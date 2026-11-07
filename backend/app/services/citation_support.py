"""Small, pure helpers shared by the answer-generation and fallback-
response paths (AGENTS.md §5.4/§5.11/§5.12 #7): building citation/passage
SSE items, filling in missing token usage, and a sane default ticket title.
"""

from app.ingestion.chunker import count_tokens
from app.llm.base import ChatMessage, StreamUsage, ToolCall
from app.llm.prompts import SourceForPrompt
from app.retrieval.hybrid import RetrievedChunk

_SNIPPET_CHARS = 320
_MAX_TITLE_CHARS = 80


def citation_items(numbers: set[int], sources: list[SourceForPrompt]) -> list[dict[str, object]]:
    by_number = {source.n: source for source in sources}
    items: list[dict[str, object]] = []
    for number in sorted(numbers):
        source = by_number.get(number)
        if source is None:
            continue
        items.append(
            {
                "n": source.n,
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "filename": source.filename,
                "page": source.page,
                "heading": source.heading,
                # Prefer a mid-chunk window around the most distinctive sentence
                # start so the drawer highlight matches what the answer cited.
                "snippet": _best_snippet(source.text, _SNIPPET_CHARS),
                "char_start": source.char_start,
                "char_end": source.char_end,
            }
        )
    return items


def passage_items(chunks: list[RetrievedChunk]) -> list[dict[str, object]]:
    """Degraded-mode "Relevant passages": every retrieved chunk, numbered
    in rank order. No citation validation is needed because nothing was
    generated for the model to cite incorrectly."""
    return [
        {
            "n": index + 1,
            "chunk_id": str(chunk.chunk_id),
            "document_id": str(chunk.document_id),
            "filename": chunk.filename,
            "page": chunk.page,
            "heading": chunk.heading,
            "snippet": _best_snippet(chunk.text, _SNIPPET_CHARS),
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }
        for index, chunk in enumerate(chunks)
    ]


def _best_snippet(text: str, max_chars: int) -> str:
    """Pick a contiguous window that starts at a sentence boundary when possible."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    # Prefer starting after the first sentence if the chunk has a heading prepend.
    for separator in (". ", "\n", "? ", "! "):
        index = cleaned.find(separator)
        if 0 < index < max_chars // 2:
            start = index + len(separator)
            return cleaned[start : start + max_chars].rstrip() + "…"
    return cleaned[:max_chars].rstrip() + "…"


def default_ticket_title(question: str) -> str:
    stripped = " ".join(question.strip().split())
    if len(stripped) <= _MAX_TITLE_CHARS:
        return stripped
    return stripped[: _MAX_TITLE_CHARS - 3] + "..."


def tool_call_title(tool_call: ToolCall | None) -> str | None:
    if tool_call is None:
        return None
    title = tool_call.arguments.get("suggested_title")
    return str(title)[:200] if title else None


def resolve_usage(
    usage: StreamUsage | None, messages: list[ChatMessage], answer_text: str
) -> tuple[int, int, bool]:
    """Fall back to tiktoken estimates when the provider didn't report
    usage (§5.12 #7): never crash, never write a misleading zero."""
    if usage is not None and usage.input_tokens is not None and usage.output_tokens is not None:
        return usage.input_tokens, usage.output_tokens, usage.estimated
    input_tokens = sum(count_tokens(message.content) for message in messages)
    output_tokens = count_tokens(answer_text)
    return input_tokens, output_tokens, True
