"""Streams one real LLM generation, validates it, persists it, and (if
eligible) caches it (AGENTS.md §5.4, §5.9, §5.11). The "nothing special
happened" path through a RAG chat endpoint — everything else in
`answer_service.py` exists to avoid reaching this function.
"""

import time
from collections.abc import Callable, Generator, Iterator

from sqlalchemy.orm import Session

from app.config import Settings
from app.embeddings.base import Embedder
from app.llm.base import (
    ChatMessage,
    LlmClient,
    StreamDone,
    StreamEvent,
    StreamToken,
    StreamToolCall,
    StreamUsage,
    ToolCall,
)
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.fallback import stream_with_fallback
from app.llm.prompts import SourceForPrompt
from app.llm.tools import ALL_TOOLS
from app.models import Conversation, User
from app.retrieval.hybrid import RetrievalResult
from app.services.answer_persistence import FinalAnswer, finish_generation
from app.services.fallback_responses import provider_unavailable_response
from app.services.stream_events import SseEvent, token_event, trace_event

_ConsumeResult = tuple[
    list[str], ToolCall | None, StreamUsage | None, int | None, int, bool, Exception | None
]


def generate_and_stream_answer(
    *,
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    sources: list[SourceForPrompt],
    retrieval_result: RetrievalResult,
    messages: list[ChatMessage],
    llm_client: LlmClient,
    breaker: CircuitBreaker,
    settings: Settings,
    scope: str,
    cacheable: bool,
    embedder: Embedder,
    retrieval_ms: int,
    cancel_check: Callable[[], bool] | None = None,
) -> Generator[SseEvent, None, FinalAnswer | None]:
    if breaker.is_open():
        yield from provider_unavailable_response(
            db,
            conversation,
            user,
            request_id,
            question,
            retrieval_result,
            retrieval_ms,
            settings,
            "circuit_open",
            None,
        )
        return None

    yield trace_event(
        "generate",
        "running",
        "Generating answer",
        "Primary model · tool: offer_help_desk_ticket",
    )
    try:
        events, model_used, fallback_used = stream_with_fallback(
            llm_client, messages, ALL_TOOLS, settings.llm_model, settings.llm_fallback_model
        )
    except Exception as exc:
        breaker.record_failure()
        yield trace_event("generate", "failed", "Generating answer", "Provider unavailable")
        yield from provider_unavailable_response(
            db,
            conversation,
            user,
            request_id,
            question,
            retrieval_result,
            retrieval_ms,
            settings,
            "provider_down",
            exc,
        )
        return None

    (
        text_parts,
        tool_call,
        usage,
        first_token_ms,
        generation_ms,
        partial,
        stream_error,
    ) = yield from _stream_tokens(events, cancel_check)
    if stream_error is None:
        breaker.record_success()
    else:
        breaker.record_failure()

    answer_text = "".join(text_parts)
    if stream_error is not None and not text_parts:
        yield trace_event("generate", "failed", "Generating answer", "Stream failed before any tokens")
        yield from provider_unavailable_response(
            db,
            conversation,
            user,
            request_id,
            question,
            retrieval_result,
            retrieval_ms,
            settings,
            "stream_error",
            stream_error,
        )
        return None

    model_note = model_used or settings.llm_model
    if fallback_used:
        model_note = f"{model_note} (fallback)"
    yield trace_event(
        "generate",
        "done",
        "Generating answer",
        f"{model_note} · {generation_ms} ms"
        + (f" · first token {first_token_ms} ms" if first_token_ms is not None else ""),
    )

    final_answer = yield from finish_generation(
        db=db,
        conversation=conversation,
        user=user,
        request_id=request_id,
        question=question,
        sources=sources,
        retrieval_result=retrieval_result,
        messages=messages,
        settings=settings,
        scope=scope,
        cacheable=cacheable,
        embedder=embedder,
        retrieval_ms=retrieval_ms,
        answer_text=answer_text,
        tool_call=tool_call,
        usage=usage,
        first_token_ms=first_token_ms,
        generation_ms=generation_ms,
        partial=partial,
        model_used=model_used,
        fallback_used=fallback_used,
    )
    return final_answer


def _stream_tokens(
    events: Iterator[StreamEvent], cancel_check: Callable[[], bool] | None
) -> Generator[SseEvent, None, _ConsumeResult]:
    """Yields `token_event`s live as they arrive. The generator's return
    value (a `_ConsumeResult`, retrieved by the caller via `yield from`)
    carries the aggregated text/tool-call/usage once the stream ends.
    """
    text_parts: list[str] = []
    tool_call: ToolCall | None = None
    usage: StreamUsage | None = None
    first_token_ms: int | None = None
    partial = False
    stream_error: Exception | None = None
    start = time.monotonic()
    try:
        for event in events:
            if cancel_check is not None and cancel_check():
                events.close()  # type: ignore[attr-defined]
                partial = True
                break
            if isinstance(event, StreamToken):
                if first_token_ms is None:
                    first_token_ms = int((time.monotonic() - start) * 1000)
                text_parts.append(event.text)
                yield token_event(event.text)
            elif isinstance(event, StreamToolCall):
                tool_call = event.tool_call
            elif isinstance(event, StreamDone):
                usage = event.usage
    except Exception as exc:  # noqa: BLE001 - mid-stream failure, handled by the caller
        stream_error = exc
        partial = True
    generation_ms = int((time.monotonic() - start) * 1000)
    return text_parts, tool_call, usage, first_token_ms, generation_ms, partial, stream_error
