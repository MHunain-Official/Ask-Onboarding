"""Integration test for ticket creation (AGENTS.md §5.6, §5.12 #22): "Yes"
saves a ticket from the session user, double-clicking is idempotent, and
employees can only ever see their own tickets.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.integration.sse_helpers import CSRF_HEADERS


def test_creating_a_ticket_saves_title_question_and_session_user(
    demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    client = make_client(demo_user)
    response = client.post(
        "/api/tickets",
        json={"title": "Can't find VPN setup steps", "question": "How do I set up the VPN?"},
        headers=CSRF_HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Can't find VPN setup steps"
    assert body["question"] == "How do I set up the VPN?"
    assert body["user_id"] == str(demo_user.id)
    assert body["status"] == "open"


def test_ticket_requires_csrf_header(
    demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    client = make_client(demo_user)
    response = client.post("/api/tickets", json={"title": "No header", "question": "Question?"})
    assert response.status_code == 403


def test_double_click_within_dedupe_window_returns_the_same_ticket(
    demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    client = make_client(demo_user)
    first = client.post(
        "/api/tickets",
        json={"title": "Same question", "question": "Where is the handbook?"},
        headers=CSRF_HEADERS,
    )
    second = client.post(
        "/api/tickets",
        json={"title": "Same question again", "question": "Where is the handbook?"},
        headers=CSRF_HEADERS,
    )
    assert first.json()["id"] == second.json()["id"]


def test_employee_cannot_see_another_employees_tickets(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    from app.models import User as UserModel
    from app.models import UserRole

    other_user = UserModel(email="other@demo.local", name="Other", role=UserRole.EMPLOYEE)
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    other_client = make_client(other_user)
    other_client.post(
        "/api/tickets",
        json={"title": "Other person's ticket", "question": "Other question?"},
        headers=CSRF_HEADERS,
    )

    demo_client = make_client(demo_user)
    demo_client.post(
        "/api/tickets",
        json={"title": "My ticket", "question": "My question?"},
        headers=CSRF_HEADERS,
    )

    response = demo_client.get("/api/tickets")
    titles = [item["title"] for item in response.json()["items"]]
    assert "My ticket" in titles
    assert "Other person's ticket" not in titles


def test_admin_sees_every_users_tickets(
    db: Session, demo_user: User, admin_user: User, make_client: Callable[..., TestClient]
) -> None:
    employee_client = make_client(demo_user)
    employee_client.post(
        "/api/tickets",
        json={"title": "Employee ticket", "question": "Employee question?"},
        headers=CSRF_HEADERS,
    )

    admin_client = make_client(admin_user)
    response = admin_client.get("/api/tickets")
    titles = [item["title"] for item in response.json()["items"]]
    assert "Employee ticket" in titles
