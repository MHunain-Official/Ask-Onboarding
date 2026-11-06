"use client";

import { useEffect, useRef } from "react";

import { splitForHighlight } from "@/lib/citations";

interface HighlightedTextProps {
  text: string;
  start: number | null;
  end: number | null;
}

// Plain text with one <mark>ed passage. Rendered as text nodes only (never
// as HTML), so a malicious document cannot inject markup (§3.2, §5.12 #36).
export function HighlightedText({ text, start, end }: HighlightedTextProps) {
  const markRef = useRef<HTMLElement>(null);
  const { before, highlighted, after } = splitForHighlight(text, start, end);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center" });
  }, [text, start, end]);

  return (
    <p className="font-serif text-[0.95rem] leading-relaxed whitespace-pre-wrap break-words">
      {before}
      {highlighted ? (
        <mark ref={markRef} className="rounded-sm bg-highlight px-0.5 text-highlight-foreground">
          {highlighted}
        </mark>
      ) : null}
      {after}
    </p>
  );
}
