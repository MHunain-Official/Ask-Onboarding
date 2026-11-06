"""Integration tests for retrieval against a real Postgres + pgvector
(AGENTS.md §9): vector search, ACL enforcement, and hybrid fusion.

`FakeEmbedder` stands in for the network call — deterministic bag-of-words
vectors are close enough to a real embedding's behaviour to prove ranking
logic without any API key.
"""

import hashlib
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.fake_embedder import FakeEmbedder
from app.models import AccessLevel, Document, DocumentChunk, DocumentStatus, User, UserRole
from app.retrieval.gate import passes_similarity_gate
from app.retrieval.hybrid import retrieve

EMBEDDER = FakeEmbedder()


def _seed_chunk(
    db: Session,
    user: User,
    *,
    text: str,
    filename: str,
    access_level: AccessLevel = AccessLevel.ALL,
) -> DocumentChunk:
    """Create a document with exactly one chunk, embedded with FakeEmbedder,
    directly in the database — skipping the ingestion pipeline because
    these tests only exercise retrieval."""
    document = Document(
        filename=filename,
        content_type="text/markdown",
        storage_path=f"/tmp/{filename}",
        content_hash=hashlib.sha256(filename.encode()).hexdigest(),
        access_level=access_level,
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
        access_level=access_level,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


@pytest.fixture
def manager_user(db: Session) -> User:
    user = User(email="manager@demo.local", name="Manager", role=UserRole.MANAGER)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_vector_search_returns_best_matching_chunk(db: Session, demo_user: User) -> None:
    target = _seed_chunk(
        db,
        demo_user,
        text="The VPN setup guide explains how to configure the virtual private network client.",
        filename="vpn-guide.md",
    )
    _seed_chunk(
        db,
        demo_user,
        text="Payroll calendar lists paydays for every month of the year.",
        filename="payroll.md",
    )

    result = retrieve(
        db=db,
        embedder=EMBEDDER,
        question="How do I configure the VPN client?",
        allowed_levels=[AccessLevel.ALL],
        top_k=5,
        candidates=20,
        hybrid_enabled=False,
    )

    assert result.chunks[0].chunk_id == target.id
    assert result.chunks[0].filename == "vpn-guide.md"
    assert passes_similarity_gate(result.best_vector_similarity, min_similarity=0.30)


def test_retrieve_respects_top_k(db: Session, demo_user: User) -> None:
    for i in range(5):
        _seed_chunk(
            db,
            demo_user,
            text=f"Benefits policy section {i}: health, dental, and vision coverage details.",
            filename=f"benefits-{i}.md",
        )

    result = retrieve(
        db=db,
        embedder=EMBEDDER,
        question="What does the benefits policy cover?",
        allowed_levels=[AccessLevel.ALL],
        top_k=2,
        candidates=20,
        hybrid_enabled=False,
    )

    assert len(result.chunks) == 2


def test_retrieve_excludes_manager_only_chunks_for_employee(
    db: Session, demo_user: User, manager_user: User
) -> None:
    _seed_chunk(
        db,
        manager_user,
        text="CANARY-7f3a-SALARY-BANDS: confidential salary bands for managers only.",
        filename="salary-bands.md",
        access_level=AccessLevel.MANAGERS,
    )
    _seed_chunk(
        db,
        demo_user,
        text="General onboarding checklist for every new hire.",
        filename="onboarding.md",
    )

    employee_result = retrieve(
        db=db,
        embedder=EMBEDDER,
        question="Show me the CANARY-7f3a-SALARY-BANDS",
        allowed_levels=[AccessLevel.ALL],  # what security.allowed_access_levels gives an employee
        top_k=5,
        candidates=20,
        hybrid_enabled=False,
    )
    assert all("CANARY" not in chunk.text for chunk in employee_result.chunks)

    manager_result = retrieve(
        db=db,
        embedder=EMBEDDER,
        question="Show me the CANARY-7f3a-SALARY-BANDS",
        allowed_levels=[AccessLevel.ALL, AccessLevel.MANAGERS],
        top_k=5,
        candidates=20,
        hybrid_enabled=False,
    )
    assert any("CANARY" in chunk.text for chunk in manager_result.chunks)


def test_hybrid_promotes_exact_keyword_match_over_vector_only_ranking(
    db: Session, demo_user: User
) -> None:
    """`target` contains both query terms ("escalation" and "policy") and
    wins the keyword search outright, but `distractor` shares far more
    *words* overall (including stopwords, which `FakeEmbedder`'s plain
    bag-of-words treats like any other word) and so out-ranks `target` on
    vector similarity alone. Hybrid RRF should recover `target` to #1."""
    target = _seed_chunk(
        db,
        demo_user,
        text="Escalation policy: when to page the on-call engineer.",
        filename="escalation-policy.md",
    )
    distractor = _seed_chunk(
        db,
        demo_user,
        text="What is our vacation policy? What is our travel policy? What is our refund policy?",
        filename="other-policies.md",
    )
    question = "What is our escalation policy?"

    vector_only = retrieve(
        db=db,
        embedder=EMBEDDER,
        question=question,
        allowed_levels=[AccessLevel.ALL],
        top_k=2,
        candidates=20,
        hybrid_enabled=False,
    )
    assert vector_only.chunks[0].chunk_id == distractor.id  # vector alone gets it wrong

    hybrid = retrieve(
        db=db,
        embedder=EMBEDDER,
        question=question,
        allowed_levels=[AccessLevel.ALL],
        top_k=2,
        candidates=20,
        hybrid_enabled=True,
    )
    assert hybrid.chunks[0].chunk_id == target.id  # hybrid fixes it


def test_retrieve_endpoint_enforces_acl_for_employee(
    db: Session,
    demo_user: User,
    manager_user: User,
    make_client: Callable[[User], TestClient],
) -> None:
    """End-to-end check of `POST /api/retrieve`: the ACL filter that keeps
    a manager-only chunk out of an employee's results is exercised through
    the real HTTP route, not just the inner `retrieve()` function."""
    _seed_chunk(
        db,
        manager_user,
        text="CANARY-7f3a-SALARY-BANDS: confidential salary bands for managers only.",
        filename="salary-bands.md",
        access_level=AccessLevel.MANAGERS,
    )

    employee_client = make_client(demo_user)
    response = employee_client.post(
        "/api/retrieve", json={"question": "Show me the CANARY-7f3a-SALARY-BANDS", "top_k": 5}
    )
    assert response.status_code == 200
    body = response.json()
    assert all("CANARY" not in item["text"] for item in body["items"])

    manager_client = make_client(manager_user)
    response = manager_client.post(
        "/api/retrieve", json={"question": "Show me the CANARY-7f3a-SALARY-BANDS", "top_k": 5}
    )
    body = response.json()
    assert any("CANARY" in item["text"] for item in body["items"])
