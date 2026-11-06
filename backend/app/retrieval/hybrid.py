"""Combine vector and keyword search into one ranked list (AGENTS.md §5.3).

When `HYBRID_ENABLED` is on, both searches run and are fused with
Reciprocal Rank Fusion; when it is off, vector search alone decides the
order. Either way the ACL filter was already applied inside each search's
SQL query — this module only combines rankings, it never re-reads chunks
without going through those filtered queries.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.base import Embedder
from app.models import AccessLevel, Document
from app.retrieval.keyword_search import KeywordScoredChunk, keyword_search
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.vector_search import ScoredChunk, vector_search


@dataclass(frozen=True)
class RetrievedChunk:
    """One final, ranked passage ready to show a user or build a prompt."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    page: int | None
    heading: str | None
    text: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    best_vector_similarity: float  # used by the no-answer gate, §5.3


def retrieve(
    db: Session,
    embedder: Embedder,
    question: str,
    allowed_levels: list[AccessLevel],
    top_k: int,
    candidates: int,
    hybrid_enabled: bool,
) -> RetrievalResult:
    """Run vector search (always) and keyword search (if enabled), fuse
    them, and return the top `top_k` chunks plus the best raw vector
    similarity for the no-answer gate."""
    vector_results = vector_search(db, embedder, question, allowed_levels, candidates)
    best_vector_similarity = vector_results[0].score if vector_results else -1.0

    keyword_results: list[KeywordScoredChunk] = []
    if hybrid_enabled:
        keyword_results = keyword_search(db, question, allowed_levels, candidates)

    chunk_data = _index_by_chunk_id(vector_results, keyword_results)
    ranked_ids = _fuse_or_rank(vector_results, keyword_results, hybrid_enabled)
    top_ids = [chunk_id for chunk_id, _score in ranked_ids[:top_k]]

    filenames = _filenames_for(db, {chunk_data[cid].document_id for cid in top_ids})
    scores_by_id = dict(ranked_ids)

    chunks = [
        RetrievedChunk(
            chunk_id=chunk_id,
            document_id=chunk_data[chunk_id].document_id,
            filename=filenames.get(chunk_data[chunk_id].document_id, "unknown"),
            page=chunk_data[chunk_id].page_number,
            heading=chunk_data[chunk_id].heading,
            text=chunk_data[chunk_id].text,
            score=scores_by_id[chunk_id],
        )
        for chunk_id in top_ids
    ]
    return RetrievalResult(chunks=chunks, best_vector_similarity=best_vector_similarity)


def _fuse_or_rank(
    vector_results: list[ScoredChunk],
    keyword_results: list[KeywordScoredChunk],
    hybrid_enabled: bool,
) -> list[tuple[UUID, float]]:
    if not hybrid_enabled:
        return [(chunk.chunk_id, chunk.score) for chunk in vector_results]
    vector_ids = [chunk.chunk_id for chunk in vector_results]
    keyword_ids = [chunk.chunk_id for chunk in keyword_results]
    return reciprocal_rank_fusion([vector_ids, keyword_ids])


def _index_by_chunk_id(
    vector_results: list[ScoredChunk], keyword_results: list[KeywordScoredChunk]
) -> dict[UUID, ScoredChunk | KeywordScoredChunk]:
    """Both result types carry the same chunk fields; either stands in for
    the other here so we need not re-query chunk text after fusing."""
    index: dict[UUID, ScoredChunk | KeywordScoredChunk] = {}
    for vector_chunk in vector_results:
        index[vector_chunk.chunk_id] = vector_chunk
    for keyword_chunk in keyword_results:
        index.setdefault(keyword_chunk.chunk_id, keyword_chunk)
    return index


def _filenames_for(db: Session, document_ids: set[UUID]) -> dict[UUID, str]:
    if not document_ids:
        return {}
    rows = db.execute(
        select(Document.id, Document.filename).where(Document.id.in_(document_ids))
    ).all()
    return {row.id: row.filename for row in rows}
