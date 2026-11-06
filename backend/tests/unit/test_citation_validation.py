"""Unit tests for deterministic grounding checks (AGENTS.md §5.11): valid
citations are kept, invalid ones are stripped, refusals need no citation,
and a fact not present in the cited source makes the answer ungrounded.
"""

from app.llm.grounding_check import check_grounding
from app.llm.prompts import SourceForPrompt


def _source(n: int, text: str) -> SourceForPrompt:
    return SourceForPrompt(
        n=n,
        chunk_id=f"chunk-{n}",
        document_id=f"doc-{n}",
        filename="doc.md",
        heading=None,
        page=None,
        text=text,
    )


def test_valid_citation_is_kept() -> None:
    sources = [_source(1, "The office closes at 5pm.")]
    result = check_grounding("The office closes at 5pm [1].", sources, is_refusal=False)
    assert result.status == "ok"
    assert result.valid_citation_numbers == {1}
    assert result.removed_citation_numbers == set()
    assert "[1]" in result.cleaned_text


def test_invalid_citation_number_is_removed_and_reported() -> None:
    sources = [_source(1, "The office closes at 5pm.")]
    result = check_grounding("The office closes at 5pm [1][9].", sources, is_refusal=False)
    assert result.removed_citation_numbers == {9}
    assert result.valid_citation_numbers == {1}
    assert "[9]" not in result.cleaned_text
    assert "[1]" in result.cleaned_text


def test_answer_with_only_invalid_citations_is_ungrounded() -> None:
    sources = [_source(1, "The office closes at 5pm.")]
    result = check_grounding("The office closes at 9am [7].", sources, is_refusal=False)
    assert result.status == "ungrounded"
    assert result.valid_citation_numbers == set()


def test_answer_with_no_citation_at_all_is_ungrounded() -> None:
    sources = [_source(1, "The office closes at 5pm.")]
    result = check_grounding("The office closes at 5pm.", sources, is_refusal=False)
    assert result.status == "ungrounded"


def test_refusal_needs_no_citation() -> None:
    sources = [_source(1, "Unrelated fact.")]
    result = check_grounding("I could not find this in the documents.", sources, is_refusal=True)
    assert result.status == "ok"


def test_number_not_present_in_cited_source_is_ungrounded_fact() -> None:
    sources = [_source(1, "The office closes at 5pm.")]
    result = check_grounding("The office closes at 11pm [1].", sources, is_refusal=False)
    assert result.status == "ungrounded"
    assert any("11" in fact for fact in result.ungrounded_facts)


def test_number_present_in_cited_source_is_grounded() -> None:
    sources = [_source(1, "Employees get 20 vacation days per year.")]
    result = check_grounding("Employees get 20 vacation days [1].", sources, is_refusal=False)
    assert result.status == "ok"
    assert result.ungrounded_facts == []


def test_url_not_in_source_is_flagged_ungrounded() -> None:
    sources = [_source(1, "See the internal wiki for details.")]
    result = check_grounding(
        "See https://evil.example.com/phish for details [1].", sources, is_refusal=False
    )
    assert result.status == "ungrounded"
    assert any("evil.example.com" in fact for fact in result.ungrounded_facts)


def test_multiple_citations_combine_cited_text_for_fact_checking() -> None:
    sources = [_source(1, "Opens at 9am."), _source(2, "Closes at 5pm.")]
    result = check_grounding("Opens at 9am and closes at 5pm [1][2].", sources, is_refusal=False)
    assert result.status == "ok"
