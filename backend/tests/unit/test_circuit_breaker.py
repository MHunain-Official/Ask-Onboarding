"""Unit tests for the in-memory circuit breaker (AGENTS.md §5.9)."""

import time

from app.llm.circuit_breaker import CircuitBreaker


def test_closed_breaker_allows_calls() -> None:
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
    assert breaker.is_open() is False


def test_breaker_opens_after_threshold_consecutive_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is False  # not yet at threshold
    breaker.record_failure()
    assert breaker.is_open() is True


def test_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=30)
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.is_open() is False  # count was reset, only one failure since


def test_breaker_closes_again_after_cooldown_elapses() -> None:
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
    breaker.record_failure()
    assert breaker.is_open() is True
    time.sleep(0.1)
    assert breaker.is_open() is False
