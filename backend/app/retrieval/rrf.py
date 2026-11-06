"""Reciprocal Rank Fusion: combine several ranked lists into one ranking
(AGENTS.md §5.3) without needing the two input lists' scores to be on the
same scale — vector cosine similarity and `ts_rank_cd` are not comparable,
but rank position always is.

Pure and dependency-free so it is unit-testable without a database.
"""

from uuid import UUID

RRF_K = 60  # the constant from AGENTS.md §5.3: score = Σ 1/(60 + rank)


def reciprocal_rank_fusion(ranked_lists: list[list[UUID]]) -> list[tuple[UUID, float]]:
    """Fuse multiple rank-ordered id lists into one list of `(id, score)`,
    sorted by score descending.

    Each list is already in best-to-worst order (rank 1 = index 0). An id
    missing from a list simply contributes nothing from that list — it is
    not penalised beyond not getting that list's points.
    """
    scores: dict[UUID, float] = {}
    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
