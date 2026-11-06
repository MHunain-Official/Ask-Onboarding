"""Integration tests for the admin observability APIs (AGENTS.md §3.6,
§5.10): stats tiles, the full `llm_calls` audit trail (ok/error/no_answer),
the audit-events log, and that every route 403s for a non-admin.
"""

import hashlib
import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.fake_embedder import FakeEmbedder
from app.llm.fake_llm import FakeLlm, ScriptedResponse
from app.llm.prompts import SYSTEM_PROMPT_V1
from app.models import AccessLevel, Document, DocumentChunk, DocumentStatus, LlmCall, User
from tests.integration.sse_helpers import CSRF_HEADERS, read_sse_events

EMBEDDER = FakeEmbedder()


def _seed_chunk(db: Session, user: User, filename: str, text: str) -> None:
    document = Document(
        filename=filename,
        content_type="text/markdown",
        storage_path=f"/tmp/{filename}",
        content_hash=hashlib.sha256(filename.encode()).hexdigest(),
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


def _ask(client: TestClient, question: str) -> list[tuple[str, dict[str, object]]]:
    with client.stream(
        "POST", "/api/chat/stream", json={"question": question}, headers=CSRF_HEADERS
    ) as response:
        assert response.status_code == 200
        return read_sse_events(response)


def _seed_three_calls(db: Session, demo_user: User, make_client: Callable[..., TestClient]) -> None:
    """One `ok`, one `error` (both models down) and one `no_answer` (gate
    #1, unrelated question) `llm_calls` row — each via the real
    `/api/chat/stream` flow so the rows are written exactly as production
    would write them, not hand-inserted."""
    _seed_chunk(
        db,
        demo_user,
        "vpn-guide.md",
        "The VPN setup guide explains how to configure the virtual private network client.",
    )

    # Deliberately different phrasings (not just the no-answer question):
    # the exact answer cache (§5.10 L1) is keyed by the normalised question
    # text, so re-asking the identical question would serve the first
    # answer from the cache instead of producing a second, distinct row.
    ok_llm = FakeLlm([ScriptedResponse(text="The VPN client is configured via the guide [1].")])
    _ask(make_client(demo_user, llm_client=ok_llm), "How do I configure the VPN client?")

    error_llm = FakeLlm(
        [
            ScriptedResponse(raise_error=ConnectionError("primary down")),
            ScriptedResponse(raise_error=ConnectionError("fallback down")),
        ]
    )
    _ask(make_client(demo_user, llm_client=error_llm), "How do I set up the VPN client?")

    # FakeEmbedder is bag-of-words (AGENTS.md §3.3): this question shares no
    # words with the VPN chunk, so it never passes the similarity gate and
    # the LLM below is never even called.
    no_answer_llm = FakeLlm([ScriptedResponse(text="unused")])
    _ask(make_client(demo_user, llm_client=no_answer_llm), "How many moons does Jupiter have?")
    assert no_answer_llm.calls == []


def test_non_admin_gets_403_on_every_admin_route(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    client = make_client(demo_user)
    random_id = uuid.uuid4()

    assert client.get("/api/admin/stats").status_code == 403
    assert client.get("/api/admin/llm-calls").status_code == 403
    assert client.get(f"/api/admin/llm-calls/{random_id}").status_code == 403
    assert client.get("/api/admin/audit-events").status_code == 403


def test_stats_reflect_ok_error_and_no_answer_calls(
    db: Session, demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_three_calls(db, demo_user, make_client)
    assert db.query(LlmCall).count() == 3

    admin_client = make_client(admin_user)
    response = admin_client.get("/api/admin/stats")
    assert response.status_code == 200
    stats = response.json()

    assert stats["total_requests"] == 3
    assert stats["error_rate"] == round(1 / 3, 4)
    assert stats["no_answer_rate"] == round(1 / 3, 4)
    # No cache hits were produced in this test (every question differs or
    # fails before a cache write) — only the gated no-answer was avoided.
    assert stats["llm_calls_avoided"] == 1
    assert stats["cache_hit_rate"] == 0.0
    assert stats["total_cost_usd"] >= 0.0
    assert stats["p50_latency_ms"] >= 0.0
    assert stats["p95_latency_ms"] >= stats["p50_latency_ms"]


def test_llm_calls_listing_supports_status_and_pagination_filters(
    db: Session, demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_three_calls(db, demo_user, make_client)
    admin_client = make_client(admin_user)

    all_calls = admin_client.get("/api/admin/llm-calls")
    assert all_calls.status_code == 200
    body = all_calls.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["items"][0]["user_name"] == demo_user.name

    only_errors = admin_client.get("/api/admin/llm-calls", params={"status": "error"})
    assert only_errors.status_code == 200
    error_body = only_errors.json()
    assert error_body["total"] == 1
    assert error_body["items"][0]["status"] == "error"

    only_user = admin_client.get(
        "/api/admin/llm-calls", params={"user_id": str(demo_user.id), "page_size": 2}
    )
    assert only_user.status_code == 200
    paged_body = only_user.json()
    assert paged_body["total"] == 3  # total ignores the page size
    assert len(paged_body["items"]) == 2  # but only one page's worth comes back


def test_llm_call_detail_contains_the_full_prompt_and_is_admin_only(
    db: Session, demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_three_calls(db, demo_user, make_client)
    ok_call = db.query(LlmCall).filter(LlmCall.status == "ok").one()

    admin_client = make_client(admin_user)
    response = admin_client.get(f"/api/admin/llm-calls/{ok_call.id}")
    assert response.status_code == 200
    detail = response.json()

    assert detail["system_prompt"] is not None
    assert SYSTEM_PROMPT_V1 in detail["system_prompt"]
    assert detail["model_response"] == "The VPN client is configured via the guide [1]."
    assert detail["messages_sent"]
    assert detail["retrieved_chunks"]
    assert detail["retrieved_chunks"][0]["score"] > 0

    employee_client = make_client(demo_user)
    forbidden = employee_client.get(f"/api/admin/llm-calls/{ok_call.id}")
    assert forbidden.status_code == 403


def test_missing_llm_call_is_404(admin_user: User, make_client: Callable[..., TestClient]) -> None:
    admin_client = make_client(admin_user)
    response = admin_client.get(f"/api/admin/llm-calls/{uuid.uuid4()}")
    assert response.status_code == 404


def test_audit_events_lists_the_provider_outage_event_and_is_admin_only(
    db: Session, demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    _seed_three_calls(db, demo_user, make_client)

    admin_client = make_client(admin_user)
    response = admin_client.get("/api/admin/audit-events")
    assert response.status_code == 200
    body = response.json()
    event_types = [item["event_type"] for item in body["items"]]
    assert "llm_provider_unavailable" in event_types

    outage_event = next(
        item for item in body["items"] if item["event_type"] == "llm_provider_unavailable"
    )
    assert outage_event["user_id"] == str(demo_user.id)
    assert outage_event["detail"] is not None

    employee_client = make_client(demo_user)
    assert employee_client.get("/api/admin/audit-events").status_code == 403
