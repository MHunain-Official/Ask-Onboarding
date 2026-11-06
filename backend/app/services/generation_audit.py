"""Small helpers for `answer_persistence.finish_generation`: grounding-issue
audit events, the `llm_calls` row for a real generation, the final
`LlmCallStatus`, and the text shown when the model produced nothing
usable. Split out purely to keep `answer_persistence.py` under 200 lines.
"""

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.base import ChatMessage, ToolCall
from app.llm.grounding_check import GroundingResult
from app.models import CacheHit, Conversation, LlmCallStatus, User
from app.retrieval.hybrid import RetrievalResult
from app.services.audit_service import LlmCallRecord, record_audit_event, record_llm_call


def audit_grounding_issues(
    db: Session, request_id: str, user: User, grounding: GroundingResult
) -> None:
    if grounding.removed_citation_numbers:
        record_audit_event(
            db,
            event_type="invalid_citation_dropped",
            request_id=request_id,
            user_id=user.id,
            details={"removed": sorted(grounding.removed_citation_numbers)},
        )
    if grounding.ungrounded_facts:
        record_audit_event(
            db,
            event_type="ungrounded_fact",
            request_id=request_id,
            user_id=user.id,
            details={"facts": grounding.ungrounded_facts[:20]},
        )


def record_generation_call(
    db: Session,
    request_id: str,
    user: User,
    conversation: Conversation,
    question: str,
    retrieval_result: RetrievalResult,
    messages: list[ChatMessage],
    settings: Settings,
    *,
    status: LlmCallStatus,
    answer_text: str,
    tool_call: ToolCall | None,
    model_used: str,
    fallback_used: bool,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    usage_estimated: bool,
    retrieval_ms: int,
    first_token_ms: int | None,
    generation_ms: int,
) -> None:
    record_llm_call(
        db,
        LlmCallRecord(
            request_id=request_id,
            status=status,
            prompt_version=settings.prompt_version,
            user_id=user.id,
            conversation_id=conversation.id,
            question=question,
            retrieval_mode="hybrid" if settings.hybrid_enabled else "vector",
            retrieved_chunk_ids=[str(c.chunk_id) for c in retrieval_result.chunks],
            retrieved_scores=[c.score for c in retrieval_result.chunks],
            system_prompt=messages[0].content,
            messages_sent=[{"role": m.role, "content": m.content} for m in messages],
            model_response=answer_text,
            tool_calls=[{"name": tool_call.name, "arguments": tool_call.arguments}]
            if tool_call
            else [],
            model=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            latency_ms_retrieval=retrieval_ms,
            latency_ms_first_token=first_token_ms,
            latency_ms_generation=generation_ms,
            latency_ms_total=retrieval_ms + generation_ms,
            cache_hit=CacheHit.NONE,
            provider="openai_compatible",
            model_requested=settings.llm_model,
            model_used=model_used,
            fallback_used=fallback_used,
            usage_estimated=usage_estimated,
        ),
    )


def resolve_status(partial: bool, is_refusal: bool, grounding_status: str) -> LlmCallStatus:
    if partial:
        return LlmCallStatus.PARTIAL
    if is_refusal:
        return LlmCallStatus.REFUSED
    if grounding_status == "ungrounded":
        return LlmCallStatus.UNGROUNDED
    return LlmCallStatus.OK


def fallback_display_text(status: LlmCallStatus) -> str:
    """What to show when grounding stripped everything out of the answer."""
    if status == LlmCallStatus.PARTIAL:
        return "The answer was interrupted. Please retry."
    return "I could not verify this against the documents."
