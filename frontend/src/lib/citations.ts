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

/** Prefer exact chunk offsets in the full document; fall back to snippet search. */
export function resolveHighlightRange(
  text: string,
  options: {
    snippet?: string;
    charStart?: number | null;
    charEnd?: number | null;
    /** When highlighting inside a chunk (not full doc), search the snippet only. */
    preferSnippet?: boolean;
  },
): { start: number; end: number } | null {
  if (options.preferSnippet) {
    return findSnippetOffsets(text, options.snippet ?? "");
  }
  if (
    options.charStart != null &&
    options.charEnd != null &&
    options.charStart >= 0 &&
    options.charEnd > options.charStart &&
    options.charEnd <= text.length
  ) {
    return { start: options.charStart, end: options.charEnd };
  }
  return findSnippetOffsets(text, options.snippet ?? "");
}

// Finds the cited snippet inside its chunk so the drawer can highlight just
// that sentence. Tries exact, whitespace-normalised, and shrinking windows.
export function findSnippetOffsets(
  chunkText: string,
  snippet: string,
): { start: number; end: number } | null {
  const trimmed = snippet.replace(/…/g, "").trim();
  if (trimmed === "") return null;

  const exact = chunkText.indexOf(trimmed);
  if (exact !== -1) return { start: exact, end: exact + trimmed.length };

  const collapsedHay = collapseWhitespace(chunkText);
  const collapsedNeedle = collapseWhitespace(trimmed);
  const collapsedAt = collapsedHay.indexOf(collapsedNeedle);
  if (collapsedAt !== -1) {
    return mapCollapsedOffsets(chunkText, collapsedAt, collapsedNeedle.length);
  }

  // Try progressively shorter prefixes of the snippet (first sentence / clause).
  for (const length of [180, 120, 80, 40]) {
    if (collapsedNeedle.length <= length) continue;
    const short = collapsedNeedle.slice(0, length);
    const at = collapsedHay.indexOf(short);
    if (at !== -1) return mapCollapsedOffsets(chunkText, at, short.length);
  }
  return null;
}

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function mapCollapsedOffsets(
  original: string,
  collapsedStart: number,
  collapsedLength: number,
): { start: number; end: number } {
  let originalIndex = 0;
  let collapsedIndex = 0;
  let start = 0;
  let end = original.length;

  // Skip leading whitespace the same way collapseWhitespace did.
  while (originalIndex < original.length && /\s/.test(original[originalIndex] ?? "")) {
    originalIndex += 1;
  }

  while (originalIndex < original.length && collapsedIndex < collapsedStart + collapsedLength) {
    const char = original[originalIndex] ?? "";
    if (/\s/.test(char)) {
      // One collapsed space may represent many original whitespace chars.
      while (originalIndex < original.length && /\s/.test(original[originalIndex] ?? "")) {
        originalIndex += 1;
      }
      if (collapsedIndex === collapsedStart) start = originalIndex;
      collapsedIndex += 1;
      continue;
    }
    if (collapsedIndex === collapsedStart) start = originalIndex;
    originalIndex += 1;
    collapsedIndex += 1;
    if (collapsedIndex === collapsedStart + collapsedLength) {
      end = originalIndex;
      break;
    }
  }
  if (end <= start) end = Math.min(original.length, start + collapsedLength);
  return { start, end };
}
