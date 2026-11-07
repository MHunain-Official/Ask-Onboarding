import { describe, expect, it } from "vitest";

import { isExternalHref, resolveInternalDocPath } from "@/lib/docLinks";

describe("resolveInternalDocPath", () => {
  it("resolves docs/threat-model.md from the repo root", () => {
    expect(resolveInternalDocPath("SECURITY.md", "docs/threat-model.md")).toBe(
      "docs/threat-model.md",
    );
  });

  it("resolves ../SECURITY.md from a nested doc", () => {
    expect(resolveInternalDocPath("docs/runbook.md", "../SECURITY.md")).toBe("SECURITY.md");
  });

  it("resolves nested ADR links from ARCHITECTURE.md", () => {
    expect(resolveInternalDocPath("ARCHITECTURE.md", "docs/adr/001-pgvector.md")).toBe(
      "docs/adr/001-pgvector.md",
    );
  });

  it("returns null for external and anchor-only links", () => {
    expect(resolveInternalDocPath("README.md", "https://example.com")).toBeNull();
    expect(resolveInternalDocPath("README.md", "#section")).toBeNull();
  });
});

describe("isExternalHref", () => {
  it("detects http and mailto", () => {
    expect(isExternalHref("https://x.test")).toBe(true);
    expect(isExternalHref("mailto:a@b.c")).toBe(true);
    expect(isExternalHref("docs/eval.md")).toBe(false);
  });
});
