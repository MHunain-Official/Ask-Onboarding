import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CitationChip } from "@/components/CitationChip";
import type { Citation } from "@/lib/types";

const citation: Citation = {
  n: 2,
  chunk_id: "chunk-1",
  document_id: "doc-1",
  filename: "vpn-guide.md",
  page: 3,
  heading: "VPN > Setup",
  snippet: "Install the client.",
};

afterEach(cleanup);

describe("CitationChip", () => {
  it("shows the citation number with an accessible name that includes the file", () => {
    render(<CitationChip citation={citation} onOpen={() => undefined} />);
    const button = screen.getByRole("button", {
      name: "Source 2: vpn-guide.md, page 3",
    });
    expect(button.textContent).toBe("2");
  });

  it("calls onOpen with the citation when clicked", () => {
    const onOpen = vi.fn();
    render(<CitationChip citation={citation} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledWith(citation);
  });
});
