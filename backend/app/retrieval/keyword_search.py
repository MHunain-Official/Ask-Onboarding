"""Postgres full-text search over `document_chunks`, filtered by ACL (§5.3).

Complements `vector_search`: exact keywords (ticket numbers, product
names, commands) sometimes rank higher under full-text than under cosine
similarity, which is why the hybrid layer fuses both.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessLevel, DocumentChunk


@dataclass(frozen=True)
class KeywordScoredChunk:
    """One chunk matched by full-text search, with its `ts_rank_cd` score."""

    chunk_id: UUID
    document_id: UUID
    text: str
    heading: str | None
    page_number: int | None
    access_level: AccessLevel
    score: float


def keyword_search(
    db: Session,
    question: str,
    allowed_levels: list[AccessLevel],
    top_n: int,
) -> list[KeywordScoredChunk]:
    """Rank chunks whose `tsv` column matches `question` under
    `websearch_to_tsquery`, restricted to `allowed_levels`.

    `websearch_to_tsquery` accepts plain user text (quotes, `-word`, `or`)
    without raising on malformed syntax the way `to_tsquery` would — the
    right choice for untrusted question text.
    """
    tsquery = func.websearch_to_tsquery("english", question)
    rank = func.ts_rank_cd(DocumentChunk.tsv, tsquery)

    rows = db.execute(
        select(DocumentChunk, rank.label("rank"))
        .where(
            DocumentChunk.access_level.in_(allowed_levels),
            DocumentChunk.tsv.op("@@")(tsquery),
        )
        .order_by(rank.desc())
        .limit(top_n)
    ).all()

    return [
        KeywordScoredChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            text=chunk.text,
            heading=chunk.heading,
            page_number=chunk.page_number,
            access_level=chunk.access_level,
            score=float(rank_value),
        )
        for chunk, rank_value in rows
    ]
