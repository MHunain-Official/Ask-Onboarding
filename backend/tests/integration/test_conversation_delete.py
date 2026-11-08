"""Deleting a conversation removes messages for the owner only; tickets/audit stay."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Conversation, Message, MessageRole, Ticket, TicketStatus, User
from tests.integration.sse_helpers import CSRF_HEADERS


def test_owner_can_delete_conversation_and_messages(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    conversation = Conversation(user_id=demo_user.id, title="VPN help")
    db.add(conversation)
    db.flush()
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="How do I VPN?",
        )
    )
    db.commit()
    conversation_id = conversation.id

    client = make_client(demo_user)
    response = client.delete(f"/api/conversations/{conversation_id}", headers=CSRF_HEADERS)
    assert response.status_code == 204
    assert db.get(Conversation, conversation_id) is None
    assert db.query(Message).filter(Message.conversation_id == conversation_id).count() == 0


def test_delete_conversation_requires_csrf(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    conversation = Conversation(user_id=demo_user.id, title="No CSRF")
    db.add(conversation)
    db.commit()
    client = make_client(demo_user)
    response = client.delete(f"/api/conversations/{conversation.id}")
    assert response.status_code == 403


def test_cannot_delete_another_users_conversation(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    other = User(email="deleter-other@demo.local", name="Other", role=demo_user.role)
    db.add(other)
    db.flush()
    conversation = Conversation(user_id=other.id, title="Secret chat")
    db.add(conversation)
    db.commit()

    client = make_client(demo_user)
    response = client.delete(f"/api/conversations/{conversation.id}", headers=CSRF_HEADERS)
    assert response.status_code == 404
    assert db.get(Conversation, conversation.id) is not None


def test_delete_nulls_ticket_conversation_link(
    db: Session, demo_user: User, make_client: Callable[..., TestClient]
) -> None:
    conversation = Conversation(user_id=demo_user.id, title="Ticketed")
    db.add(conversation)
    db.flush()
    ticket = Ticket(
        title="Need help",
        question="Where is the handbook?",
        user_id=demo_user.id,
        status=TicketStatus.OPEN,
        conversation_id=conversation.id,
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    conversation_id = conversation.id

    client = make_client(demo_user)
    assert (
        client.delete(f"/api/conversations/{conversation_id}", headers=CSRF_HEADERS).status_code
        == 204
    )
    db.refresh(ticket)
    kept = db.get(Ticket, ticket_id)
    assert kept is not None
    assert kept.conversation_id is None
