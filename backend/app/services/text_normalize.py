"""Shared question normalisation (AGENTS.md §5.10 L1: "lowercase, trim,
collapse spaces, strip trailing punctuation"). Used by both the query
router (small-talk detection) and the exact answer cache (hash key), so
"Thanks!" and "thanks" and the same question asked twice with different
spacing always agree.
"""

import re

_WHITESPACE = re.compile(r"\s+")
_TRAILING_PUNCTUATION = re.compile(r"[?!.,;:]+$")


def normalize_question(text: str) -> str:
    lowered = text.strip().lower()
    collapsed = _WHITESPACE.sub(" ", lowered)
    return _TRAILING_PUNCTUATION.sub("", collapsed).strip()
