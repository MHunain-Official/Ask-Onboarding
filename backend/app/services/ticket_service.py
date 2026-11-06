"""Help-desk tickets (AGENTS.md §5.6). The user on a ticket always comes
from the authenticated session — never from the model's tool-call output
or anything else in the request body (AGENTS.md §3.2 rule 3).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Ticket, TicketStatus, User, UserRole
from app.services.audit_service import record_audit_event

DEDUPE_WINDOW_MINUTES = 10


def create_ticket(
    db: Session,
    *,
    user: User,
    title: str,
    question: str,
    conversation_id: uuid.UUID | None,
    request_id: str | None = None,
) -> Ticket:
    """Double-clicking "Yes" (§5.12 #22) must not create two tickets: an
    identical open ticket from the same user within the dedupe window is
    returned unchanged instead of inserting a new row (and is not logged
    again — the audit event belongs to the ticket that was really created)."""
    existing = _find_recent_duplicate(db, user.id, question)
    if existing is not None:
        return existing

    ticket = Ticket(
        title=title[:200],
        question=question[:2000],
        user_id=user.id,
        conversation_id=conversation_id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    record_audit_event(
        db,
        event_type="ticket_created",
        request_id=request_id,
        user_id=user.id,
        details={"ticket_id": str(ticket.id), "title": ticket.title},
    )
    return ticket


def list_tickets(db: Session, user: User) -> list[Ticket]:
    """Employees and managers see only their own tickets; admins see all
    (AGENTS.md §6)."""
    query = db.query(Ticket).order_by(Ticket.created_at.desc())
    if user.role != UserRole.ADMIN:
        query = query.filter(Ticket.user_id == user.id)
    return query.all()


def _find_recent_duplicate(db: Session, user_id: uuid.UUID, question: str) -> Ticket | None:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=DEDUPE_WINDOW_MINUTES)
    return (
        db.query(Ticket)
        .filter(
            Ticket.user_id == user_id,
            Ticket.question == question[:2000],
            Ticket.status == TicketStatus.OPEN,
            Ticket.created_at >= cutoff,
        )
        .order_by(Ticket.created_at.desc())
        .first()
    )
