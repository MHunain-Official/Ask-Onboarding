"""Split parsed document text into overlapping, embeddable chunks (§5.2).

Markdown sectioning (cutting at headings) lives in `markdown_sections.py`;
this module does the other half: within one section, recursively split on
paragraph -> sentence -> word boundaries (`_split_into_units`), then
greedily pack those pieces into chunks near `target_tokens`, carrying a
trailing overlap into the next chunk.

Token counts use tiktoken's `cl100k_base` encoding, purely to size chunks
consistently — not tied to any particular embedding or chat model.
"""

import re
from dataclasses import dataclass

import tiktoken

from app.ingestion.markdown_sections import Section, split_into_sections

_ENCODING = tiktoken.get_encoding("cl100k_base")

# Split "after" each match, attaching the separator to the piece before it,
# so concatenating all pieces reproduces the exact original text.
_PARAGRAPH_PATTERN = re.compile(r"\n\s*\n+")
_SENTENCE_PATTERN = re.compile(r"[.!?]+[\"')\]]*\s+")
_WORD_PATTERN = re.compile(r"\s+")

# A heading prefix should never be allowed to starve the body of a chunk
# down to nothing; this is the floor on tokens left for actual content.
_MIN_BODY_TOKENS = 50


@dataclass
class Chunk:
    """One packed, embeddable piece of a document.

    `text` is what gets embedded (heading path prepended, if any).
    `char_start`/`char_end` index into the *original parsed document text*
    and cover the body only — the invariant the tests check is
    `parsed_text[char_start:char_end] == text_without_the_heading_prefix`.
    """

    text: str
    char_start: int
    char_end: int
    heading: str | None
    token_count: int


def count_tokens(text: str) -> int:
    """Shared, single place both the chunker and pipeline use to count tokens."""
    return len(_ENCODING.encode(text))


def split_text_into_chunks(
    text: str,
    *,
    target_tokens: int,
    overlap_tokens: int,
    is_markdown: bool = False,
) -> list[Chunk]:
    """Split `text` into chunks of roughly `target_tokens` with
    `overlap_tokens` of trailing context repeated at the start of the next
    chunk. Callers pass `target_tokens`/`overlap_tokens` from `Settings` —
    this module has no config of its own (AGENTS.md §3.1: config in one place).
    """
    if not text.strip():
        return []

    sections = split_into_sections(text, is_markdown=is_markdown)
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(_chunk_section(text, section, target_tokens, overlap_tokens))
    return chunks


def _chunk_section(
    full_text: str, section: Section, target_tokens: int, overlap_tokens: int
) -> list[Chunk]:
    heading_prefix = section.heading or ""
    heading_tokens = count_tokens(heading_prefix) if heading_prefix else 0
    body_target = max(target_tokens - heading_tokens, _MIN_BODY_TOKENS)

    section_text = full_text[section.char_start : section.char_end]
    relative_units = _split_into_units(section_text, body_target)
    units = [(s + section.char_start, e + section.char_start) for s, e in relative_units]
    # Drop whitespace-only pieces (e.g. the blank line right after a heading)
    # so no chunk is ever built from nothing but separators.
    units = [u for u in units if full_text[u[0] : u[1]].strip()]
    if not units:
        return []

    unit_token_counts = [count_tokens(full_text[s:e]) for s, e in units]

    chunks: list[Chunk] = []
    start_idx = 0
    unit_count = len(units)
    while start_idx < unit_count:
        end_idx = _pack_forward(unit_token_counts, start_idx, body_target)

        chunk_char_start = units[start_idx][0]
        chunk_char_end = units[end_idx][1]
        body_text = full_text[chunk_char_start:chunk_char_end]
        chunk_text = f"{heading_prefix}\n\n{body_text}" if heading_prefix else body_text
        chunks.append(
            Chunk(
                text=chunk_text,
                char_start=chunk_char_start,
                char_end=chunk_char_end,
                heading=section.heading,
                token_count=count_tokens(chunk_text),
            )
        )

        if end_idx == unit_count - 1:
            break
        start_idx = _next_start_index(unit_token_counts, start_idx, end_idx, overlap_tokens)

    return chunks


def _pack_forward(unit_token_counts: list[int], start_idx: int, body_target: int) -> int:
    """Greedily include units starting at `start_idx` while staying near
    `body_target` tokens. Always includes at least one unit, even an
    oversized one, so a single huge word/sentence still becomes a chunk
    instead of looping forever."""
    total = 0
    end_idx = start_idx
    n = len(unit_token_counts)
    while end_idx < n:
        candidate_total = total + unit_token_counts[end_idx]
        if candidate_total > body_target and end_idx > start_idx:
            break
        total = candidate_total
        end_idx += 1
        if total >= body_target:
            break
    return end_idx - 1


def _next_start_index(
    unit_token_counts: list[int], start_idx: int, end_idx: int, overlap_tokens: int
) -> int:
    """Pick the start of the next chunk so it repeats up to `overlap_tokens`
    of trailing content from the chunk that just ended, guaranteeing forward
    progress (the loop in `_chunk_section` always terminates)."""
    if overlap_tokens <= 0:
        return end_idx + 1

    overlap_total = 0
    overlap_start_idx = end_idx
    while overlap_start_idx > start_idx:
        candidate = overlap_total + unit_token_counts[overlap_start_idx]
        if candidate > overlap_tokens:
            break
        overlap_total = candidate
        overlap_start_idx -= 1
    overlap_start_idx += 1

    if overlap_start_idx <= start_idx:
        return end_idx + 1
    return overlap_start_idx


def _split_into_units(text: str, max_tokens: int) -> list[tuple[int, int]]:
    """Recursively split `text` into (start, end) pieces at or under
    `max_tokens`, preferring paragraph, then sentence, then word boundaries.
    A single word longer than `max_tokens` is returned whole — packing, not
    mangling, is the chunker's job. Pieces always cover `text` exactly, with
    separators attached to the piece before them, so no text is ever lost.
    """
    if not text:
        return []
    if count_tokens(text) <= max_tokens:
        return [(0, len(text))]

    for pattern in (_PARAGRAPH_PATTERN, _SENTENCE_PATTERN, _WORD_PATTERN):
        pieces = _split_after_pattern(text, pattern)
        if len(pieces) <= 1:
            continue
        result: list[tuple[int, int]] = []
        for piece_start, piece_end in pieces:
            for sub_start, sub_end in _split_into_units(text[piece_start:piece_end], max_tokens):
                result.append((piece_start + sub_start, piece_start + sub_end))
        return result

    # No separator at all (one extremely long token run) — nothing more to split.
    return [(0, len(text))]


def _split_after_pattern(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    last = 0
    for match in pattern.finditer(text):
        end = match.end()
        pieces.append((last, end))
        last = end
    if last < len(text):
        pieces.append((last, len(text)))
    return pieces if pieces else [(0, len(text))]
