import { describe, expect, it } from "vitest";

import { parseDocumentBlocks, sanitizeDocumentText } from "@/lib/documentText";

describe("sanitizeDocumentText", () => {
  it("replaces private-use junk with bullets without changing length", () => {
    const raw = `Hello\uE000world\uFFFD!`;
    const cleaned = sanitizeDocumentText(raw);
    expect(cleaned.length).toBe(raw.length);
    expect(cleaned).toBe("Hello•world•!");
  });
});

describe("parseDocumentBlocks", () => {
  it("formats document-control key/value rows", () => {
    const text = [
      "Name of Document Human Resources Policy Manual",
      "Recommended By HR Committee",
      "Approved By Board of Directors",
    ].join("\n");
    const blocks = parseDocumentBlocks(text);
    expect(blocks.filter((block) => block.kind === "kv")).toHaveLength(3);
    expect(blocks[0]).toMatchObject({
      kind: "kv",
      label: "Name of Document",
      value: "Human Resources Policy Manual",
    });
  });

  it("formats table-of-contents rows with right-aligned page numbers", () => {
    const text = ["1 Document Control 3", "2 Changes in Policies Manual 4", "3 Definitions 5-6"].join(
      "\n",
    );
    const blocks = parseDocumentBlocks(text);
    expect(blocks.every((block) => block.kind === "toc")).toBe(true);
    expect(blocks[1]).toMatchObject({
      kind: "toc",
      index: "2",
      title: "Changes in Policies Manual",
      page: "4",
    });
  });

  it("turns lone page numbers into page markers", () => {
    const blocks = parseDocumentBlocks("Title\n1\nBody text here.");
    expect(blocks.some((block) => block.kind === "page" && block.page === "1")).toBe(true);
  });
});
