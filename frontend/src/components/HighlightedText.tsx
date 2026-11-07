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
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [text, start, end]);

  return (
    <p className="font-serif text-[0.95rem] leading-relaxed whitespace-pre-wrap break-words">
      {before}
      {highlighted ? (
        <mark
          ref={markRef}
          className="rounded-sm bg-amber-200/90 px-0.5 font-medium text-ink shadow-[inset_0_-2px_0_0_rgba(180,83,9,0.35)] dark:bg-amber-400/30 dark:text-amber-50"
        >
          {highlighted}
        </mark>
      ) : null}
      {after}
    </p>
  );
}
