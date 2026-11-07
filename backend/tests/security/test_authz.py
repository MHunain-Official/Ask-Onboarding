"""Core authz/abuse-prevention suite (AGENTS.md §3.2, §5.12 #21-#24):
no cookie means 401, the wrong role means 403 on an admin-only route, too
many requests in a minute means 429, and a state-changing POST without the
CSRF header is rejected — each proven against the real FastAPI app, not a
unit test of the dependency function in isolation.
"""

import io
import uuid
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.llm.fake_llm import FakeLlm, ScriptedResponse
from app.main import app
from app.models import User
from tests.integration.sse_helpers import CSRF_HEADERS


@pytest.fixture
def anonymous_client(db: Session) -> Generator[TestClient, None, None]:
    """A `TestClient` with no session cookie and no `require_user` override
    — the real 401 path, not a stand-in for it. `get_db` is still swapped
    for the test session so the request never touches a stray connection."""

    def _db_override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _db_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unauthenticated_request_to_documents_returns_401(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/documents")
    assert response.status_code == 401


def test_unauthenticated_chat_request_returns_401_even_with_csrf_header(
    anonymous_client: TestClient,
) -> None:
    """CSRF header alone must never be mistaken for authentication."""
    response = anonymous_client.post(
        "/api/chat/stream", json={"question": "hi"}, headers=CSRF_HEADERS
    )
    assert response.status_code == 401


def test_employee_gets_403_on_the_admin_only_audit_events_route(
    make_client: Callable[..., TestClient], demo_user: User
) -> None:
    client = make_client(demo_user)
    response = client.get("/api/admin/audit-events")
    assert response.status_code == 403


def test_admin_can_read_the_admin_only_audit_events_route(
    make_client: Callable[..., TestClient], admin_user: User
) -> None:
    client = make_client(admin_user)
    response = client.get("/api/admin/audit-events")
    assert response.status_code == 200
    assert "items" in response.json()


def test_manager_also_gets_403_on_the_admin_only_route(
    make_client: Callable[..., TestClient], manager_user: User
) -> None:
    """Admin-only means admin-only: a manager is not an admin either."""
    client = make_client(manager_user)
    response = client.get("/api/admin/audit-events")
    assert response.status_code == 403


def test_chat_without_the_csrf_header_is_rejected(
    make_client: Callable[..., TestClient], demo_user: User
) -> None:
    client = make_client(demo_user)
    response = client.post("/api/chat/stream", json={"question": "hi"})
    assert response.status_code == 403


def test_document_upload_without_the_csrf_header_is_rejected(
    make_client: Callable[..., TestClient], demo_user: User
) -> None:
    client = make_client(demo_user)
    response = client.post(
        "/api/documents",
        files={"file": ("notes.md", io.BytesIO(b"# Notes"), "text/markdown")},
    )
    assert response.status_code == 403


def test_document_delete_without_the_csrf_header_is_rejected(
    make_client: Callable[..., TestClient], demo_user: User
) -> None:
    client = make_client(demo_user)
    response = client.delete(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == 403


def test_chat_rate_limit_returns_429_after_the_per_minute_cap_is_exceeded(
    make_client: Callable[..., TestClient], demo_user: User
) -> None:
    low_limit_settings = get_settings().model_copy(update={"rate_limit_chat_per_minute": 2})
    app.dependency_overrides[get_settings] = lambda: low_limit_settings

    llm = FakeLlm([ScriptedResponse(text="ok") for _ in range(5)])
    client = make_client(demo_user, llm_client=llm)

    statuses = []
    for _ in range(3):
        with client.stream(
            "POST", "/api/chat/stream", json={"question": "hi"}, headers=CSRF_HEADERS
        ) as response:
            statuses.append(response.status_code)

    assert statuses[:2] == [200, 200]
    assert statuses[2] == 429


def test_upload_rate_limit_returns_429_after_the_per_minute_cap_is_exceeded(
    make_client: Callable[..., TestClient], manager_user: User
) -> None:
    low_limit_settings = get_settings().model_copy(update={"rate_limit_upload_per_minute": 1})
    app.dependency_overrides[get_settings] = lambda: low_limit_settings
    client = make_client(manager_user)

    first = client.post(
        "/api/documents",
        files={"file": ("one.md", io.BytesIO(b"# One"), "text/markdown")},
        headers=CSRF_HEADERS,
    )
    second = client.post(
        "/api/documents",
        files={"file": ("two.md", io.BytesIO(b"# Two"), "text/markdown")},
        headers=CSRF_HEADERS,
    )

    assert first.status_code == 201
    assert second.status_code == 429
