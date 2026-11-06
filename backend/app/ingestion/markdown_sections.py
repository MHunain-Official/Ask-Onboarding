"""Cut markdown text into sections at heading lines, remembering each
section's heading path ("IT > VPN > Setup" — §5.2) so the chunker can
prepend it to every chunk drawn from that section.
"""

import re
from dataclasses import dataclass

_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)


@dataclass
class Section:
    """A contiguous span of `char_start:char_end` in the original text,
    labelled with the heading path it falls under (`None` for plain text or
    for text before the first heading)."""

    heading: str | None
    char_start: int
    char_end: int


def split_into_sections(text: str, *, is_markdown: bool) -> list[Section]:
    """Plain text is always a single, headingless section. Markdown is cut
    at each `#`..`######` line; nested headings build a path like
    "IT > VPN > Setup" by tracking which ancestor headings are still open."""
    if not is_markdown:
        return [Section(heading=None, char_start=0, char_end=len(text))]

    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        return [Section(heading=None, char_start=0, char_end=len(text))]

    sections: list[Section] = []

    # Preamble text before the first heading (e.g. a title line) still needs
    # a home, so it becomes its own headingless section.
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        sections.append(Section(heading=None, char_start=0, char_end=matches[0].start()))

    stack: list[tuple[int, str]] = []  # (heading level, title), outermost first
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        stack = [item for item in stack if item[0] < level]
        stack.append((level, title))
        heading_path = " > ".join(title for _, title in stack)

        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append(
            Section(heading=heading_path, char_start=content_start, char_end=content_end)
        )

    return sections
