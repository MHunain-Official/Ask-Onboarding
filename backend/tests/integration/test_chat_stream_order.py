"""Integration test for SSE event ordering and audit persistence
(AGENTS.md §5.4, §3.6): `meta` always comes first, `token`s stream the
answer, `citations`/`ticket_offer` come after the text, `done` is last,
and the full `llm_calls` row (and `usage_daily`) is written.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.fake_embedder import FakeEmbedder
from app.llm.fake_llm import FakeLlm, ScriptedResponse
from app.models import (
    AccessLevel,
    Document,
    DocumentChunk,
    DocumentStatus,
    LlmCall,
    LlmCallStatus,
    UsageDaily,
    User,
)
from tests.integration.sse_helpers import CSRF_HEADERS, read_sse_events

EMBEDDER = FakeEmbedder()


def _seed_vpn_chunk(db: Session, user: User) -> None:
    text = "The VPN setup guide explains how to configure the virtual private network client."
    document = Document(
        filename="vpn-guide.md",
        content_type="text/markdown",
        storage_path="/tmp/vpn-guide.md",
        content_hash=hashlib.sha256(b"vpn").hexdigest(),
        access_level=AccessLevel.ALL,
        version=1,
        status=DocumentStatus.READY,
        chunk_count=1,
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    chunk = DocumentChunk(
        document_id=document.id,
        document_version=1,
        chunk_index=0,
        text=text,
        text_hash=hashlib.sha256(text.encode()).hexdigest(),
        char_start=0,
        char_end=len(text),
        heading=None,
        token_count=len(text.split()),
        embedding=EMBEDDER.embed_texts([text])[0],
        access_level=AccessLevel.ALL,
    )
    db.add(chunk)
    db.commit()


def test_events_arrive_in_order_and_llm_call_is_persisted(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_vpn_chunk(db, demo_user)
    llm = FakeLlm([ScriptedResponse(text="The VPN client is configured via the guide [1].")])
    client = make_client(demo_user, llm_client=llm)

    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"question": "How do I configure the VPN client?"},
        headers=CSRF_HEADERS,
    ) as response:
        assert response.status_code == 200
        events = read_sse_events(response)

    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert names.count("token") >= 1
    assert names.index("citations") < names.index("done")
    # Tokens arrive as separate events, not one giant blob — proves this
    # really streamed rather than buffering the whole answer first.
    assert names.count("token") > 1

    token_events = [payload for name, payload in events if name == "token"]
    joined = "".join(str(payload["text"]) for payload in token_events)
    assert joined == "The VPN client is configured via the guide [1]."

    call = db.query(LlmCall).one()
    assert call.status == LlmCallStatus.OK
    assert call.model_used == "openai/gpt-4o-mini"
    assert call.fallback_used is False
    assert call.input_tokens is not None
    assert call.output_tokens is not None
    assert call.latency_ms_total is not None
    assert call.retrieved_chunk_ids

    now = datetime.now(UTC)
    today_midnight = datetime(now.year, now.month, now.day)
    usage_row = (
        db.query(UsageDaily)
        .filter(UsageDaily.user_id == demo_user.id, UsageDaily.date == today_midnight)
        .first()
    )
    assert usage_row is not None
    assert usage_row.requests == 1
    assert usage_row.input_tokens > 0
