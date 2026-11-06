"""Grounding validation, persistence, and (if eligible) caching for one
completed LLM generation (AGENTS.md §5.4, §5.10, §5.11). Split out of
`answer_generation.py` purely to keep that file under 200 lines.
"""

from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.embeddings.base import Embedder
from app.llm.base import ChatMessage, StreamUsage, ToolCall
from app.llm.grounding_check import check_grounding
from app.llm.prompts import SourceForPrompt
from app.models import Conversation, LlmCallStatus, MessageRole, User
from app.retrieval.hybrid import RetrievalResult
from app.services.budget_service import estimate_cost_usd, record_usage
from app.services.cache_service import build_source_doc_refs, store_answer
from app.services.citation_support import (
    citation_items,
    default_ticket_title,
    resolve_usage,
    tool_call_title,
)
from app.services.conversation_service import persist_message
from app.services.generation_audit import (
    audit_grounding_issues,
    fallback_display_text,
    record_generation_call,
    resolve_status,
)
from app.services.stream_events import SseEvent, citations_event, done_event, ticket_offer_event


@dataclass(frozen=True)
class FinalAnswer:
    """What a single-flight follower replays once the leader is done."""

    text: str
    citations: list[dict[str, object]]
    ticket_offer: bool
    suggested_title: str | None
    status: LlmCallStatus


def finish_generation(
    *,
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    sources: list[SourceForPrompt],
    retrieval_result: RetrievalResult,
    messages: list[ChatMessage],
    settings: Settings,
    scope: str,
    cacheable: bool,
    embedder: Embedder,
    retrieval_ms: int,
    answer_text: str,
    tool_call: ToolCall | None,
    usage: StreamUsage | None,
    first_token_ms: int | None,
    generation_ms: int,
    partial: bool,
    model_used: str,
    fallback_used: bool,
) -> Generator[SseEvent, None, FinalAnswer]:
    is_refusal = tool_call is not None
    grounding = check_grounding(answer_text, sources, is_refusal=is_refusal)
    audit_grounding_issues(db, request_id, user, grounding)

    status = resolve_status(partial, is_refusal, grounding.status)
    ticket_offer = is_refusal or status == LlmCallStatus.UNGROUNDED
    suggested_title = tool_call_title(tool_call) or (
        default_ticket_title(question) if ticket_offer else None
    )

    items = citation_items(grounding.valid_citation_numbers, sources)
    display_text = grounding.cleaned_text.strip() or fallback_display_text(status)

    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        display_text,
        citations=items or None,
        ticket_offer=ticket_offer,
    )

    input_tokens, output_tokens, usage_estimated = resolve_usage(usage, messages, answer_text)
    cost = estimate_cost_usd(
        input_tokens,
        output_tokens,
        settings.llm_price_input_per_mtok,
        settings.llm_price_output_per_mtok,
    )
    record_usage(db, user.id, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost)
    record_generation_call(
        db,
        request_id,
        user,
        conversation,
        question,
        retrieval_result,
        messages,
        settings,
        status=status,
        answer_text=answer_text,
        tool_call=tool_call,
        model_used=model_used,
        fallback_used=fallback_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        usage_estimated=usage_estimated,
        retrieval_ms=retrieval_ms,
        first_token_ms=first_token_ms,
        generation_ms=generation_ms,
    )

    if items:
        yield citations_event(items)
    if ticket_offer and suggested_title:
        yield ticket_offer_event(suggested_title, question)
    yield done_event(str(message.id), status.value)

    if cacheable and status == LlmCallStatus.OK and not is_refusal:
        document_ids = {source.document_id for source in sources}
        store_answer(
            db,
            question=question,
            scope=scope,
            prompt_version=settings.prompt_version,
            model=settings.llm_model,
            answer_text=display_text,
            citations=items,
            source_docs=build_source_doc_refs(db, document_ids),
            question_embedding=embedder.embed_query(question),
            ttl_hours=settings.cache_ttl_hours,
        )

    return FinalAnswer(
        text=display_text,
        citations=items,
        ticket_offer=ticket_offer,
        suggested_title=suggested_title,
        status=status,
    )
