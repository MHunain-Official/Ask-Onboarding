"""Known fusion-ordering cases for Reciprocal Rank Fusion (AGENTS.md §9).

Pure-function tests: no database, no embedder.
"""

import uuid

from app.retrieval.rrf import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_orders_by_combined_rank() -> None:
    a, b, c, d, e = (uuid.uuid4() for _ in range(5))
    vector_ranked = [a, b, c, d]  # a is #1 by vector similarity
    keyword_ranked = [c, a, e, b]  # c is #1 by keyword rank

    fused = reciprocal_rank_fusion([vector_ranked, keyword_ranked])

    # a: 1/61 + 1/62 = 0.032523 (ranked #1 in vector, #2 in keyword)
    # c: 1/63 + 1/61 = 0.032266 (ranked #3 in vector, #1 in keyword)
    # b: 1/62 + 1/64 = 0.031754
    # e: 0       + 1/63 = 0.015873 (only in keyword)
    # d: 1/64 + 0      = 0.015625 (only in vector)
    assert [chunk_id for chunk_id, _ in fused] == [a, c, b, e, d]


def test_reciprocal_rank_fusion_single_list_preserves_order() -> None:
    """Vector-only mode (hybrid disabled) is just one ranked list; fusing a
    single list must not reorder it."""
    a, b, c = (uuid.uuid4() for _ in range(3))

    fused = reciprocal_rank_fusion([[a, b, c]])

    assert [chunk_id for chunk_id, _ in fused] == [a, b, c]
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)


def test_reciprocal_rank_fusion_empty_input_returns_empty() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_reciprocal_rank_fusion_missing_from_one_list_still_scores() -> None:
    """An id absent from the second list only loses that list's points, it
    is not disqualified."""
    a, b = uuid.uuid4(), uuid.uuid4()

    fused = reciprocal_rank_fusion([[a, b], [a]])
    scores = dict(fused)

    assert scores[a] == 1.0 / 61 + 1.0 / 61
    assert scores[b] == 1.0 / 62
