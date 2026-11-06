"use client";

import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HighlightedText } from "@/components/HighlightedText";
import { Skeleton } from "@/components/Skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, getDocumentContent } from "@/lib/api";
import type { DocumentContent, DocumentItem } from "@/lib/types";

export function DocumentViewDialog({
  document,
  onClose,
}: {
  document: DocumentItem | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={document !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl">
        {document ? <Body key={document.id} document={document} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function Body({ document }: { document: DocumentItem }) {
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocumentContent(document.id)
      .then((value) => !cancelled && setContent(value))
      .catch((caught: unknown) => {
        if (cancelled) return;
        const gone = caught instanceof ApiError && caught.status === 404;
        setError(gone ? "This document was removed." : "We couldn't load this document.");
      });
    return () => {
      cancelled = true;
    };
  }, [document.id]);

  return (
    <>
      <DialogHeader>
        <DialogTitle>{document.filename}</DialogTitle>
        <DialogDescription>Version {document.version} · extracted text</DialogDescription>
      </DialogHeader>
      {error ? (
        <ErrorBanner message={error} />
      ) : content ? (
        <HighlightedText text={content.text} start={null} end={null} />
      ) : (
        <Skeleton lines={8} />
      )}
    </>
  );
}
