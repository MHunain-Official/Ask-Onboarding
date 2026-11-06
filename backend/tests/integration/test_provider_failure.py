"""Integration test for provider failure handling (AGENTS.md §5.9 #1,
§5.12 #1): when both the primary and fallback model fail, the user gets a
friendly `error` event (never a raw stack trace), and the failure is
fully audited.
"""

import hashlib
from collections.abc import Callable

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
    User,
)
from app.services.fallback_responses import PROVIDER_UNAVAILABLE_TEXT
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


def test_primary_and_fallback_both_down_emits_friendly_error_event(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_vpn_chunk(db, demo_user)
    llm = FakeLlm(
        [
            ScriptedResponse(raise_error=ConnectionError("primary provider down")),
            ScriptedResponse(raise_error=ConnectionError("fallback provider down")),
        ]
    )
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
    assert "error" in names
    error_payload = dict(events[names.index("error")][1])
    assert error_payload["message"] == PROVIDER_UNAVAILABLE_TEXT
    assert "request_id" in error_payload
    # Never a raw stack trace or exception repr reaches the client:
    assert "ConnectionError" not in error_payload["message"]
    assert "Traceback" not in error_payload["message"]
    assert names[-1] == "done"

    call = db.query(LlmCall).one()
    assert call.status == LlmCallStatus.ERROR
    assert call.error_type == "provider_down"
    assert call.error_message is not None and "provider down" in call.error_message
