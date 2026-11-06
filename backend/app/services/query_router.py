"""L0 query router (AGENTS.md §5.10): the cheapest possible layer. Empty or
too-long input is rejected before touching the database; greetings and
thanks get a fixed, friendly reply with no retrieval and no LLM call at all.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.text_normalize import normalize_question

RouterAction = Literal["reject", "small_talk", "continue"]

SMALL_TALK_REPLY = (
    "Hi! Ask me a question about our company documents — for example, "
    '"How do I request time off?" or "What\'s our VPN setup process?"'
)

# Exact, normalised phrases only — deliberately not a fuzzy/semantic match,
# so a real question that happens to start with "hi" (e.g. "hi-vis vest
# policy") is never mistaken for small talk.
_SMALL_TALK_PHRASES = {
    "hi",
    "hello",
    "hey",
    "yo",
    "thanks",
    "thank you",
    "thx",
    "ok",
    "okay",
    "cool",
    "good morning",
    "good afternoon",
    "good evening",
    "nice",
    "great",
    "got it",
}


@dataclass(frozen=True)
class RouterDecision:
    action: RouterAction
    message: str | None = None


def route_question(question: str, max_chars: int) -> RouterDecision:
    stripped = question.strip()
    if not stripped:
        return RouterDecision("reject", "Please enter a question.")
    if len(stripped) > max_chars:
        return RouterDecision(
            "reject", f"Questions are limited to {max_chars} characters. Please shorten it."
        )
    if normalize_question(stripped) in _SMALL_TALK_PHRASES:
        return RouterDecision("small_talk", SMALL_TALK_REPLY)
    return RouterDecision("continue")
