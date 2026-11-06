"""Controllable fake LLM for tests (AGENTS.md §3.3): deterministic, no
network, and it records every call it received so a test can assert on
exactly what prompt was sent — not just what came back (the canary-leakage
suite in Phase 7 depends on inspecting the recorded messages).
"""

from collections.abc import Iterator
from dataclasses import dataclass

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


@dataclass
class ScriptedResponse:
    """One queued answer. Set `raise_error` to simulate a provider failure;
    set `raise_after_tokens` too to make the failure happen mid-stream
    (after that many words were already yielded) instead of before the
    first token.
    """

    text: str = ""
    tool_call: ToolCall | None = None
    raise_error: Exception | None = None
    raise_after_tokens: int | None = None
    input_tokens: int | None = 10
    output_tokens: int | None = 10
    usage_estimated: bool = False


@dataclass
class FakeLlmCall:
    """One recorded `stream_chat` invocation."""

    messages: list[ChatMessage]
    tools: list[ToolDefinition]
    model: str


class FakeLlm:
    """Drop-in `LlmClient`. Queue responses with `queue()`; the default
    (empty queue) answer is a plain refusal-free "I don't know." reply so
    a forgotten queue fails a test loudly rather than hanging."""

    def __init__(self, responses: list[ScriptedResponse] | None = None) -> None:
        self._responses: list[ScriptedResponse] = list(responses or [])
        self.calls: list[FakeLlmCall] = []

    def queue(self, response: ScriptedResponse) -> None:
        self._responses.append(response)

    def stream_chat(
        self, messages: list[ChatMessage], tools: list[ToolDefinition], model: str
    ) -> Iterator[StreamEvent]:
        self.calls.append(FakeLlmCall(messages=list(messages), tools=list(tools), model=model))
        default = ScriptedResponse(text="I don't know.")
        response = self._responses.pop(0) if self._responses else default
        return _play(response)


def _play(response: ScriptedResponse) -> Iterator[StreamEvent]:
    if response.raise_error is not None and response.raise_after_tokens is None:
        raise response.raise_error

    words = response.text.split(" ") if response.text else []
    for index, word in enumerate(words):
        if response.raise_after_tokens is not None and index >= response.raise_after_tokens:
            assert response.raise_error is not None
            raise response.raise_error
        yield StreamToken(text=word if index == 0 else f" {word}")

    if response.tool_call is not None:
        yield StreamToolCall(tool_call=response.tool_call)

    finish_reason = "tool_calls" if response.tool_call is not None else "stop"
    usage = StreamUsage(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated=response.usage_estimated,
    )
    yield StreamDone(finish_reason=finish_reason, usage=usage)
