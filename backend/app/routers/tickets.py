"""Help-desk ticket endpoints (AGENTS.md §5.6). State-changing `POST`
requires the CSRF header (§3.2); the user on a created ticket always comes
from the session, never from the request body.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import TicketCreateRequest, TicketListResponse, TicketPublic
from app.security import require_csrf_header, require_user
from app.services.ticket_service import create_ticket, list_tickets

router = APIRouter(prefix="/api", tags=["tickets"])


@router.post(
    "/tickets",
    response_model=TicketPublic,
    status_code=status.HTTP_201_CREATED,
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
    return TicketPublic.model_validate(ticket)


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets_endpoint(
    user: User = Depends(require_user), db: Session = Depends(get_db)
) -> TicketListResponse:
    """Employees and managers see only their own tickets; admins see all."""
    tickets = list_tickets(db, user)
    return TicketListResponse(items=[TicketPublic.model_validate(t) for t in tickets])
