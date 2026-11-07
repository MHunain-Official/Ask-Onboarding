"""L0 query router (AGENTS.md §5.10): cheapest layer before retrieval/LLM.

Empty or too-long input is rejected; greetings/thanks get a fixed reply;
conversation-meta and "explain simpler" intents are flagged for special paths.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.text_normalize import normalize_question

RouterAction = Literal[
    "reject",
    "small_talk",
    "explain_simpler",
    "conversation_meta",
    "continue",
]

SMALL_TALK_REPLY = (
    "Hi! I'm Ask Onboarding — I answer from your company documents. "
    'Try something like "How do I request PTO?" or "What\'s the VPN command?"'
)

# Exact normalised phrases — keep this set narrow so "hi-vis vest policy"
# is never mistaken for small talk.
_SMALL_TALK_EXACT = {
    "hi",
    "hello",
    "hey",
    "hey there",
    "hi there",
    "hello there",
    "yo",
    "thanks",
    "thank you",
    "thanks a lot",
    "thank you so much",
    "thx",
    "ty",
    "ok",
    "okay",
    "k",
    "cool",
    "nice",
    "great",
    "got it",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "bye",
    "goodbye",
    "see you",
    "how are you",
    "how r you",
    "whats up",
    "what's up",
    "sup",
}

_SMALL_TALK_PREFIXES = (
    "hi ",
    "hello ",
    "hey ",
    "thanks ",
    "thank you ",
    "good morning",
    "good afternoon",
    "good evening",
)

_EXPLAIN_SIMPLER_PHRASES = {
    "explain simpler",
    "explain more simply",
    "explain in simple words",
    "explain in simpler words",
    "explain in easy wording",
    "explain in easier wording",
    "in plain words",
    "in plain english",
    "make it simpler",
    "make it easier",
    "simplify that",
    "simplify this",
    "simpler please",
    "easier please",
    "eli5",
    "explain like im 5",
    "explain like i'm 5",
}

_CONVERSATION_META_PHRASES = {
    "what did we talk about",
    "what were we talking about",
    "what are we talking about",
    "what was my first question",
    "what was the first question",
    "summarize this chat",
    "summarise this chat",
    "summarize our conversation",
    "summarise our conversation",
    "remind me what we discussed",
    "what did i ask earlier",
    "recap this conversation",
    "recap our chat",
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
    normalised = normalize_question(stripped)
    if _is_small_talk(normalised):
        return RouterDecision("small_talk", SMALL_TALK_REPLY)
    if normalised in _EXPLAIN_SIMPLER_PHRASES or _starts_with_any(
        normalised, ("explain this", "simplify", "make that easier")
    ):
        return RouterDecision("explain_simpler")
    if normalised in _CONVERSATION_META_PHRASES or _starts_with_any(
        normalised, ("what did we", "what were we", "summarize our", "summarise our", "recap ")
    ):
        return RouterDecision("conversation_meta")
    return RouterDecision("continue")


def _is_small_talk(normalised: str) -> bool:
    if normalised in _SMALL_TALK_EXACT:
        return True
    # Short greetings with trailing punctuation already stripped by normalize.
    if len(normalised.split()) <= 4 and any(
        normalised.startswith(prefix) for prefix in _SMALL_TALK_PREFIXES
    ):
        # Avoid matching real questions that start with "hi" as a word in a phrase
        # longer than a greeting — only allow if no question word follows.
        question_words = ("how", "what", "when", "where", "why", "which", "who", "can", "do")
        tokens = normalised.split()
        return not (len(tokens) >= 2 and tokens[1] in question_words)
    return False


def _starts_with_any(text: str, prefixes: tuple[str, ...]) -> bool:
    return any(text.startswith(prefix) for prefix in prefixes)
