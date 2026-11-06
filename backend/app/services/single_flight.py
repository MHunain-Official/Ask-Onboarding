"""Best-effort single-flight for identical concurrent questions (AGENTS.md
§5.10 L5 / §5.12 #21).

Only the leader (the first caller for a given key) actually generates an
answer; any caller that arrives while the leader is still running waits
and then replays the leader's final answer, so one popular question
asked by many users at once triggers exactly one LLM call.

Honest limitation: followers do not see the leader's tokens stream live —
they wait, then get the finished answer in one block, the same shape as a
cache hit. True live token fan-out would need a pub/sub layer (Redis),
which AGENTS.md §1 deliberately avoids. This still achieves the goal that
matters for cost/latency: one generation, not N.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class Flight[T]:
    event: threading.Event = field(default_factory=threading.Event)
    result: T | None = None


class SingleFlightRegistry[T]:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flights: dict[str, Flight[T]] = {}

    def acquire(self, key: str) -> tuple[Flight[T], bool]:
        """Return `(flight, is_leader)`. Callers that are not the leader
        must call `wait_for_result`, never generate their own answer in
        parallel with the leader for the same key."""
        with self._lock:
            flight = self._flights.get(key)
            if flight is not None:
                return flight, False
            flight = Flight()
            self._flights[key] = flight
            return flight, True

    def release(self, key: str, flight: Flight[T], result: T | None) -> None:
        """Leader-only: publish the result and let any waiting followers
        through, then remove the key so the next distinct request leads."""
        flight.result = result
        flight.event.set()
        with self._lock:
            if self._flights.get(key) is flight:
                del self._flights[key]

    def wait_for_result(self, flight: Flight[T], timeout: float = 90.0) -> T | None:
        """`None` means the leader failed or timed out — the caller should
        fall back to generating its own answer rather than wait forever."""
        flight.event.wait(timeout=timeout)
        return flight.result


_registry: SingleFlightRegistry[object] = SingleFlightRegistry()


def get_single_flight_registry() -> SingleFlightRegistry[object]:
    return _registry
