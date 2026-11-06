"""Chat client for any OpenAI-compatible endpoint (OpenRouter in prod,
AGENTS.md §1: "one client for many models").

Retries (bounded, max 3, backoff) only cover *establishing* the stream —
once the provider has started sending tokens we stop retrying silently,
because the caller may already have shown some of them to the user
(§5.9: a mid-stream failure is a partial answer, not something to replay).
"""

import contextlib
import json
import time
from collections.abc import Iterator
from typing import Any, cast

import structlog
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from app.config import Settings
from app.llm.base import (
    ChatMessage,
    StreamDone,
    StreamEvent,
    StreamToken,
    StreamToolCall,
    StreamUsage,
    ToolCall,
    ToolDefinition,
)

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, APIStatusError)


class OpenAiCompatibleClient:
    """Streams chat completions via the `openai` SDK against `LLM_BASE_URL`."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        model: str,
    ) -> Iterator[StreamEvent]:
        stream = self._create_stream_with_retry(messages, tools, model)
        return _consume_stream(stream)

    def _create_stream_with_retry(
        self, messages: list[ChatMessage], tools: list[ToolDefinition], model: str
    ) -> object:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._client.chat.completions.create(
                    model=model,
                    # `cast(Any, ...)`: the SDK's message/tool params are a long union of
                    # TypedDicts; plain dicts are valid at runtime but mypy can't match the
                    # overload, so we cast rather than duplicate the SDK's own types here.
                    messages=cast(Any, [_to_openai_message(m) for m in messages]),
                    tools=cast(Any, [_to_openai_tool(t) for t in tools] or None),
                    temperature=0,
                    max_tokens=self._settings.llm_max_output_tokens,
                    stream=True,
                )
            except RETRYABLE_ERRORS as exc:
                last_error = exc
                logger.warning("llm.retry", attempt=attempt, model=model, error=str(exc))
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)  # 2s, 4s backoff
        assert last_error is not None  # loop always sets this before exhausting retries
        raise last_error


def _to_openai_message(message: ChatMessage) -> dict[str, str]:
    return {"role": message.role, "content": message.content}


def _to_openai_tool(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _consume_stream(stream: object) -> Iterator[StreamEvent]:
    """Turn provider chunk deltas into `StreamEvent`s. Tool-call arguments
    arrive as incremental JSON fragments across many chunks, so they are
    accumulated by index and only emitted as one complete `StreamToolCall`
    once the stream reports `finish_reason`.
    """
    tool_call_parts: dict[int, dict[str, str]] = {}
    finish_reason = "stop"
    usage = StreamUsage(input_tokens=None, output_tokens=None, estimated=True)

    try:
        for chunk in stream:  # type: ignore[attr-defined]
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = choice.delta
            if delta.content:
                yield StreamToken(text=delta.content)
            for tool_delta in delta.tool_calls or []:
                _accumulate_tool_call(tool_call_parts, tool_delta)
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            usage = _usage_from_chunk(chunk) or usage
    finally:
        _close_quietly(stream)

    for call in _finished_tool_calls(tool_call_parts):
        yield StreamToolCall(tool_call=call)
    yield StreamDone(finish_reason=finish_reason, usage=usage)


def _accumulate_tool_call(parts: dict[int, dict[str, str]], tool_delta: object) -> None:
    index = tool_delta.index  # type: ignore[attr-defined]
    entry = parts.setdefault(index, {"id": "", "name": "", "arguments": ""})
    if tool_delta.id:  # type: ignore[attr-defined]
        entry["id"] = tool_delta.id  # type: ignore[attr-defined]
    function = tool_delta.function  # type: ignore[attr-defined]
    if function is not None:
        if function.name:
            entry["name"] = function.name
        if function.arguments:
            entry["arguments"] += function.arguments


def _finished_tool_calls(parts: dict[int, dict[str, str]]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for entry in parts.values():
        try:
            arguments = json.loads(entry["arguments"]) if entry["arguments"] else {}
        except json.JSONDecodeError:
            arguments = {}
        calls.append(ToolCall(id=entry["id"], name=entry["name"], arguments=arguments))
    return calls


def _usage_from_chunk(chunk: object) -> StreamUsage | None:
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None
    return StreamUsage(
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        estimated=False,
    )


def _close_quietly(stream: object) -> None:
    close = getattr(stream, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):  # best-effort cleanup, never raise from here
            close()
