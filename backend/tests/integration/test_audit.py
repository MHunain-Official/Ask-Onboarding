"""Direct tests for `audit_service.record_llm_call` / `record_audit_event`
(AGENTS.md §3.6): one row is written for each outcome status, the 100 KB
field cap is enforced, and the admin routes that read this data back are
admin-only. `test_admin.py` covers the full end-to-end chat-to-admin-API
path; this file isolates the write side so a regression here fails fast
and close to the cause.
"""

import uuid
from collections.abc import Callable, Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import AuditEvent, CacheHit, LlmCall, LlmCallStatus, User
from app.services.audit_service import LlmCallRecord, record_audit_event, record_llm_call


def _record(db: Session, user: User, call_status: LlmCallStatus, **overrides: object) -> LlmCall:
    record = LlmCallRecord(
        request_id=str(uuid.uuid4()),
        status=call_status,
        prompt_version="v1",
        user_id=user.id,
        question="How do I configure the VPN?",
        **overrides,  # type: ignore[arg-type]
    )
    return record_llm_call(db, record)


def test_record_llm_call_writes_a_row_for_an_ok_answer(db: Session, demo_user: User) -> None:
    row = _record(
        db,
        demo_user,
        LlmCallStatus.OK,
        model="openai/gpt-4o-mini",
        input_tokens=10,
        output_tokens=20,
    )

    saved = db.get(LlmCall, row.id)
    assert saved is not None
    assert saved.status == LlmCallStatus.OK
    assert saved.model == "openai/gpt-4o-mini"
    assert saved.input_tokens == 10
    assert saved.output_tokens == 20


def test_record_llm_call_writes_a_row_for_an_error(db: Session, demo_user: User) -> None:
    row = _record(
        db,
        demo_user,
        LlmCallStatus.ERROR,
        error_type="provider_down",
        error_message="primary and fallback both failed",
    )

    saved = db.get(LlmCall, row.id)
    assert saved is not None
    assert saved.status == LlmCallStatus.ERROR
    assert saved.error_type == "provider_down"
    assert saved.error_message == "primary and fallback both failed"


def test_record_llm_call_writes_no_answer_gate_hit(db: Session, demo_user: User) -> None:
    """Gate #1 (§5.3) never calls the LLM — `model` stays `None`."""
    row = _record(db, demo_user, LlmCallStatus.NO_ANSWER, cache_hit=CacheHit.NONE)

    saved = db.get(LlmCall, row.id)
    assert saved is not None
    assert saved.status == LlmCallStatus.NO_ANSWER
    assert saved.model is None


def test_record_llm_call_caps_oversized_fields_at_100kb(db: Session, demo_user: User) -> None:
    """The owner's "never truncate to zero, but cap at 100 KB" rule
    (§3.6): a 200 KB model response must be capped, not dropped entirely."""
    huge_response = "x" * 200_000
    row = _record(db, demo_user, LlmCallStatus.OK, model_response=huge_response)

    saved = db.get(LlmCall, row.id)
    assert saved is not None
    assert saved.model_response is not None
    assert 0 < len(saved.model_response.encode("utf-8")) <= 100_000


def test_record_audit_event_writes_an_append_only_row(db: Session, demo_user: User) -> None:
    record_audit_event(
        db,
        event_type="login",
        request_id="req-123",
        user_id=demo_user.id,
        details={"email": demo_user.email},
    )

    saved = db.query(AuditEvent).filter(AuditEvent.event_type == "login").one()
    assert saved.user_id == demo_user.id
    assert saved.details == {"email": demo_user.email}
    assert saved.request_id == "req-123"


def test_admin_routes_reject_a_non_admin_and_accept_an_admin(
    demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    employee_client = make_client(demo_user)
    assert employee_client.get("/api/admin/stats").status_code == 403
    assert employee_client.get("/api/admin/llm-calls").status_code == 403
    assert employee_client.get("/api/admin/audit-events").status_code == 403

    admin_client = make_client(admin_user)
    assert admin_client.get("/api/admin/stats").status_code == 200
    assert admin_client.get("/api/admin/llm-calls").status_code == 200
    assert admin_client.get("/api/admin/audit-events").status_code == 200


def test_admin_routes_require_authentication(db: Session) -> None:
    """No session cookie at all must 401, not 403 — a different failure
    than "logged in as the wrong role" (checked above)."""

    def _db_override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _db_override
    try:
        anonymous = TestClient(app)
        assert anonymous.get("/api/admin/stats").status_code == 401
    finally:
        app.dependency_overrides.clear()
