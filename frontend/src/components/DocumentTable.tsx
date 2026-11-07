"use client";

import { Eye, RefreshCw, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { StatusChip } from "@/components/StatusChip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import type { DocumentItem } from "@/lib/types";

interface DocumentTableProps {
  documents: DocumentItem[];
  canManage: boolean;
  onView: (document: DocumentItem) => void;
  onDelete: (document: DocumentItem) => Promise<void>;
  onReupload: (document: DocumentItem, file: File) => void;
}

function accessLabel(level: DocumentItem["access_level"]): string {
  if (level === "admins") return "Admins only";
  if (level === "managers") return "Managers only";
  return "Everyone";
}

function fileKind(contentType: string, filename: string): string {
  if (contentType.includes("pdf")) return "PDF";
  return filename.toLowerCase().endsWith(".md") ? "Markdown" : "Text";
}

export function DocumentTable({
  documents,
  canManage,
  onView,
  onDelete,
  onReupload,
}: DocumentTableProps) {
  const [toDelete, setToDelete] = useState<DocumentItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const reuploadTarget = useRef<DocumentItem | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    await onDelete(toDelete);
    setDeleting(false);
    setToDelete(null);
  }

  return (
    <>
      <input
        ref={fileInput}
        type="file"
        accept=".pdf,.md,.txt"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose a new version of the file"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file && reuploadTarget.current) onReupload(reuploadTarget.current, file);
          event.target.value = "";
        }}
      />
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Access</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Chunks</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((document) => (
              <TableRow key={document.id}>
                <TableCell className="max-w-64 whitespace-normal">
                  <span className="font-medium break-words">{document.filename}</span>
                  {document.status === "failed" ? (
                    <span className="mt-0.5 block text-xs text-destructive">
                      {document.error_message ?? "Processing failed."}
                      {document.version > 1 ? " The previous version is still active." : ""}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell>{fileKind(document.content_type, document.filename)}</TableCell>
                <TableCell>v{document.version}</TableCell>
                <TableCell>
                  <Badge variant={document.access_level === "all" ? "secondary" : "outline"}>
                    {accessLabel(document.access_level)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <StatusChip
                    status={document.status}
                    title={document.error_message ?? undefined}
                  />
                </TableCell>
                <TableCell className="text-right tabular-nums">{document.chunk_count}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {formatDateTime(document.updated_at)}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`View ${document.filename}`}
                      onClick={() => onView(document)}
                    >
                      <Eye aria-hidden="true" />
                    </Button>
                    {canManage ? (
                      <>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Upload a new version of ${document.filename}`}
                          onClick={() => {
                            reuploadTarget.current = document;
                            fileInput.current?.click();
                          }}
                        >
                          <RefreshCw aria-hidden="true" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Delete ${document.filename}`}
                          onClick={() => setToDelete(document)}
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={toDelete !== null} onOpenChange={(open) => !open && setToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this document?</DialogTitle>
            <DialogDescription>
              {toDelete?.filename} and all its indexed passages will be removed. Answers will no
              longer cite it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setToDelete(null)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={deleting} onClick={() => void confirmDelete()}>
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
