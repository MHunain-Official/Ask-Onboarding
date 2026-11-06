"""Integration test for the no-answer gate (AGENTS.md §5.3 gate #1,
§5.12 #29): an unrelated question must never reach the LLM at all, and the
user still gets an honest "not found" answer plus a ticket offer.
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
from tests.integration.sse_helpers import CSRF_HEADERS, read_sse_events

EMBEDDER = FakeEmbedder()


def _seed_unrelated_chunk(db: Session, user: User) -> None:
    text = "The payroll calendar lists paydays for every month of the year."
    document = Document(
        filename="payroll.md",
        content_type="text/markdown",
        storage_path="/tmp/payroll.md",
        content_hash=hashlib.sha256(b"payroll").hexdigest(),
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


def test_unrelated_question_skips_the_llm_and_offers_a_ticket(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_unrelated_chunk(db, demo_user)
    fake_llm = FakeLlm([ScriptedResponse(text="this should never be used")])
    client = make_client(demo_user, llm_client=fake_llm)

    # `FakeEmbedder` is bag-of-words with no stopword removal (AGENTS.md
    # §3.3), so a question sharing a common stopword with the seeded
    # document could score above the gate by accident. This question
    # shares no words at all with the payroll chunk.
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"question": "How many moons does Jupiter have?"},
        headers=CSRF_HEADERS,
    ) as response:
        assert response.status_code == 200
        events = read_sse_events(response)

    event_names = [name for name, _ in events]
    assert "ticket_offer" in event_names
    assert "done" in event_names
    done_payload = dict(events[event_names.index("done")][1])
    assert done_payload["status"] == "no_answer"

    # The core assertion (§9): the fake LLM was never called at all.
    assert fake_llm.calls == []

    call = db.query(LlmCall).one()
    assert call.status == LlmCallStatus.NO_ANSWER
    assert call.model is None
