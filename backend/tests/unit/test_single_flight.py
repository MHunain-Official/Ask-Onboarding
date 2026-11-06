"""Unit tests for the single-flight registry (AGENTS.md §5.10 L5): only
the leader computes; a follower waits and replays the leader's result.
"""

import threading
import time

from app.services.single_flight import SingleFlightRegistry


def test_leader_computes_and_follower_replays_same_result() -> None:
    registry: SingleFlightRegistry[str] = SingleFlightRegistry()
    compute_calls = []

    def leader_work() -> None:
        flight, is_leader = registry.acquire("key")
        assert is_leader is True
        time.sleep(0.05)
        compute_calls.append("leader")
        registry.release("key", flight, "the answer")

    def follower_work(results: list[str | None]) -> None:
        time.sleep(0.01)  # ensure the leader has already acquired
        flight, is_leader = registry.acquire("key")
        assert is_leader is False
        results.append(registry.wait_for_result(flight))

    follower_results: list[str | None] = []
    leader_thread = threading.Thread(target=leader_work)
    follower_thread = threading.Thread(target=follower_work, args=(follower_results,))
    leader_thread.start()
    follower_thread.start()
    leader_thread.join()
    follower_thread.join()

    assert compute_calls == ["leader"]  # the follower never computed its own answer
    assert follower_results == ["the answer"]


def test_distinct_keys_both_become_leaders() -> None:
    registry: SingleFlightRegistry[str] = SingleFlightRegistry()
    _, is_leader_a = registry.acquire("key-a")
    _, is_leader_b = registry.acquire("key-b")
    assert is_leader_a is True
    assert is_leader_b is True


def test_key_is_reusable_after_release() -> None:
    registry: SingleFlightRegistry[str] = SingleFlightRegistry()
    flight, is_leader = registry.acquire("key")
    registry.release("key", flight, "done")
    _, is_leader_again = registry.acquire("key")
    assert is_leader_again is True
