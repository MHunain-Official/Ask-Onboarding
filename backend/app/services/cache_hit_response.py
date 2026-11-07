"""L1 exact answer cache hit (AGENTS.md §5.10): replay the saved answer,
still fully audited (`cache_hit=exact`), with no LLM call at all.
"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CacheHit, Conversation, LlmCallStatus, MessageRole, User
from app.services.audit_service import LlmCallRecord, record_llm_call
from app.services.cache_service import CachedAnswer
from app.services.conversation_service import persist_message
from app.services.stream_events import (
    SseEvent,
    citations_event,
    done_event,
    token_event,
    trace_event,
)


def cache_hit_response(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    cached: CachedAnswer,
    settings: Settings,
) -> Iterator[SseEvent]:
    yield trace_event(
        "cache",
        "done",
        "Saved answer",
        "Exact cache hit — skipped embedding, retrieval, and the LLM",
        {"cache_hit": "exact"},
    )
    yield trace_event("retrieve", "skipped", "Document search", "Not needed for a cached answer")
    yield trace_event("generate", "skipped", "LLM generation", "Replaying the saved answer")

    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        cached.answer_text,
        citations=cached.citations or None,
        ticket_offer=False,
    )
    record_llm_call(
        db,
        LlmCallRecord(
            request_id=request_id,
            status=LlmCallStatus.OK,
            prompt_version=settings.prompt_version,
            user_id=user.id,
            conversation_id=conversation.id,
            question=question,
            model=settings.llm_model,
            model_requested=settings.llm_model,
            model_used=settings.llm_model,
            cache_hit=CacheHit.EXACT,
        ),
    )
    # Replay the text so the UI can stream/show it like a normal answer.
    yield token_event(cached.answer_text)
    if cached.citations:
        yield citations_event(cached.citations)
    yield done_event(str(message.id), LlmCallStatus.OK.value)
