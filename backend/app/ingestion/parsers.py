"""Parse an uploaded file's raw bytes into plain text (AGENTS.md §5.1 step 4).

Each parser returns a `ParsedDocument`: the full text the chunker will split,
plus (for PDFs) a list of page markers so chunks can carry a `page_number`.
Markdown/text parsers have no pages, so `pages` is empty and the chunker
falls back to heading-based sectioning only.
"""

from dataclasses import dataclass, field
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class ParseError(Exception):
    """Raised when a file cannot be turned into usable text.

    The ingestion pipeline catches this, sets `documents.status=failed`,
    and stores `str(exc)` as the human-readable `error_message`.
    """


@dataclass
class PageMarker:
    """Where one PDF page's text starts/ends within the full parsed text."""

    page_number: int
    char_start: int
    char_end: int


@dataclass
class ParsedDocument:
    """The result of parsing one uploaded file."""

    text: str
    pages: list[PageMarker] = field(default_factory=list)


def parse_markdown(raw_bytes: bytes) -> ParsedDocument:
    """Markdown is parsed as decoded text; heading splitting happens later,
    in the chunker, which needs the raw `#`/`##` markers intact."""
    text = _decode_text(raw_bytes)
    _require_non_empty(text)
    return ParsedDocument(text=text)


def parse_txt(raw_bytes: bytes) -> ParsedDocument:
    text = _decode_text(raw_bytes)
    _require_non_empty(text)
    return ParsedDocument(text=text)


def parse_pdf(raw_bytes: bytes, *, max_pages: int) -> ParsedDocument:
    """Extract text page by page so each chunk can record its `page_number`.

    A scanned/image-only PDF has pages but no extractable text — that is
    the single most common real-world ingestion failure, so it gets its
    own clear error message rather than silently producing an empty doc.
    """
    try:
        reader = PdfReader(BytesIO(raw_bytes))
    except PdfReadError as exc:
        raise ParseError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        raise ParseError("PDF is password-protected and cannot be read")

    if len(reader.pages) == 0:
        raise ParseError("PDF has no pages")

    if len(reader.pages) > max_pages:
        raise ParseError(f"PDF has {len(reader.pages)} pages, over the {max_pages} page limit")

    chunks_of_text: list[str] = []
    pages: list[PageMarker] = []
    cursor = 0
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - a single bad page must not crash ingestion
            raise ParseError(f"Could not extract text from page {index}: {exc}") from exc
        page_text = page_text.strip()
        if not page_text:
            continue
        if chunks_of_text:
            # Separate pages with a blank line so the chunker treats them as
            # distinct paragraphs, never merging the last word of one page
            # into the first word of the next.
            chunks_of_text.append("\n\n")
            cursor += 2
        start = cursor
        chunks_of_text.append(page_text)
        cursor += len(page_text)
        pages.append(PageMarker(page_number=index, char_start=start, char_end=cursor))

    full_text = "".join(chunks_of_text)
    _require_non_empty(full_text, message="PDF has no extractable text (scanned/image-only?)")
    return ParsedDocument(text=full_text, pages=pages)


def parse_by_filename(filename: str, raw_bytes: bytes, *, max_pages: int) -> ParsedDocument:
    """Pick the right parser from the file's extension. The single place
    both the ingestion pipeline and the document-content endpoint call, so
    a citation's highlighted passage is always computed from the exact same
    parsed text the chunker originally split."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return parse_pdf(raw_bytes, max_pages=max_pages)
    if lowered.endswith(".md"):
        return parse_markdown(raw_bytes)
    return parse_txt(raw_bytes)


def _decode_text(raw_bytes: bytes) -> str:
    """UTF-8 first; latin-1 never fails (every byte is a valid code point)
    so it is the documented fallback for files with an unknown encoding."""
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")


def _require_non_empty(text: str, *, message: str = "Document has no extractable text") -> None:
    if not text.strip():
        raise ParseError(message)
