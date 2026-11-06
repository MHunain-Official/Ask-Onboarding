"use client";

import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";

import { CitationChip } from "@/components/CitationChip";
import { ErrorBanner } from "@/components/ErrorBanner";
import { SafeMarkdown } from "@/components/SafeMarkdown";
import { TicketOfferCard } from "@/components/TicketOfferCard";
import { Button } from "@/components/ui/button";
import type { ChatItem } from "@/hooks/useChatStream";
import { formatDate } from "@/lib/format";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  item: ChatItem;
  conversationId: string | null;
  onOpenCitation: (citation: Citation) => void;
  onRetry: (assistantId: string) => void;
  onRegenerate: (assistantId: string) => void;
}

export function ChatMessage({
  item,
  conversationId,
  onOpenCitation,
  onRetry,
  onRegenerate,
}: ChatMessageProps) {
  if (item.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm whitespace-pre-wrap break-words text-primary-foreground">
          {item.content}
        </p>
      </div>
    );
  }
  return <AssistantMessage {...{ item, conversationId, onOpenCitation, onRetry, onRegenerate }} />;
}

function AssistantMessage({
  item,
  conversationId,
  onOpenCitation,
  onRetry,
  onRegenerate,
}: ChatMessageProps) {
  const streaming = item.status === "streaming";
  const hasText = item.content.length > 0;

  return (
    <article aria-label="Assistant answer" className="grid max-w-[90%] gap-3">
      {item.cachedAt ? (
        <p className="text-xs text-muted-foreground">
          Saved answer
          {item.cachedAt !== "saved" ? ` · ${formatDate(item.cachedAt)}` : ""}
        </p>
      ) : null}

      {hasText || streaming ? (
        // aria-live only while streaming, so finished messages are not re-announced.
        <div
          aria-live={streaming ? "polite" : "off"}
          aria-busy={streaming}
          className={cn(
            "rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-[0.95rem] leading-relaxed",
            streaming && "streaming-caret",
          )}
        >
          {hasText ? (
            <SafeMarkdown
              text={item.content}
              citations={item.citations}
              onOpenCitation={onOpenCitation}
            />
          ) : (
            <span className="text-muted-foreground">Searching the documents…</span>
          )}
        </div>
      ) : null}

      {item.status === "ungrounded" ? (
        <p
          role="note"
          className="rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-sm text-warning"
        >
          I couldn&apos;t verify this against the documents. Check the passages below before relying
          on it.
        </p>
      ) : null}
      {item.status === "partial" ? (
        <ErrorBanner message="This answer was interrupted." onRetry={() => onRetry(item.id)} />
      ) : null}
      {item.status === "error" ? (
        <ErrorBanner
          message={item.errorMessage ?? "Something went wrong."}
          requestId={item.requestId}
          onRetry={() => onRetry(item.id)}
        />
      ) : null}
      {item.status === "stopped" ? <p className="text-xs text-muted-foreground">Stopped.</p> : null}

      <SourceList citations={item.citations} onOpen={onOpenCitation} />

      {item.ticketOffer ? (
        <TicketOfferCard offer={item.ticketOffer} conversationId={conversationId} />
      ) : null}

      {!streaming && hasText ? (
        <MessageActions text={item.content} onRegenerate={() => onRegenerate(item.id)} />
      ) : null}
    </article>
  );
}

function SourceList({
  citations,
  onOpen,
}: {
  citations: Citation[];
  onOpen: (citation: Citation) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Sources
      </h3>
      <ul className="grid gap-1.5">
        {citations.map((citation) => (
          <li key={citation.n} className="flex items-start gap-2 text-sm">
            <CitationChip citation={citation} onOpen={onOpen} className="mt-0.5 translate-y-0" />
            <span className="min-w-0">
              <span className="font-medium">{citation.filename}</span>
              {citation.page ? (
                <span className="text-muted-foreground"> · p. {citation.page}</span>
              ) : null}
              {citation.heading ? (
                <span className="text-muted-foreground"> · {citation.heading}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MessageActions({ text, onRegenerate }: { text: string; onRegenerate: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex gap-1">
      <Button variant="ghost" size="sm" onClick={() => void copy()}>
        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
        {copied ? "Copied" : "Copy"}
      </Button>
      <Button variant="ghost" size="sm" onClick={onRegenerate}>
        <RotateCcw aria-hidden="true" />
        Regenerate
      </Button>
    </div>
  );
}
