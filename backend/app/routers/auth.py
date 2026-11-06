"""Demo login: pick a seeded user by email, no password (AGENTS.md §1, §8.3)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, UserPublic
from app.security import clear_session_cookie, create_session_cookie, require_user
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserPublic)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    """Log in as one of the seeded demo users. This is a demo app: there is
    no password, matching the owner's explicit choice of a simple login."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown demo user")
    create_session_cookie(response, user)
    record_audit_event(
        db,
        event_type="login",
        request_id=getattr(request.state, "request_id", None),
        user_id=user.id,
    )
    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    clear_session_cookie(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(require_user)) -> User:
    return user
