"""Admin-only observability APIs (AGENTS.md §3.6, §6): stats tiles, the
full `llm_calls` audit trail (exact prompt/response/chunks/timings/cost),
and the append-only `audit_events` log.

`require_role(UserRole.ADMIN)` is applied once, at the router level, so a
non-admin request is rejected before it ever reaches a query that could
leak a prompt or another user's question (AGENTS.md §3.2: access control
belongs in the query path, not as an afterthought).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditEvent, LlmCall, LlmCallStatus, UserRole
from app.schemas import (
    AdminStats,
    AuditEventListResponse,
    LlmCallDetail,
    LlmCallListResponse,
    ProjectDocContent,
    ProjectDocListResponse,
    ProjectDocMeta,
)
from app.security import require_role
from app.services.admin_query_service import (
    filter_audit_events,
    filter_llm_calls,
    to_audit_event_public,
    to_llm_call_detail,
    to_llm_call_summary,
    user_names_by_id,
)
from app.services.admin_stats_service import compute_admin_stats
from app.services.project_docs_service import (
    ProjectDocsError,
    list_project_docs,
    read_project_doc,
    resolve_docs_root,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(db: Session = Depends(get_db)) -> AdminStats:
    return compute_admin_stats(db)


@router.get("/llm-calls", response_model=LlmCallListResponse)
def list_llm_calls(
    call_status: LlmCallStatus | None = Query(default=None, alias="status"),
    user_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> LlmCallListResponse:
    query = filter_llm_calls(
        db, status=call_status, user_id=user_id, date_from=date_from, date_to=date_to
    )
    total = query.count()
    rows = (
        query.order_by(LlmCall.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    names = user_names_by_id(db, {row.user_id for row in rows if row.user_id})
    return LlmCallListResponse(items=[to_llm_call_summary(row, names) for row in rows], total=total)


@router.get("/llm-calls/{call_id}", response_model=LlmCallDetail)
def get_llm_call_detail(call_id: uuid.UUID, db: Session = Depends(get_db)) -> LlmCallDetail:
    row = db.get(LlmCall, call_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LLM call not found")
    names = user_names_by_id(db, {row.user_id} if row.user_id else set())
    return to_llm_call_detail(row, names)


@router.get("/audit-events", response_model=AuditEventListResponse)
def list_audit_events(
    event_type: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> AuditEventListResponse:
    query = filter_audit_events(
        db, event_type=event_type, user_id=user_id, date_from=date_from, date_to=date_to
    )
    total = query.count()
    rows = (
        query.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditEventListResponse(items=[to_audit_event_public(row) for row in rows], total=total)


def _docs_root():
    settings = get_settings()
    configured = settings.project_docs_root.strip() or None
    return resolve_docs_root(configured), configured is not None


@router.get("/project-docs", response_model=ProjectDocListResponse)
def get_project_docs_index() -> ProjectDocListResponse:
    root, configured = _docs_root()
    items = [
        ProjectDocMeta(path=entry.path, title=entry.title, group=entry.group)
        for entry in list_project_docs(root)
    ]
    return ProjectDocListResponse(items=items, root_configured=configured or root.exists())


@router.get("/project-docs/content", response_model=ProjectDocContent)
def get_project_doc_content(
    path: str = Query(min_length=1, max_length=400),
) -> ProjectDocContent:
    root, _ = _docs_root()
    try:
        entry, text = read_project_doc(root, path)
    except ProjectDocsError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return ProjectDocContent(
        path=entry.path,
        title=entry.title,
        group=entry.group,
        content=text,
    )
