"""Query and filtering helpers for the admin llm-calls and audit-events
tables (AGENTS.md §3.6, §6). Kept out of the router so `routers/admin.py`
stays a thin HTTP-to-service mapping the owner can read in one glance.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Query, Session

from app.models import AuditEvent, LlmCall, LlmCallStatus, User
from app.schemas import (
    AuditEventPublic,
    LlmCallDetail,
    LlmCallSummary,
    RetrievedChunkScore,
)


def to_naive_utc(value: datetime) -> datetime:
    """Query params may arrive timezone-aware (e.g. a trailing `Z`); every
    `created_at` column is naive UTC, so align before comparing."""
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def filter_llm_calls(
    db: Session,
    *,
    status: LlmCallStatus | None,
    user_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> "Query[LlmCall]":
    query = db.query(LlmCall)
    if status is not None:
        query = query.filter(LlmCall.status == status)
    if user_id is not None:
        query = query.filter(LlmCall.user_id == user_id)
    if date_from is not None:
        query = query.filter(LlmCall.created_at >= to_naive_utc(date_from))
    if date_to is not None:
        query = query.filter(LlmCall.created_at <= to_naive_utc(date_to))
    return query


def filter_audit_events(
    db: Session,
    *,
    event_type: str | None,
    user_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> "Query[AuditEvent]":
    query = db.query(AuditEvent)
    if event_type is not None:
        query = query.filter(AuditEvent.event_type == event_type)
    if user_id is not None:
        query = query.filter(AuditEvent.user_id == user_id)
    if date_from is not None:
        query = query.filter(AuditEvent.created_at >= to_naive_utc(date_from))
    if date_to is not None:
        query = query.filter(AuditEvent.created_at <= to_naive_utc(date_to))
    return query


def user_names_by_id(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = db.query(User.id, User.name).filter(User.id.in_(user_ids)).all()
    return {row[0]: row[1] for row in rows}


def to_llm_call_summary(row: LlmCall, user_names: dict[uuid.UUID, str]) -> LlmCallSummary:
    return LlmCallSummary(
        id=row.id,
        request_id=row.request_id,
        user_id=row.user_id,
        user_name=user_names.get(row.user_id) if row.user_id else None,
        question=row.question,
        status=row.status,
        cache_hit=row.cache_hit,
        model_used=row.model_used,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        estimated_cost_usd=row.estimated_cost_usd,
        latency_ms_total=row.latency_ms_total,
        created_at=row.created_at,
    )


def to_llm_call_detail(row: LlmCall, user_names: dict[uuid.UUID, str]) -> LlmCallDetail:
    summary = to_llm_call_summary(row, user_names)
    return LlmCallDetail(
        **summary.model_dump(),
        conversation_id=row.conversation_id,
        retrieval_mode=row.retrieval_mode,
        retrieved_chunks=_zip_retrieved_chunks(row),
        system_prompt=row.system_prompt,
        messages_sent=row.messages_sent,
        model_response=row.model_response,
        tool_calls=row.tool_calls,
        provider=row.provider,
        model_requested=row.model_requested,
        fallback_used=row.fallback_used,
        usage_estimated=row.usage_estimated,
        error_type=row.error_type,
        error_message=row.error_message,
        prompt_version=row.prompt_version,
        latency_ms_retrieval=row.latency_ms_retrieval,
        latency_ms_first_token=row.latency_ms_first_token,
        latency_ms_generation=row.latency_ms_generation,
    )


def _zip_retrieved_chunks(row: LlmCall) -> list[RetrievedChunkScore] | None:
    if not row.retrieved_chunk_ids:
        return None
    scores = row.retrieved_scores or []
    return [
        RetrievedChunkScore(chunk_id=chunk_id, score=scores[i] if i < len(scores) else 0.0)
        for i, chunk_id in enumerate(row.retrieved_chunk_ids)
    ]


def to_audit_event_public(row: AuditEvent) -> AuditEventPublic:
    return AuditEventPublic(
        id=row.id,
        event_type=row.event_type,
        user_id=row.user_id,
        detail=row.details,
        created_at=row.created_at,
    )
