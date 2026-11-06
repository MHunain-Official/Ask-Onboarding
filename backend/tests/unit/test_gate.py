"""Unit tests for the no-answer similarity gate (AGENTS.md §5.3 gate #1)."""

from app.retrieval.gate import passes_similarity_gate


def test_passes_similarity_gate_true_when_similarity_above_threshold() -> None:
    assert passes_similarity_gate(best_vector_similarity=0.45, min_similarity=0.30) is True


def test_passes_similarity_gate_false_when_similarity_below_threshold() -> None:
    assert passes_similarity_gate(best_vector_similarity=0.10, min_similarity=0.30) is False


def test_passes_similarity_gate_true_at_exact_threshold() -> None:
    assert passes_similarity_gate(best_vector_similarity=0.30, min_similarity=0.30) is True
