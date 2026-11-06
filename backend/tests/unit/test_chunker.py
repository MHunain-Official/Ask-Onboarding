"""Chunker tests (AGENTS.md §9 and §5.2's invariants): target size and
overlap, offset round-trip, heading path, short documents, unicode text,
and never losing or dropping any text. No API keys needed.
"""

from app.ingestion.chunker import split_text_into_chunks


def test_short_document_is_a_single_chunk() -> None:
    text = "Just a short note about the office wifi password."

    chunks = split_text_into_chunks(text, target_tokens=500, overlap_tokens=80)

    assert len(chunks) == 1
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)
    assert chunks[0].text == text
    assert chunks[0].heading is None


def test_empty_text_produces_no_chunks() -> None:
    assert split_text_into_chunks("   \n\n  ", target_tokens=500, overlap_tokens=80) == []


def test_offsets_round_trip_to_the_original_text() -> None:
    text = "\n\n".join(
        f"Paragraph number {i} has several words in it to pad it out nicely." for i in range(20)
    )

    chunks = split_text_into_chunks(text, target_tokens=20, overlap_tokens=5)

    assert len(chunks) > 1
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text


def test_no_chunk_is_ever_empty() -> None:
    text = "\n\n".join(f"Sentence {i}. Another sentence right here." for i in range(30))

    chunks = split_text_into_chunks(text, target_tokens=15, overlap_tokens=3)

    assert chunks
    assert all(chunk.text.strip() for chunk in chunks)


def test_chunks_cover_the_document_with_no_gaps() -> None:
    text = " ".join(f"word{i}" for i in range(300))

    chunks = split_text_into_chunks(text, target_tokens=20, overlap_tokens=5)

    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        # No gap between consecutive chunks: every character is covered by
        # at least one chunk, so no text is ever lost.
        assert current.char_start <= previous.char_end


def test_overlap_is_present_between_consecutive_chunks() -> None:
    text = " ".join(f"word{i}" for i in range(300))

    chunks = split_text_into_chunks(text, target_tokens=20, overlap_tokens=10)

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.char_start < previous.char_end


def test_no_overlap_when_overlap_tokens_is_zero() -> None:
    text = " ".join(f"word{i}" for i in range(300))

    chunks = split_text_into_chunks(text, target_tokens=20, overlap_tokens=0)

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.char_start == previous.char_end


def test_heading_path_is_attached_and_prepended() -> None:
    text = (
        "# IT\n\n"
        "## VPN\n\n"
        "### Setup\n\n"
        "Install the client and log in with your company email address.\n"
    )

    chunks = split_text_into_chunks(text, target_tokens=500, overlap_tokens=0, is_markdown=True)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.heading == "IT > VPN > Setup"
    assert chunk.text.startswith("IT > VPN > Setup\n\n")
    body = chunk.text.removeprefix(f"{chunk.heading}\n\n")
    assert text[chunk.char_start : chunk.char_end] == body


def test_heading_path_resets_on_sibling_sections() -> None:
    text = "# IT\n\n## VPN\n\nVPN content here.\n\n## Email\n\nEmail content here.\n"

    chunks = split_text_into_chunks(text, target_tokens=500, overlap_tokens=0, is_markdown=True)

    headings = [chunk.heading for chunk in chunks]
    assert "IT > VPN" in headings
    assert "IT > Email" in headings


def test_non_markdown_text_ignores_hash_characters() -> None:
    text = "# This is not a heading, just a sentence with a # in it.\n\nMore text follows here."

    chunks = split_text_into_chunks(text, target_tokens=500, overlap_tokens=0, is_markdown=False)

    assert len(chunks) == 1
    assert chunks[0].heading is None


def test_unicode_text_is_split_safely() -> None:
    text = "\n\n".join(
        f"Párrafo número {i} con palabras en español y un emoji 😀 incluido." for i in range(20)
    )

    chunks = split_text_into_chunks(text, target_tokens=15, overlap_tokens=3)

    assert chunks
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text
    assert "😀" in " ".join(chunk.text for chunk in chunks)


def test_a_single_oversized_word_still_becomes_one_chunk() -> None:
    # No separator exists at all: the chunker must not loop forever or crash.
    text = "a" * 2000

    chunks = split_text_into_chunks(text, target_tokens=10, overlap_tokens=2)

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_chunk_token_count_stays_near_target() -> None:
    text = " ".join(f"word{i}" for i in range(500))

    chunks = split_text_into_chunks(text, target_tokens=30, overlap_tokens=0)

    for chunk in chunks[:-1]:  # the final chunk may legitimately be smaller
        assert chunk.token_count <= 30 * 1.5
