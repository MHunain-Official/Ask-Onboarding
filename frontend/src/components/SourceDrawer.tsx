"use client";

import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HighlightedText } from "@/components/HighlightedText";
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
import { findSnippetOffsets } from "@/lib/citations";
import type { Chunk, Citation, DocumentContent } from "@/lib/types";

type LoadState<T> =
  | { kind: "loading" }
  | { kind: "gone" } // 404: the source was updated or removed (§5.12 #20)
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
      <SheetContent className="w-full gap-0 sm:max-w-xl">
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
          Source [{citation.n}]{where ? ` · ${where}` : ""}
        </SheetDescription>
      </SheetHeader>

      <Tabs
        defaultValue="passage"
        onValueChange={(value) => value === "document" && loadDocument()}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList variant="line" className="px-4 pt-2">
          <TabsTrigger value="passage">Passage</TabsTrigger>
          <TabsTrigger value="document">Full document</TabsTrigger>
        </TabsList>
        <TabsContent value="passage" className="overflow-y-auto p-4">
          <PassagePanel state={chunk} snippet={citation.snippet} />
        </TabsContent>
        <TabsContent value="document" className="overflow-y-auto p-4">
          <DocumentPanel state={document} />
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

function PassagePanel({ state, snippet }: { state: LoadState<Chunk>; snippet: string }) {
  if (state.kind === "loading") return <Skeleton lines={6} />;
  if (state.kind === "gone") return <GoneNotice />;
  if (state.kind === "error") return <ErrorBanner message="We couldn't load this passage." />;
  const offsets = findSnippetOffsets(state.value.text, snippet);
  return (
    <HighlightedText
      text={state.value.text}
      start={offsets?.start ?? 0}
      end={offsets?.end ?? state.value.text.length}
    />
  );
}

function DocumentPanel({ state }: { state: LoadState<DocumentContent> | null }) {
  if (state === null || state.kind === "loading") return <Skeleton lines={10} />;
  if (state.kind === "gone") return <GoneNotice />;
  if (state.kind === "error") return <ErrorBanner message="We couldn't load the document." />;
  const { value } = state;
  return (
    <div className="grid gap-2">
      {value.highlight_page ? (
        <p className="text-xs text-muted-foreground">
          The cited passage is on page {value.highlight_page} (extracted text shown).
        </p>
      ) : null}
      <HighlightedText
        text={value.text}
        start={value.highlight_char_start}
        end={value.highlight_char_end}
      />
    </div>
  );
}
