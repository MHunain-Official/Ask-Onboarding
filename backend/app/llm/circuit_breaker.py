"""Simple in-memory circuit breaker (AGENTS.md §5.9).

After `failure_threshold` consecutive failures, `is_open()` returns True
for `cooldown_seconds` so callers can fail fast instead of hanging every
request on a provider that is already down. After the cooldown, one
request is allowed through as a half-open probe: if it fails, the window
re-opens from that moment.
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    failure_threshold: int
    cooldown_seconds: float
    _consecutive_failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def is_open(self) -> bool:
        """True if calls should be skipped right now."""
        with self._lock:
            if self._opened_at is None:
                return False
            elapsed = time.monotonic() - self._opened_at
            return elapsed < self.cooldown_seconds

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
