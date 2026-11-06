"""Per-user daily token cap and a global daily USD kill switch (AGENTS.md
§5.10 L7). Over cap never fails silently: the caller switches to a
degraded, retrieval-only response and logs an audit event.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import UsageDaily


def _today() -> datetime:
    """`usage_daily.date` is a naive `DateTime` column (§4), not a `DATE`
    column, so the lookup key is always midnight UTC — never the current
    time — or two requests in the same day would never match the same row.
    """
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day)


@dataclass(frozen=True)
class BudgetStatus:
    degraded: bool
    reason: str | None


def check_budget(
    db: Session,
    user_id: uuid.UUID,
    *,
    daily_token_cap_per_user: int,
    daily_cost_cap_usd: float,
) -> BudgetStatus:
    today = _today()
    user_usage = (
        db.query(UsageDaily).filter(UsageDaily.date == today, UsageDaily.user_id == user_id).first()
    )
    if user_usage is not None:
        tokens_used = user_usage.input_tokens + user_usage.output_tokens
        if tokens_used >= daily_token_cap_per_user:
            return BudgetStatus(degraded=True, reason="per_user_token_cap")

    total_cost_today = (
        db.query(func.coalesce(func.sum(UsageDaily.cost_usd), 0.0))
        .filter(UsageDaily.date == today)
        .scalar()
    )
    if total_cost_today is not None and total_cost_today >= daily_cost_cap_usd:
        return BudgetStatus(degraded=True, reason="global_cost_cap")

    return BudgetStatus(degraded=False, reason=None)


def record_usage(
    db: Session,
    user_id: uuid.UUID,
    *,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    cache_hit: bool = False,
) -> None:
    today = _today()
    row = (
        db.query(UsageDaily).filter(UsageDaily.date == today, UsageDaily.user_id == user_id).first()
    )
    if row is None:
        # Explicit zeros: the mapped_column `default=0` only applies once
        # SQLAlchemy flushes the INSERT, but we increment this same Python
        # object before that happens, so it must not start out as None.
        row = UsageDaily(
            date=today,
            user_id=user_id,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            requests=0,
            cache_hits=0,
        )
        db.add(row)
    row.input_tokens += input_tokens
    row.output_tokens += output_tokens
    row.cost_usd += cost_usd
    row.requests += 1
    if cache_hit:
        row.cache_hits += 1
    db.commit()


def estimate_cost_usd(
    input_tokens: int, output_tokens: int, price_input_per_mtok: float, price_output_per_mtok: float
) -> float:
    return (input_tokens / 1_000_000) * price_input_per_mtok + (
        output_tokens / 1_000_000
    ) * price_output_per_mtok
