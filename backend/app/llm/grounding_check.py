"""Deterministic grounding checks, no extra LLM call (AGENTS.md §5.11).

Runs after generation, before persisting or caching anything. Two
independent checks: every non-refusal answer must carry at least one
citation that was actually retrieved, and every number/date/URL/email/
code snippet the model wrote must appear in the text of a chunk it cited.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.llm.prompts import SourceForPrompt

GroundingStatus = Literal["ok", "ungrounded"]

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_URL_PATTERN = re.compile(r"https?://\S+")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CODE_PATTERN = re.compile(r"`([^`]+)`")
# No trailing `\b`: a number immediately followed by a unit letter (e.g.
# "11pm", "20kg") must still count as a fact to verify. The leading
# negative lookbehind still stops a number *inside* a larger token like
# "V2" from being extracted on its own.
_NUMBER_PATTERN = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")


@dataclass(frozen=True)
class GroundingResult:
    status: GroundingStatus
    cleaned_text: str
    valid_citation_numbers: set[int]
    removed_citation_numbers: set[int]
    ungrounded_facts: list[str]


def check_grounding(
    answer_text: str, sources: list[SourceForPrompt], *, is_refusal: bool
) -> GroundingResult:
    """`is_refusal` is True when the model called `offer_help_desk_ticket`:
    a refusal needs no citation and is never checked for ungrounded facts.
    """
    valid_numbers = {source.n for source in sources}
    cited = [int(match.group(1)) for match in _CITATION_PATTERN.finditer(answer_text)]
    removed = {n for n in cited if n not in valid_numbers}
    cleaned_text = _strip_citations(answer_text, removed)
    remaining_valid = {n for n in cited if n in valid_numbers}

    if is_refusal:
        return GroundingResult("ok", cleaned_text, remaining_valid, removed, [])

    if not remaining_valid:
        return GroundingResult("ungrounded", cleaned_text, remaining_valid, removed, [])

    cited_text = " ".join(source.text for source in sources if source.n in remaining_valid)
    facts = _extract_facts(cleaned_text)
    ungrounded_facts = [fact for fact in facts if fact not in cited_text]
    status: GroundingStatus = "ungrounded" if ungrounded_facts else "ok"
    return GroundingResult(status, cleaned_text, remaining_valid, removed, ungrounded_facts)


def _strip_citations(text: str, numbers_to_remove: set[int]) -> str:
    if not numbers_to_remove:
        return text
    for number in numbers_to_remove:
        text = re.sub(rf"\[{number}\]", "", text)
    return text


def _extract_facts(text: str) -> list[str]:
    """Numbers, dates, URLs, emails and code/commands, in that priority
    order so a long number already captured as part of a URL/email is not
    also re-checked (and possibly flagged) as a bare number."""
    without_citations = _CITATION_PATTERN.sub("", text)
    facts: list[str] = []
    consumed = without_citations
    for pattern in (_URL_PATTERN, _EMAIL_PATTERN, _CODE_PATTERN):
        matches = pattern.findall(consumed)
        facts.extend(matches)
        consumed = pattern.sub(" ", consumed)
    facts.extend(_NUMBER_PATTERN.findall(consumed))
    return facts
