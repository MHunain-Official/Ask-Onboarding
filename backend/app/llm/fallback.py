"""Primary model first, `LLM_FALLBACK_MODEL` second (AGENTS.md §5.9).

`LlmClient.stream_chat` is lazy — nothing is sent over the network until
the first `next()` — so we pull exactly one event before deciding the
primary model "worked". If that first pull raises, nothing has reached
the user yet, so switching models is silent and safe. Any failure *after*
that first event is a mid-stream failure, not something this module
retries (the caller treats it as a partial answer, AGENTS.md §5.9 #9).
"""

from collections.abc import Iterator

import structlog

from app.llm.base import ChatMessage, LlmClient, StreamEvent, ToolDefinition

logger = structlog.get_logger(__name__)


def stream_with_fallback(
    client: LlmClient,
    messages: list[ChatMessage],
    tools: list[ToolDefinition],
    primary_model: str,
    fallback_model: str,
) -> tuple[Iterator[StreamEvent], str, bool]:
    """Return `(events, model_used, fallback_used)`.

    Raises only if both the primary and the fallback model fail before
    yielding anything — the caller's job at that point is a friendly error
    and degraded mode (AGENTS.md §5.9 #1).
    """
    try:
        events = _start(client, messages, tools, primary_model)
        return events, primary_model, False
    except Exception as exc:
        if fallback_model == primary_model:
            raise
        logger.warning(
            "llm.fallback_triggered",
            primary_model=primary_model,
            fallback_model=fallback_model,
            error=str(exc),
        )
        events = _start(client, messages, tools, fallback_model)  # a second failure propagates
        return events, fallback_model, True


def _start(
    client: LlmClient, messages: list[ChatMessage], tools: list[ToolDefinition], model: str
) -> Iterator[StreamEvent]:
    """Force the connection to open (pull one event) before returning, so
    the caller above can tell "never connected" apart from "connected,
    then nothing to say" without silently retrying either case twice."""
    events = client.stream_chat(messages, tools, model)
    try:
        first_event = next(events)
    except StopIteration:
        return iter(())
    return _prepend(first_event, events)


def _prepend(first: StreamEvent, rest: Iterator[StreamEvent]) -> Iterator[StreamEvent]:
    yield first
    yield from rest
