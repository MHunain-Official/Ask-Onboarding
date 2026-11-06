"""Canned SSE responses that never call the LLM (AGENTS.md §5.3 gate #1,
§5.9, §5.10 L7): the deterministic no-answer gate, the degraded "Relevant
passages" mode (budget cap or provider outage), each fully audited.
"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CacheHit, Conversation, LlmCallStatus, MessageRole, User
from app.retrieval.hybrid import RetrievalResult
from app.services.audit_service import LlmCallRecord, record_audit_event, record_llm_call
from app.services.citation_support import default_ticket_title, passage_items
from app.services.conversation_service import persist_message
from app.services.stream_events import citations_event, done_event, error_event, ticket_offer_event

NO_ANSWER_TEXT = (
    "I couldn't find anything about that in our documents. Would you like me to "
    "open a help-desk ticket so a person can help?"
)
BUDGET_DEGRADED_TEXT = (
    "We're at today's usage limit, so here are the most relevant passages from the "
    "documents instead of a generated answer. Please try again later."
)
PROVIDER_UNAVAILABLE_TEXT = (
    "The AI service is unavailable right now. Your question was saved — please retry in a moment."
)


def no_answer_response(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    retrieval_result: RetrievalResult,
    retrieval_ms: int,
    settings: Settings,
) -> Iterator[dict[str, str]]:
    """Gate #1 (§5.3): deterministic, the LLM is never called."""
    passages = passage_items(retrieval_result.chunks)
    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        NO_ANSWER_TEXT,
        citations=passages or None,
        ticket_offer=True,
    )
    _record_call(
        db,
        request_id,
        user,
        conversation,
        question,
        retrieval_result,
        retrieval_ms,
        settings,
        status=LlmCallStatus.NO_ANSWER,
    )
    if passages:
        yield citations_event(passages)
    yield ticket_offer_event(default_ticket_title(question), question)
    yield done_event(str(message.id), LlmCallStatus.NO_ANSWER.value)


def budget_degraded_response(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    retrieval_result: RetrievalResult,
    retrieval_ms: int,
    settings: Settings,
    reason: str,
) -> Iterator[dict[str, str]]:
    record_audit_event(
        db,
        event_type="budget_exceeded",
        request_id=request_id,
        user_id=user.id,
        details={"reason": reason},
    )
    passages = passage_items(retrieval_result.chunks)
    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        BUDGET_DEGRADED_TEXT,
        citations=passages or None,
        ticket_offer=False,
    )
    _record_call(
        db,
        request_id,
        user,
        conversation,
        question,
        retrieval_result,
        retrieval_ms,
        settings,
        status=LlmCallStatus.NO_ANSWER,
        error_type="budget_exceeded",
        error_message=reason,
    )
    if passages:
        yield citations_event(passages)
    yield done_event(str(message.id), "ok")


def provider_unavailable_response(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    retrieval_result: RetrievalResult,
    retrieval_ms: int,
    settings: Settings,
    reason: str,
    error: Exception | None,
) -> Iterator[dict[str, str]]:
    record_audit_event(
        db,
        event_type="llm_provider_unavailable",
        request_id=request_id,
        user_id=user.id,
        details={"reason": reason},
    )
    passages = passage_items(retrieval_result.chunks)
    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        PROVIDER_UNAVAILABLE_TEXT,
        citations=passages or None,
        ticket_offer=False,
    )
    error_message = str(error) if error else reason
    _record_call(
        db,
        request_id,
        user,
        conversation,
        question,
        retrieval_result,
        retrieval_ms,
        settings,
        status=LlmCallStatus.ERROR,
        error_type=reason,
        error_message=error_message,
    )
    yield error_event("llm_unavailable", PROVIDER_UNAVAILABLE_TEXT, request_id)
    if passages:
        yield citations_event(passages)
    yield done_event(str(message.id), LlmCallStatus.ERROR.value)


def _record_call(
    db: Session,
    request_id: str,
    user: User,
    conversation: Conversation,
    question: str,
    retrieval_result: RetrievalResult,
    retrieval_ms: int,
    settings: Settings,
    *,
    status: LlmCallStatus,
    error_type: str | None = None,
    error_message: str | None = None,
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
            latency_ms_retrieval=retrieval_ms,
            latency_ms_total=retrieval_ms,
            cache_hit=CacheHit.NONE,
            model_requested=settings.llm_model,
            error_type=error_type,
            error_message=error_message,
        ),
    )
