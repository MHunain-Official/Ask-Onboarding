import { describe, expect, it } from "vitest";

import {
  citationNumberFromHref,
  findSnippetOffsets,
  linkCitations,
  splitForHighlight,
} from "@/lib/citations";
import type { Citation } from "@/lib/types";

function makeCitation(n: number): Citation {
  return {
    n,
    chunk_id: `c${n}`,
    document_id: "d",
    filename: "f.md",
    page: null,
    heading: null,
    snippet: "",
  };
}

describe("linkCitations", () => {
  it("links only numbers the server cited", () => {
    const result = linkCitations("Use the VPN [1]. Also see [9].", [makeCitation(1)]);
    expect(result).toBe("Use the VPN [1](#cite-1). Also see [9].");
  });

  it("handles adjacent citations", () => {
    const result = linkCitations("Fact [1][2]", [makeCitation(1), makeCitation(2)]);
    expect(result).toBe("Fact [1](#cite-1)[2](#cite-2)");
  });
});

describe("citationNumberFromHref", () => {
  it("reads the number from a citation link", () => {
    expect(citationNumberFromHref("#cite-3")).toBe(3);
  });

  it("returns null for ordinary links", () => {
    expect(citationNumberFromHref("https://example.com")).toBeNull();
    expect(citationNumberFromHref(undefined)).toBeNull();
  });
});

describe("splitForHighlight", () => {
  it("splits text around the highlighted range", () => {
    expect(splitForHighlight("abcdef", 2, 4)).toEqual({
      before: "ab",
      highlighted: "cd",
      after: "ef",
    });
  });

  it("gives no highlight for out-of-range offsets", () => {
    expect(splitForHighlight("abc", 2, 10).highlighted).toBe("");
    expect(splitForHighlight("abc", null, null).before).toBe("abc");
  });
});

describe("findSnippetOffsets", () => {
  it("finds the snippet inside the chunk, ignoring ellipses", () => {
    expect(findSnippetOffsets("Hello big world", "…big world…")).toEqual({
      start: 6,
      end: 15,
    });
  });

  it("returns null when the snippet is not in the chunk", () => {
    expect(findSnippetOffsets("Hello", "nope")).toBeNull();
  });
});
