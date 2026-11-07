"use client";

import { useEffect, useRef } from "react";

import { splitForHighlight } from "@/lib/citations";
import { parseDocumentBlocks, sanitizeDocumentText, type DocumentBlock } from "@/lib/documentText";
import { cn } from "@/lib/utils";

interface DocumentTextViewProps {
  text: string;
  highlightStart?: number | null;
  highlightEnd?: number | null;
  className?: string;
}

/** Structured layout for extracted PDF/plain text (source drawer + doc dialog). */
export function DocumentTextView({
  text,
  highlightStart = null,
  highlightEnd = null,
  className,
}: DocumentTextViewProps) {
  const sanitized = sanitizeDocumentText(text);
  const blocks = parseDocumentBlocks(sanitized);
  const markRef = useRef<HTMLElement>(null);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [sanitized, highlightStart, highlightEnd]);

  if (blocks.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No extractable text in this document.</p>
    );
  }

  return (
    <div className={cn("grid w-full gap-3 text-[0.95rem] leading-relaxed", className)}>
      {blocks.map((block, index) => (
        <BlockView
          key={`${block.kind}-${block.start}-${index}`}
          block={block}
          rangeStart={highlightStart}
          rangeEnd={highlightEnd}
          markRef={markRef}
        />
      ))}
    </div>
  );
}

function BlockView({
  block,
  rangeStart,
  rangeEnd,
  markRef,
}: {
  block: DocumentBlock;
  rangeStart: number | null;
  rangeEnd: number | null;
  markRef: React.RefObject<HTMLElement | null>;
}) {
  if (block.kind === "page") {
    return (
      <div className="flex items-center gap-3 py-1">
        <span className="h-px flex-1 bg-border/70" />
        <span className="rounded-full border border-border/70 bg-muted/50 px-2.5 py-0.5 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase">
          Page {block.page}
        </span>
        <span className="h-px flex-1 bg-border/70" />
      </div>
    );
  }

  if (block.kind === "heading") {
    return (
      <h3 className="font-heading pt-2 text-base font-semibold tracking-tight text-foreground first:pt-0">
        <HighlightedSlice
          text={block.text}
          absStart={block.start}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          markRef={markRef}
        />
      </h3>
    );
  }

  if (block.kind === "kv") {
    return (
      <div className="grid gap-1 rounded-xl border border-border/60 bg-card/50 px-3 py-2.5 sm:grid-cols-[minmax(9rem,14rem)_minmax(0,1fr)] sm:items-start sm:gap-4">
        <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {block.label}
        </div>
        <div className="min-w-0 font-medium break-words">
          <HighlightedSlice
            text={block.value}
            absStart={block.valueStart}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            markRef={markRef}
          />
        </div>
      </div>
    );
  }

  if (block.kind === "toc") {
    return (
      <div className="flex items-baseline gap-3 border-b border-dashed border-border/50 py-1.5">
        <span className="w-7 shrink-0 text-sm font-semibold text-ring tabular-nums">
          {block.index}
        </span>
        <span className="min-w-0 flex-1 break-words">
          <HighlightedSlice
            text={block.title}
            absStart={block.start}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            markRef={markRef}
          />
        </span>
        <span className="shrink-0 pl-2 font-mono text-xs tabular-nums text-muted-foreground">
          {block.page}
        </span>
      </div>
    );
  }

  return (
    <p className="max-w-none break-words text-foreground/95">
      <HighlightedSlice
        text={block.text}
        absStart={block.start}
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        markRef={markRef}
      />
    </p>
  );
}

function HighlightedSlice({
  text,
  absStart,
  rangeStart,
  rangeEnd,
  markRef,
}: {
  text: string;
  absStart: number;
  rangeStart: number | null;
  rangeEnd: number | null;
  markRef: React.RefObject<HTMLElement | null>;
}) {
  let localStart: number | null = null;
  let localEnd: number | null = null;
  if (rangeStart !== null && rangeEnd !== null) {
    const overlapStart = Math.max(rangeStart, absStart);
    const overlapEnd = Math.min(rangeEnd, absStart + text.length);
    if (overlapEnd > overlapStart) {
      localStart = overlapStart - absStart;
      localEnd = overlapEnd - absStart;
    }
  }

  const { before, highlighted, after } = splitForHighlight(text, localStart, localEnd);
  return (
    <>
      {before}
      {highlighted ? (
        <mark
          ref={markRef}
          className="rounded-sm bg-amber-200/90 px-0.5 font-medium text-foreground shadow-[inset_0_-2px_0_0_rgba(180,83,9,0.35)] dark:bg-amber-400/30 dark:text-amber-50"
        >
          {highlighted}
        </mark>
      ) : null}
      {after}
    </>
  );
}
