"""Unit tests for the L0 query router (AGENTS.md §5.10): reject empty/too
long, fixed reply for small talk, everything else continues.
"""

from app.services.query_router import route_question


def test_empty_question_is_rejected() -> None:
    decision = route_question("   ", max_chars=1000)
    assert decision.action == "reject"


def test_too_long_question_is_rejected() -> None:
    decision = route_question("a" * 50, max_chars=10)
    assert decision.action == "reject"


def test_greeting_is_small_talk_with_no_retrieval_needed() -> None:
    decision = route_question("Thanks!", max_chars=1000)
    assert decision.action == "small_talk"
    assert decision.message


def test_small_talk_match_is_case_and_punctuation_insensitive() -> None:
    assert route_question("  Hi  ", max_chars=1000).action == "small_talk"
    assert route_question("OK.", max_chars=1000).action == "small_talk"


def test_real_question_continues() -> None:
    decision = route_question("How do I request time off?", max_chars=1000)
    assert decision.action == "continue"


def test_question_that_merely_starts_with_a_greeting_word_continues() -> None:
    """A real question must never be mistaken for small talk just because
    it starts with the same word."""
    decision = route_question("hi-vis vest policy for warehouse staff", max_chars=1000)
    assert decision.action == "continue"
