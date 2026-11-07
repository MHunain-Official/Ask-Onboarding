"use client";

import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { DocumentTextView } from "@/components/DocumentTextView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, getChunk, getDocumentContent } from "@/lib/api";
import { resolveHighlightRange } from "@/lib/citations";
import { sanitizeDocumentText } from "@/lib/documentText";
import type { Chunk, Citation, DocumentContent } from "@/lib/types";

type LoadState<T> =
  | { kind: "loading" }
  | { kind: "gone" }
  | { kind: "error" }
  | { kind: "ready"; value: T };

function toLoadError(error: unknown): { kind: "gone" } | { kind: "error" } {
  return error instanceof ApiError && error.status === 404 ? { kind: "gone" } : { kind: "error" };
}

interface SourceDrawerProps {
  citation: Citation | null;
  onClose: () => void;
}

export function SourceDrawer({ citation, onClose }: SourceDrawerProps) {
  return (
    <Sheet open={citation !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-2xl lg:max-w-3xl">
        {citation ? <DrawerBody key={citation.chunk_id} citation={citation} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function DrawerBody({ citation }: { citation: Citation }) {
  const [chunk, setChunk] = useState<LoadState<Chunk>>({ kind: "loading" });
  const [document, setDocument] = useState<LoadState<DocumentContent> | null>(null);

  useEffect(() => {
    let cancelled = false;
    getChunk(citation.chunk_id)
      .then((value) => !cancelled && setChunk({ kind: "ready", value }))
      .catch((error: unknown) => !cancelled && setChunk(toLoadError(error)));
    return () => {
      cancelled = true;
    };
  }, [citation.chunk_id]);

  function loadDocument() {
    if (document) return;
    setDocument({ kind: "loading" });
    getDocumentContent(citation.document_id, citation.chunk_id)
      .then((value) => setDocument({ kind: "ready", value }))
      .catch((error: unknown) => setDocument(toLoadError(error)));
  }

  const where = [citation.page ? `Page ${citation.page}` : null, citation.heading]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <SheetHeader className="border-b pr-12">
        <SheetTitle className="flex items-center gap-2">
          <FileText className="size-4 shrink-0 text-ring" aria-hidden="true" />
          <span className="truncate">{citation.filename}</span>
        </SheetTitle>
        <SheetDescription>
          Source [{citation.n}]{where ? ` · ${where}` : ""} · cited passage highlighted
        </SheetDescription>
      </SheetHeader>

      <Tabs
        defaultValue="passage"
        onValueChange={(value) => value === "document" && loadDocument()}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList variant="line" className="w-full justify-start px-4 pt-2">
          <TabsTrigger value="passage">Cited passage</TabsTrigger>
          <TabsTrigger value="document">Full document</TabsTrigger>
        </TabsList>
        <TabsContent value="passage" className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          <PassagePanel state={chunk} citation={citation} />
        </TabsContent>
        <TabsContent value="document" className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
          <DocumentPanel state={document} citation={citation} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function GoneNotice() {
  return (
    <ErrorBanner message="This source has been updated or removed since the answer was written. Ask the question again to get the current answer." />
  );
}

function PassagePanel({ state, citation }: { state: LoadState<Chunk>; citation: Citation }) {
  if (state.kind === "loading") return <Skeleton lines={6} />;
  if (state.kind === "gone") return <GoneNotice />;
  if (state.kind === "error") return <ErrorBanner message="We couldn't load this passage." />;

  const cleaned = sanitizeDocumentText(state.value.text);
  const offsets = resolveHighlightRange(cleaned, {
    snippet: sanitizeDocumentText(citation.snippet),
    preferSnippet: true,
  });

  return (
    <div className="grid gap-4">
      <p className="text-xs font-medium tracking-wide text-ring uppercase">Exact passage used</p>
      <DocumentTextView
        text={state.value.text}
        highlightStart={offsets?.start ?? 0}
        highlightEnd={offsets?.end ?? cleaned.length}
      />
    </div>
  );
}

function DocumentPanel({
  state,
  citation,
}: {
  state: LoadState<DocumentContent> | null;
  citation: Citation;
}) {
  if (state === null || state.kind === "loading") return <Skeleton lines={10} />;
  if (state.kind === "gone") return <GoneNotice />;
  if (state.kind === "error") return <ErrorBanner message="We couldn't load the document." />;
  const { value } = state;
  const cleaned = sanitizeDocumentText(value.text);
  const offsets = resolveHighlightRange(cleaned, {
    snippet: sanitizeDocumentText(citation.snippet),
    charStart: value.highlight_char_start ?? citation.char_start,
    charEnd: value.highlight_char_end ?? citation.char_end,
  });
  return (
    <div className="grid gap-4">
      {value.highlight_page ? (
        <p className="text-xs text-muted-foreground">
          The cited passage is on page {value.highlight_page} (extracted text shown).
        </p>
      ) : (
        <p className="text-xs font-medium tracking-wide text-ring uppercase">
          Highlighted region from this answer
        </p>
      )}
      <DocumentTextView
        text={value.text}
        highlightStart={offsets?.start ?? null}
        highlightEnd={offsets?.end ?? null}
      />
    </div>
  );
}
