"""Help-desk ticket endpoints (AGENTS.md §5.6). CSRF on state-changing routes."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    TicketCreateRequest,
    TicketListResponse,
    TicketPublic,
    TicketStatusUpdateRequest,
)
from app.security import require_csrf_header, require_user
from app.services.ticket_service import create_ticket, list_tickets, update_ticket_status

router = APIRouter(prefix="/api", tags=["tickets"])


def _to_public(ticket: object) -> TicketPublic:
    public = TicketPublic.model_validate(ticket)
    user = getattr(ticket, "user", None)
    if user is not None:
        public.user_name = getattr(user, "name", None)
    return public


@router.post(
    "/tickets",
    response_model=TicketPublic,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_ticket_endpoint(
    body: TicketCreateRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> TicketPublic:
    ticket = create_ticket(
        db,
        user=user,
        title=body.title,
        question=body.question,
        conversation_id=body.conversation_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return _to_public(ticket)


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets_endpoint(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> TicketListResponse:
    tickets = list_tickets(db, user)
    return TicketListResponse(items=[_to_public(ticket) for ticket in tickets])


@router.patch(
    "/tickets/{ticket_id}",
    response_model=TicketPublic,
    dependencies=[Depends(require_csrf_header)],
)
def update_ticket_endpoint(
    ticket_id: uuid.UUID,
    body: TicketStatusUpdateRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> TicketPublic:
    ticket = update_ticket_status(
        db,
        ticket_id=ticket_id,
        new_status=body.status,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
    )
    return _to_public(ticket)
