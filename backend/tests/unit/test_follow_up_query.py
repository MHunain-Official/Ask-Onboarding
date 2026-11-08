from app.llm.base import ChatMessage
from app.services.follow_up_query import (
    build_retrieval_question,
    looks_like_follow_up,
)


def test_short_roman_urdu_follow_up_uses_previous_user_question() -> None:
    history = [
        ChatMessage(role="user", content="Slack kai norms kia hai ?"),
        ChatMessage(role="assistant", content="Slack ke norms yeh hain… [1]"),
    ]
    retrieval = build_retrieval_question("thora detail mai batoo gai ?", history)
    assert "Slack kai norms kia hai ?" in retrieval
    assert "thora detail mai batoo gai ?" in retrieval
    assert retrieval.startswith("Slack kai norms kia hai ?")


def test_standalone_new_topic_does_not_prepend_history() -> None:
    history = [
        ChatMessage(role="user", content="Slack kai norms kia hai ?"),
        ChatMessage(role="assistant", content="Slack norms… [1]"),
    ]
    question = "How do I request Paid Time Off according to the 2025 policy?"
    retrieval = build_retrieval_question(question, history)
    assert retrieval == question
    assert "Slack" not in retrieval


def test_looks_like_follow_up_for_short_and_detail_phrases() -> None:
    assert looks_like_follow_up("thora detail mai batoo gai ?")
    assert looks_like_follow_up("tell me more")
    assert not looks_like_follow_up(
        "How do I request Paid Time Off according to the 2025 company policy document?"
    )


def test_no_history_only_expands_abbreviations() -> None:
    assert "employee" in build_retrieval_question("new EMP handbook", [])
