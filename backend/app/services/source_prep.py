"""Turns retrieved chunks into numbered prompt sources, with the two lean-
prompt touch-ups from AGENTS.md §5.10 L6: drop near-duplicate chunks and
hand the result to `truncate_sources_to_token_budget` for the context cap.
"""

import difflib

from app.llm.prompts import SourceForPrompt
from app.retrieval.hybrid import RetrievedChunk

_NEAR_DUPLICATE_RATIO = 0.95


def build_sources(chunks: list[RetrievedChunk]) -> list[SourceForPrompt]:
    return [
        SourceForPrompt(
            n=index + 1,
            chunk_id=str(chunk.chunk_id),
            document_id=str(chunk.document_id),
            filename=chunk.filename,
            heading=chunk.heading,
            page=chunk.page,
            text=chunk.text,
        )
        for index, chunk in enumerate(chunks)
    ]


def drop_near_duplicates(sources: list[SourceForPrompt]) -> list[SourceForPrompt]:
    """Drop a lower-ranked source whose text is near-identical to a
    higher-ranked one already kept."""
    kept: list[SourceForPrompt] = []
    for source in sources:
        if any(
            difflib.SequenceMatcher(None, source.text, other.text).ratio() > _NEAR_DUPLICATE_RATIO
            for other in kept
        ):
            continue
        kept.append(source)
    return kept
