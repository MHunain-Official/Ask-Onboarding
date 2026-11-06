// Helpers for showing citations safely.

import type { Citation } from "@/lib/types";

const CITATION_PATTERN = /\[(\d{1,3})\]/g;

// Prefix of the markdown link target we use to mark a citation. The
// markdown renderer turns these links into CitationChip buttons.
export const CITATION_HREF_PREFIX = "#cite-";

// Replaces "[2]" with a markdown link "[2](#cite-2)", but only for numbers the
// server actually sent a citation for. Unknown numbers stay as plain text.
export function linkCitations(text: string, citations: Citation[]): string {
  const known = new Set(citations.map((citation) => citation.n));
  return text.replace(CITATION_PATTERN, (match, digits: string) => {
    const n = Number(digits);
    return known.has(n) ? `[${n}](${CITATION_HREF_PREFIX}${n})` : match;
  });
}

export function citationNumberFromHref(href: string | undefined): number | null {
  if (!href?.startsWith(CITATION_HREF_PREFIX)) return null;
  const n = Number(href.slice(CITATION_HREF_PREFIX.length));
  return Number.isInteger(n) ? n : null;
}

export interface HighlightParts {
  before: string;
  highlighted: string;
  after: string;
}

// Splits text so the middle part can be wrapped in <mark>. Offsets outside
// the text (for example after the document changed) give no highlight.
export function splitForHighlight(
  text: string,
  start: number | null,
  end: number | null,
): HighlightParts {
  const valid = start !== null && end !== null && start >= 0 && end > start && end <= text.length;
  if (!valid) return { before: text, highlighted: "", after: "" };
  return {
    before: text.slice(0, start),
    highlighted: text.slice(start, end),
    after: text.slice(end),
  };
}

// Finds the cited snippet inside its chunk so the drawer can highlight just
// that sentence. Falls back to no highlight if the snippet is not found.
export function findSnippetOffsets(
  chunkText: string,
  snippet: string,
): { start: number; end: number } | null {
  const trimmed = snippet.replace(/…$/, "").replace(/^…/, "").trim();
  if (trimmed === "") return null;
  const start = chunkText.indexOf(trimmed);
  if (start === -1) return null;
  return { start, end: start + trimmed.length };
}
