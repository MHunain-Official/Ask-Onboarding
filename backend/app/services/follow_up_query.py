"""Build a retrieval-only query that keeps follow-ups on-topic.

The LLM already sees conversation history, but hybrid search used to run on
the latest message alone. Short follow-ups like "thora detail mai batoo gai?"
then retrieve unrelated docs and trip the similarity gate. Prepending the
previous user question for retrieval only fixes that without a rewrite LLM.
"""

from __future__ import annotations

import re

from app.llm.base import ChatMessage
from app.services.abbreviations import expand_abbreviations

# Referential follow-ups (English + common Roman Urdu/Hinglish).
_FOLLOW_UP_HINTS = re.compile(
    r"\b("
    r"more|detail|details|explain|simpler|elaborate|continue|further|also|"
    r"that|this|those|them|it|same|"
    r"thora|zyada|batao|batoo|bata|bataye|gai|aur|uska|iska|uski|inki|woh|yeh|"
    r"please|pls"
    r")\b",
    re.IGNORECASE,
)

# Clear new questions should not inherit the previous topic for search.
_STANDALONE_QUESTION = re.compile(
    r"^\s*(how|what|when|where|who|which|why|can i|do i|does|is there|are there)\b",
    re.IGNORECASE,
)


def last_user_question(history: list[ChatMessage]) -> str | None:
    for message in reversed(history):
        if message.role == "user" and message.content.strip():
            return message.content.strip()
    return None


def looks_like_follow_up(question: str) -> bool:
    cleaned = question.strip()
    if not cleaned:
        return False
    if _FOLLOW_UP_HINTS.search(cleaned):
        return True
    words = re.findall(r"[A-Za-z0-9']+", cleaned)
    # Vague short turns without a new interrogative topic ("ok and?", "aur?").
    return bool(len(words) <= 8 and not _STANDALONE_QUESTION.search(cleaned))


def build_retrieval_question(question: str, history: list[ChatMessage]) -> str:
    """Question used for embedding/keyword search (not what the LLM sees)."""
    expanded = expand_abbreviations(question)
    previous = last_user_question(history)
    if previous is None or not looks_like_follow_up(question):
        return expanded
    # Previous topic first so vector/keyword search stay on the prior docs.
    return f"{previous}\nFollow-up: {expanded}"
