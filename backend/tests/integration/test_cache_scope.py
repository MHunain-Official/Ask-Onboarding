"""Integration tests for ACL-scoped answer caching (AGENTS.md §5.10 cache
safety rules, §5.12 #35): an employee-scope cache entry can never be
served to a manager or vice versa, and a re-upload invalidates it.
"""

import hashlib
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.fake_embedder import FakeEmbedder
from app.llm.fake_llm import FakeLlm, ScriptedResponse
from app.models import AccessLevel, AnswerCache, Document, DocumentChunk, DocumentStatus, User
from app.services.cache_service import invalidate_cache_for_document
from tests.integration.sse_helpers import CSRF_HEADERS, read_sse_events

EMBEDDER = FakeEmbedder()
QUESTION = "How do I configure the VPN client?"
ANSWER = "Open the VPN app and sign in with your company account [1]."


def _seed_vpn_chunk(db: Session, user: User) -> Document:
    text = "The VPN setup guide explains how to configure the virtual private network client."
    document = Document(
        filename="vpn-guide.md",
        content_type="text/markdown",
        storage_path="/tmp/vpn-guide.md",
        content_hash=hashlib.sha256(b"vpn-v1").hexdigest(),
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
    return document


def _ask(client: TestClient, llm: FakeLlm, question: str = QUESTION) -> list:
    with client.stream(
        "POST", "/api/chat/stream", json={"question": question}, headers=CSRF_HEADERS
    ) as response:
        assert response.status_code == 200
        return read_sse_events(response)


def test_second_identical_question_is_served_from_cache_without_calling_llm(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_vpn_chunk(db, demo_user)
    llm = FakeLlm([ScriptedResponse(text=ANSWER)])
    client = make_client(demo_user, llm_client=llm)

    _ask(client, llm)
    assert len(llm.calls) == 1

    second_client = make_client(demo_user, llm_client=llm)
    _ask(second_client, llm)
    assert len(llm.calls) == 1  # second ask was a cache hit: no new LLM call

    assert db.query(AnswerCache).count() == 1


def test_manager_scope_never_receives_an_employee_scoped_cache_hit(
    db: Session, demo_user: User, manager_user: User, make_client: Callable[..., TestClient]
) -> None:
    """A cache row written for the employee scope ("all") must never be
    read back for the manager scope ("all+managers"), even though both
    users ask the exact same question (AGENTS.md §5.10 cache safety rule 1).
    """
    _seed_vpn_chunk(db, demo_user)
    llm = FakeLlm([ScriptedResponse(text=ANSWER), ScriptedResponse(text=ANSWER)])

    employee_client = make_client(demo_user, llm_client=llm)
    _ask(employee_client, llm)
    assert len(llm.calls) == 1

    manager_client = make_client(manager_user, llm_client=llm)
    _ask(manager_client, llm)
    # The manager's scope is different, so this must be a fresh LLM call,
    # not a replay of the employee's cached answer.
    assert len(llm.calls) == 2

    scopes = {row.scope for row in db.query(AnswerCache).all()}
    assert scopes == {"all", "all+managers"}


def test_reupload_invalidates_the_cached_answer(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    document = _seed_vpn_chunk(db, demo_user)
    llm = FakeLlm([ScriptedResponse(text=ANSWER), ScriptedResponse(text=ANSWER)])
    client = make_client(demo_user, llm_client=llm)

    _ask(client, llm)
    assert len(llm.calls) == 1
    assert db.query(AnswerCache).filter(AnswerCache.invalidated_at.is_(None)).count() == 1

    # Simulate the worker bumping the version on re-upload (AGENTS.md §5.1):
    # the atomic swap always ends by invalidating any cache entry that
    # depended on the old version.
    document.version = 2
    db.commit()
    invalidated = invalidate_cache_for_document(db, document.id)
    assert invalidated == 1

    _ask(client, llm)
    # The stale cache entry must not be served: this is a second real call.
    assert len(llm.calls) == 2
