"""Parser tests (AGENTS.md §9): markdown, txt with encoding fallback, and
PDF page numbers / the empty-PDF error path. No API keys needed."""

import pytest

from app.ingestion.parsers import ParseError, parse_markdown, parse_pdf, parse_txt
from tests.unit.pdf_builder import build_minimal_pdf


def test_parse_markdown_decodes_utf8() -> None:
    raw = "# Heading\n\nSome café ☕ content.".encode()

    parsed = parse_markdown(raw)

    assert parsed.text == "# Heading\n\nSome café ☕ content."
    assert parsed.pages == []


def test_parse_markdown_rejects_empty_content() -> None:
    with pytest.raises(ParseError):
        parse_markdown(b"   \n\n  ")


def test_parse_txt_decodes_utf8() -> None:
    raw = "Plain text with unicode: naïve, résumé.".encode()

    parsed = parse_txt(raw)

    assert parsed.text == "Plain text with unicode: naïve, résumé."


def test_parse_txt_falls_back_to_latin1_on_invalid_utf8() -> None:
    # "café" encoded as latin-1 is not valid UTF-8 (0xe9 is a lone byte).
    raw = "café".encode("latin-1")

    parsed = parse_txt(raw)

    assert parsed.text == "café"


def test_parse_txt_rejects_empty_file() -> None:
    with pytest.raises(ParseError):
        parse_txt(b"")


def test_parse_pdf_extracts_text_and_page_numbers() -> None:
    raw = build_minimal_pdf(["Page one text", "Page two text"])

    parsed = parse_pdf(raw, max_pages=300)

    assert "Page one text" in parsed.text
    assert "Page two text" in parsed.text
    assert [page.page_number for page in parsed.pages] == [1, 2]
    for page in parsed.pages:
        assert parsed.text[page.char_start : page.char_end]


def test_parse_pdf_with_no_extractable_text_raises() -> None:
    raw = build_minimal_pdf(["", ""])  # pages exist, but carry no text (image-only, in effect)

    with pytest.raises(ParseError, match="no extractable text"):
        parse_pdf(raw, max_pages=300)


def test_parse_pdf_over_page_limit_raises() -> None:
    raw = build_minimal_pdf(["one", "two", "three"])

    with pytest.raises(ParseError, match="page limit"):
        parse_pdf(raw, max_pages=2)


def test_parse_pdf_rejects_garbage_bytes() -> None:
    with pytest.raises(ParseError):
        parse_pdf(b"this is not a pdf at all", max_pages=300)
