"use client";

import ReactMarkdown from "react-markdown";

import { CitationChip } from "@/components/CitationChip";
import { citationNumberFromHref, linkCitations } from "@/lib/citations";
import type { Citation } from "@/lib/types";

interface SafeMarkdownProps {
  text: string;
  citations: Citation[];
  onOpenCitation: (citation: Citation) => void;
}

// Renders model output as markdown. react-markdown never emits raw HTML
// (it has no dangerouslySetInnerHTML path unless a plugin is added), so
// model text cannot inject markup (AGENTS.md §3.2 rule 5).
export function SafeMarkdown({ text, citations, onOpenCitation }: SafeMarkdownProps) {
  return (
    <ReactMarkdown
      components={{
        a({ href, children }) {
          const n = citationNumberFromHref(href);
          const citation = citations.find((candidate) => candidate.n === n);
          if (citation) return <CitationChip citation={citation} onOpen={onOpenCitation} />;
          // Real links from the model open safely in a new tab.
          return (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              {children}
            </a>
          );
        },
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => (
          <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
        ),
        code: ({ children }) => (
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
        ),
        pre: ({ children }) => (
          <pre className="mb-3 overflow-x-auto rounded-md bg-muted p-3 font-mono text-sm">
            {children}
          </pre>
        ),
      }}
    >
      {linkCitations(text, citations)}
    </ReactMarkdown>
  );
}
