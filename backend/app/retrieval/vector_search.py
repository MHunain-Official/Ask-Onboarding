"""Vector (cosine) search over `document_chunks`, filtered by ACL (§5.3).

The ACL filter is part of the SQL query itself — never applied after the
rows come back — so a chunk the user may not read never leaves the
database (AGENTS.md §3.2 LLM-specific rule 1).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.base import Embedder
from app.models import AccessLevel, DocumentChunk


@dataclass(frozen=True)
class ScoredChunk:
    """One retrieved chunk plus how well it matched the question."""

    chunk_id: UUID
    document_id: UUID
    text: str
    heading: str | None
    page_number: int | None
    access_level: AccessLevel
    score: float  # cosine similarity in [-1, 1]; higher is better
    char_start: int
    char_end: int


def vector_search(
    db: Session,
    embedder: Embedder,
    question: str,
    allowed_levels: list[AccessLevel],
    top_n: int,
) -> list[ScoredChunk]:
    """Embed the question and return the `top_n` nearest chunks by cosine
    similarity, restricted to `allowed_levels`.

    pgvector's `<=>` operator is cosine *distance* (0 = identical,
    2 = opposite), not similarity — a mix-up this project's AI_LOG calls
    out explicitly as an easy mistake. We convert with `similarity = 1 -
    distance` before returning, so every caller works with similarity.
    """
    query_vector = embedder.embed_query(question)
    distance = DocumentChunk.embedding.cosine_distance(query_vector)

    rows = db.execute(
        select(DocumentChunk, distance.label("distance"))
        .where(DocumentChunk.access_level.in_(allowed_levels))
        .order_by(distance)
        .limit(top_n)
    ).all()

    return [
        ScoredChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            text=chunk.text,
            heading=chunk.heading,
            page_number=chunk.page_number,
            access_level=chunk.access_level,
            score=1.0 - distance_value,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        for chunk, distance_value in rows
    ]
