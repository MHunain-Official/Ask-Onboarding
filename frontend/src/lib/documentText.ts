/** Clean and structure extracted PDF/plain text for the source drawer. */

export type DocumentBlock =
  | { kind: "page"; page: string; start: number; end: number }
  | { kind: "heading"; text: string; start: number; end: number }
  | {
      kind: "kv";
      label: string;
      value: string;
      start: number;
      end: number;
      /** Absolute start of `value` inside the full document text. */
      valueStart: number;
    }
  | { kind: "toc"; index: string; title: string; page: string; start: number; end: number }
  | { kind: "para"; text: string; start: number; end: number };

const KV_LABELS = [
  "Name of Document",
  "Recommended By",
  "Approved By",
  "Responsible Manager",
  "Prepared By",
  "Last Revision Date",
  "Distribution",
  "Document Number",
  "Version",
  "Effective Date",
  "Review Date",
];

/**
 * 1:1 character replacements so citation highlight offsets stay valid.
 * Also normalises common PDF extraction junk (private-use bullets, form feeds).
 */
export function sanitizeDocumentText(text: string): string {
  let out = "";
  for (const char of text) {
    const code = char.charCodeAt(0);
    if (char === "\f" || char === "\r") {
      out += "\n";
      continue;
    }
    // Private Use Area / replacement char → readable bullet, same length.
    if (char === "\uFFFD" || (code >= 0xe000 && code <= 0xf8ff)) {
      out += "•";
      continue;
    }
    // Other C0 controls except tab/newline → space.
    if (code < 32 && char !== "\n" && char !== "\t") {
      out += " ";
      continue;
    }
    out += char;
  }
  return out;
}

export function parseDocumentBlocks(text: string): DocumentBlock[] {
  const blocks: DocumentBlock[] = [];
  let offset = 0;
  const lines = text.split("\n");

  for (const rawLine of lines) {
    const start = offset;
    const end = offset + rawLine.length;
    offset = end + 1; // account for the '\n' (except past last line — still fine)

    const line = rawLine.replace(/\t+/g, "  ").trimEnd();
    const trimmed = line.trim();
    if (!trimmed) continue;
    // Point offsets at the trimmed content so highlights stay aligned.
    const contentStart = start + rawLine.indexOf(trimmed);
    const contentEnd = contentStart + trimmed.length;

    const pageOnly = /^\[?\s*page\s*[:.]?\s*(\d+)\s*\]?$/i.exec(trimmed);
    if (pageOnly) {
      blocks.push({ kind: "page", page: pageOnly[1], start: contentStart, end: contentEnd });
      continue;
    }
    if (/^\d{1,3}$/.test(trimmed) && trimmed.length <= 3) {
      blocks.push({ kind: "page", page: trimmed, start: contentStart, end: contentEnd });
      continue;
    }

    const toc = /^(\d{1,3})\s+(.+?)\s+(\d{1,3}(?:\s*[-–]\s*\d{1,3})?)\s*$/.exec(trimmed);
    if (toc && toc[2].length > 2 && !/^\d+$/.test(toc[2])) {
      blocks.push({
        kind: "toc",
        index: toc[1],
        title: toc[2].trim(),
        page: toc[3].replace(/\s+/g, ""),
        start: contentStart,
        end: contentEnd,
      });
      continue;
    }

    const kv = matchKeyValue(trimmed);
    if (kv) {
      const valueIndex = trimmed.indexOf(kv.value);
      const valueStart = valueIndex >= 0 ? contentStart + valueIndex : contentStart;
      blocks.push({
        kind: "kv",
        label: kv.label,
        value: kv.value,
        start: contentStart,
        end: contentEnd,
        valueStart,
      });
      continue;
    }

    if (looksLikeHeading(trimmed)) {
      blocks.push({
        kind: "heading",
        text: trimmed,
        start: contentStart,
        end: contentEnd,
      });
      continue;
    }

    blocks.push({ kind: "para", text: trimmed, start: contentStart, end: contentEnd });
  }

  return blocks;
}

function matchKeyValue(line: string): { label: string; value: string } | null {
  for (const label of KV_LABELS) {
    if (line.toLowerCase().startsWith(label.toLowerCase())) {
      const rest = line.slice(label.length).trim();
      if (rest.length > 0) return { label, value: rest };
    }
  }
  // Generic "Label: value" or "Label - value"
  const colon = /^([A-Z][A-Za-z0-9 /&-]{2,40})\s*[:：]\s+(.+)$/.exec(line);
  if (colon) return { label: colon[1].trim(), value: colon[2].trim() };
  return null;
}

function looksLikeHeading(line: string): boolean {
  if (line.length > 90) return false;
  if (/[.!?]$/.test(line)) return false;
  if (/^note\s*:/i.test(line)) return false;
  // ALL CAPS short line, or "Section # 1 - TITLE"
  if (/^section\s*#?\s*\d+/i.test(line)) return true;
  if (/^table of contents$/i.test(line)) return true;
  const letters = line.replace(/[^A-Za-z]/g, "");
  if (letters.length >= 4 && letters === letters.toUpperCase()) return true;
  return false;
}
