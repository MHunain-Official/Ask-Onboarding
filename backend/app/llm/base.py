"""LLM client interface (AGENTS.md §1: one interface, many providers behind it).

Every caller depends on `LlmClient`, never on a concrete provider SDK —
swapping `OpenAiCompatibleClient` for `FakeLlm` in tests needs no mocking
library, exactly like `Embedder`/`FakeEmbedder` in `app/embeddings/`.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """One message in the conversation sent to the model."""

    role: Role
    content: str


@dataclass(frozen=True)
class ToolDefinition:
    """One function-calling tool the model may invoke (AGENTS.md §3.2 rule 3:
    the app ships exactly one, `offer_help_desk_ticket`)."""

    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class ToolCall:
    """One invocation of a tool, as reconstructed from the model's stream."""

    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class StreamToken:
    """One piece of generated answer text."""

    text: str


@dataclass(frozen=True)
class StreamToolCall:
    """The model finished emitting one complete tool call."""

    tool_call: ToolCall


@dataclass(frozen=True)
class StreamUsage:
    """Token accounting for one generation (§5.12 #7: usage may be missing)."""

    input_tokens: int | None
    output_tokens: int | None
    estimated: bool


@dataclass(frozen=True)
class StreamDone:
    """Terminal event: the model has finished responding."""

    finish_reason: str
    usage: StreamUsage


StreamEvent = StreamToken | StreamToolCall | StreamDone


class LlmClient(Protocol):
    """Turns a conversation into a stream of tokens/tool calls/usage.

    Implementations must raise on connection failure *before* yielding
    anything if the call never reached the provider (so `fallback.py` can
    silently retry on a different model), and may raise mid-stream if the
    connection drops after some tokens were already yielded (the caller
    treats that as a partial answer, never a silent retry).
    """

    def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        model: str,
    ) -> Iterator[StreamEvent]:
        """Stream one assistant turn for `messages`, offering `tools`."""
        ...
