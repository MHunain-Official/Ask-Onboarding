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
from app.services.stream_events import SseEvent, citations_event, done_event


def cache_hit_response(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    cached: CachedAnswer,
    settings: Settings,
) -> Iterator[SseEvent]:
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
    if cached.citations:
        yield citations_event(cached.citations)
    yield done_event(str(message.id), LlmCallStatus.OK.value)
