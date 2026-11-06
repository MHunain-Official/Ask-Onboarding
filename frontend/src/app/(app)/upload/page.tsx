"use client";

import { FileText } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { DocumentTable } from "@/components/DocumentTable";
import { DocumentViewDialog } from "@/components/DocumentViewDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { UploadDropzone } from "@/components/UploadDropzone";
import { UploadProgressList, type UploadTask } from "@/components/UploadProgressList";
import { ApiError, deleteDocument, listDocuments, uploadDocument } from "@/lib/api";
import { checkUploadFile } from "@/lib/uploadRules";
import type { AccessLevel, DocumentItem } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export default function UploadPage() {
  const { user } = useAuth();
  const canRestrict = user.role !== "employee";
  const [documents, setDocuments] = useState<DocumentItem[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [managersOnly, setManagersOnly] = useState(false);
  const [viewing, setViewing] = useState<DocumentItem | null>(null);
  const nextTaskId = useRef(0);

  const refresh = useCallback(() => {
    listDocuments()
      .then((items) => {
        setDocuments(items);
        setLoadFailed(false);
      })
      .catch(() => setLoadFailed(true));
  }, []);

  useEffect(refresh, [refresh]);

  // Poll every 2 s while anything is still being indexed (§7).
  const isBusy =
    documents?.some((doc) => doc.status === "queued" || doc.status === "processing") ?? false;
  useEffect(() => {
    if (!isBusy) return;
    const timer = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isBusy, refresh]);

  const updateTask = (id: number, change: Partial<UploadTask>) =>
    setTasks((current) => current.map((task) => (task.id === id ? { ...task, ...change } : task)));

  async function uploadOne(file: File) {
    const problem = checkUploadFile(file);
    const id = nextTaskId.current++;
    if (problem) {
      setTasks((current) => [
        ...current,
        { id, name: file.name, progress: 0, state: "error", message: problem },
      ]);
      return;
    }
    setTasks((current) => [...current, { id, name: file.name, progress: 0, state: "uploading" }]);
    const accessLevel: AccessLevel = canRestrict && managersOnly ? "managers" : "all";
    try {
      const saved = await uploadDocument(file, accessLevel, (progress) =>
        updateTask(id, { progress }),
      );
      // An identical re-upload returns the existing row untouched (§5.1 "no changes").
      const before = documents?.find((doc) => doc.id === saved.id);
      const unchanged = before !== undefined && before.version === saved.version;
      updateTask(id, {
        state: "done",
        progress: 1,
        message: unchanged ? "No changes" : "Queued for indexing",
      });
      refresh();
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Upload failed.";
      updateTask(id, { state: "error", message });
    }
  }

  function handleFiles(files: File[]) {
    files.forEach((file) => void uploadOne(file));
  }

  function handleReupload(document: DocumentItem, file: File) {
    // The filename is the document's identity, so keep the original name (§5.1).
    void uploadOne(new File([file], document.filename, { type: file.type }));
  }

  async function handleDelete(document: DocumentItem) {
    try {
      await deleteDocument(document.id);
      toast.success(`Deleted ${document.filename}`);
      refresh();
    } catch {
      toast.error(`Couldn't delete ${document.filename}`);
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-5 p-4 sm:p-6">
      <header>
        <h1 className="font-heading text-2xl font-semibold">Documents</h1>
        <p className="text-sm text-muted-foreground">
          Upload the files the assistant is allowed to answer from. Uploading a changed file with
          the same name replaces the old version.
        </p>
      </header>

      <UploadDropzone onFiles={handleFiles} />
      {canRestrict ? (
        <label className="flex w-fit items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={managersOnly}
            onChange={(event) => setManagersOnly(event.target.checked)}
            className="size-4 accent-[var(--ring)]"
          />
          Make new uploads visible to managers only
        </label>
      ) : null}
      <UploadProgressList tasks={tasks} />

      {loadFailed ? (
        <ErrorBanner message="We couldn't load the document list." onRetry={refresh} />
      ) : null}
      {documents === null && !loadFailed ? <Skeleton lines={6} /> : null}
      {documents?.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description="Drop a PDF, Markdown or text file above to get started. Once it is ready, you can ask questions about it."
        />
      ) : null}
      {documents && documents.length > 0 ? (
        <DocumentTable
          documents={documents}
          onView={setViewing}
          onDelete={handleDelete}
          onReupload={handleReupload}
        />
      ) : null}
      <DocumentViewDialog document={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}
