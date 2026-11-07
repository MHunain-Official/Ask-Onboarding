"""Human-readable one-liners for retrieval-track SSE steps."""

from app.retrieval.hybrid import RetrievalResult


def format_retrieval_detail(
    result: RetrievalResult, *, hybrid_enabled: bool, elapsed_ms: int
) -> str:
    mode = "hybrid (vector + keyword)" if hybrid_enabled else "vector only"
    if not result.chunks:
        return f"{mode} · no chunks · {elapsed_ms} ms"
    top = result.chunks[0]
    heading = f" · {top.heading}" if top.heading else ""
    return (
        f"{mode} · {len(result.chunks)} passage(s) · "
        f"best {result.best_vector_similarity:.2f} · "
        f"top: {top.filename}{heading} · {elapsed_ms} ms"
    )


def format_gate_detail(best: float, minimum: float, passed: bool) -> str:
    compare = "≥" if passed else "<"
    outcome = "continue to answer" if passed else "no answer — skip LLM"
    return f"best similarity {best:.2f} {compare} {minimum:.2f} → {outcome}"
