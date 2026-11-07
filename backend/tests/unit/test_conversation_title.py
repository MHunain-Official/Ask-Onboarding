"""Conversation sidebar titles come from the first user question."""

from app.services.conversation_service import title_from_question


def test_title_from_question_keeps_short_questions() -> None:
    assert title_from_question("How do I set up VPN?") == "How do I set up VPN?"


def test_title_from_question_truncates_long_questions() -> None:
    long = "What is the exact procedure for " + ("submitting expenses " * 10)
    title = title_from_question(long, max_length=40)
    assert len(title) <= 40
    assert title.endswith("…")


def test_title_from_question_collapses_whitespace() -> None:
    assert title_from_question("  hello   world  ") == "hello world"
