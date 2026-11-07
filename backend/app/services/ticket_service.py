"""Help-desk tickets. The user on a ticket always comes from the session
(AGENTS.md §3.2 rule 3). Managers/admins triage; employees see their own.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models import Ticket, TicketStatus, User
from app.security import can_manage_tickets
from app.services.audit_service import record_audit_event

DEDUPE_WINDOW_MINUTES = 10

# Staff may move a ticket through this lifecycle; employees only create/open.
_STAFF_STATUSES = {
    TicketStatus.OPEN,
    TicketStatus.IN_REVIEW,
    TicketStatus.IN_PROGRESS,
    TicketStatus.ANSWERED,
    TicketStatus.CLOSED,
}


def create_ticket(
    db: Session,
    *,
    user: User,
    title: str,
    question: str,
    conversation_id: uuid.UUID | None,
    request_id: str | None = None,
) -> Ticket:
    """Double-clicking Yes must not create two tickets (§5.12 #22)."""
    existing = _find_recent_duplicate(db, user.id, question)
    if existing is not None:
        return existing

    ticket = Ticket(
        title=title[:200],
        question=question[:2000],
        user_id=user.id,
        conversation_id=conversation_id,
        status=TicketStatus.OPEN,
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
    """Managers and admins see every ticket (help-desk queue). Employees see
    only their own, including status updates from staff."""
    query = db.query(Ticket).options(joinedload(Ticket.user)).order_by(Ticket.created_at.desc())
    if not can_manage_tickets(user):
        query = query.filter(Ticket.user_id == user.id)
    return query.all()


def update_ticket_status(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    new_status: TicketStatus,
    actor: User,
    request_id: str | None = None,
) -> Ticket:
    if not can_manage_tickets(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only managers and admins may update tickets")
    if new_status not in _STAFF_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown ticket status")
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    previous = ticket.status
    ticket.status = new_status
    db.commit()
    db.refresh(ticket)
    record_audit_event(
        db,
        event_type="ticket_status_updated",
        request_id=request_id,
        user_id=actor.id,
        details={
            "ticket_id": str(ticket.id),
            "from": previous.value,
            "to": new_status.value,
        },
    )
    return ticket


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
