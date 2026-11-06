"""Admin dashboard stats tiles (AGENTS.md §3.6 admin page, §5.10 "LLM
calls avoided"). Everything here is computed from the `llm_calls` table
that every answer attempt already writes to — no second LLM call, no
extra bookkeeping table.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CacheHit, LlmCall, LlmCallStatus
from app.schemas import AdminStats

_EMPTY_STATS = AdminStats(
    total_requests=0,
    error_rate=0.0,
    p50_latency_ms=0.0,
    p95_latency_ms=0.0,
    total_cost_usd=0.0,
    no_answer_rate=0.0,
    cache_hit_rate=0.0,
    llm_calls_avoided=0,
    estimated_saved_usd=0.0,
)


def compute_admin_stats(db: Session) -> AdminStats:
    total_requests = db.query(func.count(LlmCall.id)).scalar() or 0
    if total_requests == 0:
        return _EMPTY_STATS

    error_count = (
        db.query(func.count(LlmCall.id)).filter(LlmCall.status == LlmCallStatus.ERROR).scalar() or 0
    )
    no_answer_count = (
        db.query(func.count(LlmCall.id)).filter(LlmCall.status == LlmCallStatus.NO_ANSWER).scalar()
        or 0
    )
    cache_hit_count = (
        db.query(func.count(LlmCall.id)).filter(LlmCall.cache_hit != CacheHit.NONE).scalar() or 0
    )
    total_cost = db.query(func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0)).scalar()

    p50, p95 = _latency_percentiles(db)
    # Every NO_ANSWER row is a gated response (the deterministic
    # similarity gate or the budget cap) — the real LLM path never
    # produces that status (see `generation_audit.resolve_status`), so
    # cache hits + no-answers is exactly "calls the LLM never saw" (§5.10).
    llm_calls_avoided = cache_hit_count + no_answer_count

    return AdminStats(
        total_requests=total_requests,
        error_rate=round(error_count / total_requests, 4),
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        total_cost_usd=round(float(total_cost or 0.0), 4),
        no_answer_rate=round(no_answer_count / total_requests, 4),
        cache_hit_rate=round(cache_hit_count / total_requests, 4),
        llm_calls_avoided=llm_calls_avoided,
        estimated_saved_usd=round(llm_calls_avoided * _average_real_call_cost(db), 4),
    )


def _latency_percentiles(db: Session) -> tuple[float, float]:
    rows = (
        db.query(LlmCall.latency_ms_total)
        .filter(LlmCall.latency_ms_total.is_not(None))
        .order_by(LlmCall.latency_ms_total.asc())
        .all()
    )
    # The `.is_not(None)` filter above guarantees every value is a real
    # int; mypy can't see that through the ORM tuple-row unpacking.
    values = [int(row[0]) for row in rows if row[0] is not None]
    return _percentile(values, 0.50), _percentile(values, 0.95)


def _percentile(sorted_values: list[int], fraction: float) -> float:
    """Nearest-rank percentile over an already-sorted list. Good enough for
    a dashboard tile and avoids pulling in a stats library for one number."""
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return float(sorted_values[index])


def _average_real_call_cost(db: Session) -> float:
    """Average cost of a call that actually reached the LLM (no cache hit,
    not a gated no-answer) — used to estimate dollars saved by every call
    the cache or the gate avoided."""
    avg = (
        db.query(func.avg(LlmCall.estimated_cost_usd))
        .filter(
            LlmCall.cache_hit == CacheHit.NONE,
            LlmCall.status != LlmCallStatus.NO_ANSWER,
            LlmCall.estimated_cost_usd.is_not(None),
        )
        .scalar()
    )
    return float(avg) if avg is not None else 0.0
