"""No-answer gate #1 (AGENTS.md §5.3): a deterministic, pre-LLM check.

If the best vector similarity is too low, the question is almost certainly
not answered by any uploaded document. Skipping the LLM call in that case
saves cost and latency and prevents the model from guessing.
"""


def passes_similarity_gate(best_vector_similarity: float, min_similarity: float) -> bool:
    """Return True if retrieval found something close enough to bother the
    LLM with. `best_vector_similarity` is cosine similarity in [-1, 1]."""
    return best_vector_similarity >= min_similarity
