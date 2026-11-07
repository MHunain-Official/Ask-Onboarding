"""Signed-cookie sessions for the demo login (AGENTS.md §1: simple, not an IdP).

The cookie holds only a user id, signed with `itsdangerous` so it cannot be
forged or edited by the browser. There is no password: the owner explicitly
chose a password-less demo login and documents it as such in the README.
"""

import uuid
from collections.abc import Callable

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AccessLevel, User, UserRole

SESSION_COOKIE_NAME = "ask_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key, salt="ask-onboarding-session")


def create_session_cookie(response: Response, user: User) -> None:
    """Sign the user id and set it as an HttpOnly cookie on the response."""
    settings = get_settings()
    token = _serializer().dumps({"user_id": str(user.id)})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def _read_user_id_from_cookie(cookie_value: str) -> uuid.UUID:
    try:
        payload = _serializer().loads(cookie_value, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired"
        ) from exc
    try:
        return uuid.UUID(payload["user_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired"
        ) from exc


def require_user(
    ask_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: return the logged-in user or raise 401."""
    if ask_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    user_id = _read_user_id_from_cookie(ask_session)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    return user


def require_role(*allowed_roles: UserRole) -> Callable[..., User]:
    """Build a dependency that only lets the given roles through (403 otherwise)."""

    def dependency(user: User = Depends(require_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for this role"
            )
        return user

    return dependency


def require_csrf_header(request: Request) -> None:
    """Simple CSRF defence for state-changing routes (AGENTS.md §3.2): a
    cross-site form submission cannot set a custom header, so requiring
    one here (plus the `SameSite=Lax` cookie) proves the request came from
    our own frontend JS, not a forged cross-site form post."""
    if not request.headers.get("X-Requested-With") and not request.headers.get("X-CSRF-Token"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")


def allowed_access_levels(user: User) -> list[AccessLevel]:
    """Which document access levels this user may read.

    Employees: `all` only.
    Managers: `all` + `managers`.
    Admins: `all` + `managers` + `admins`.

    Single source of truth for every retrieval query and document endpoint
    (AGENTS.md §5.7) — never re-implemented elsewhere.
    """
    if user.role == UserRole.ADMIN:
        return [AccessLevel.ALL, AccessLevel.MANAGERS, AccessLevel.ADMINS]
    if user.role == UserRole.MANAGER:
        return [AccessLevel.ALL, AccessLevel.MANAGERS]
    return [AccessLevel.ALL]


def can_manage_documents(user: User) -> bool:
    """Only managers and admins may upload, re-upload, retry, or delete docs."""
    return user.role in (UserRole.MANAGER, UserRole.ADMIN)


def can_manage_tickets(user: User) -> bool:
    """Managers and admins triage help-desk tickets for everyone."""
    return user.role in (UserRole.MANAGER, UserRole.ADMIN)
