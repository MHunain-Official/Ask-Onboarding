"""Inserts for `llm_calls` and `audit_events` (AGENTS.md §3.6). One place,
so every caller logs the full audit trail consistently — the owner's
"full audit logs" requirement is only as good as this being used
everywhere an answer is produced or a sensitive action happens.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import AuditEvent, CacheHit, LlmCall, LlmCallStatus

# Never truncate silently to zero: cap each free-text field at 100 KB,
# but a value under the cap is returned untouched (AGENTS.md §3.6).
_MAX_FIELD_BYTES = 100_000


@dataclass
class LlmCallRecord:
    """Every column on `llm_calls` (§3.6/§4) except the auto id/created_at."""

    request_id: str
    status: LlmCallStatus
    prompt_version: str
    user_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    question: str = ""
    retrieval_mode: str | None = None
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    retrieved_scores: list[float] = field(default_factory=list)
    system_prompt: str | None = None
    messages_sent: list[dict[str, object]] = field(default_factory=list)
    model_response: str | None = None
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms_total: int | None = None
    latency_ms_retrieval: int | None = None
    latency_ms_first_token: int | None = None
    latency_ms_generation: int | None = None
    cache_hit: CacheHit = CacheHit.NONE
    provider: str | None = None
    model_requested: str | None = None
    model_used: str | None = None
    fallback_used: bool = False
    usage_estimated: bool = False
    error_type: str | None = None
    error_message: str | None = None


def record_llm_call(db: Session, record: LlmCallRecord) -> LlmCall:
    row = LlmCall(
        request_id=record.request_id,
        user_id=record.user_id,
        conversation_id=record.conversation_id,
        question=_cap(record.question),
        retrieval_mode=record.retrieval_mode,
        retrieved_chunk_ids=record.retrieved_chunk_ids,
        retrieved_scores=record.retrieved_scores,
        system_prompt=_cap(record.system_prompt),
        messages_sent=record.messages_sent,
        model_response=_cap(record.model_response),
        tool_calls=record.tool_calls,
        model=record.model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        estimated_cost_usd=record.estimated_cost_usd,
        latency_ms_total=record.latency_ms_total,
        latency_ms_retrieval=record.latency_ms_retrieval,
        latency_ms_first_token=record.latency_ms_first_token,
        latency_ms_generation=record.latency_ms_generation,
        status=record.status,
        cache_hit=record.cache_hit,
        provider=record.provider,
        model_requested=record.model_requested,
        model_used=record.model_used,
        fallback_used=record.fallback_used,
        usage_estimated=record.usage_estimated,
        error_type=record.error_type,
        error_message=_cap(record.error_message),
        prompt_version=record.prompt_version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    request_id: str | None = None,
    user_id: uuid.UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditEvent(request_id=request_id, user_id=user_id, event_type=event_type, details=details)
    )
    db.commit()


def _cap(value: str | None) -> str | None:
    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= _MAX_FIELD_BYTES:
        return value
    return encoded[:_MAX_FIELD_BYTES].decode("utf-8", errors="ignore")
