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
  const canManage = user.role === "manager" || user.role === "admin";
  const [documents, setDocuments] = useState<DocumentItem[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [accessLevel, setAccessLevel] = useState<AccessLevel>("all");
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
    try {
      const saved = await uploadDocument(file, accessLevel, (progress) =>
        updateTask(id, { progress }),
      );
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
    if (!canManage) {
      toast.error("Only managers and admins can upload documents.");
      return;
    }
    files.forEach((file) => void uploadOne(file));
  }

  function handleReupload(document: DocumentItem, file: File) {
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
        <h1 className="font-heading text-2xl font-semibold">
          {canManage ? "Document library" : "Company documents"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {canManage
            ? "Upload the files the assistant may answer from. Choose who can read each file. Re-uploading the same filename replaces the old version after indexing."
            : "Browse documents you are allowed to read. Uploads and deletions are handled by managers and admins."}
        </p>
      </header>

      {canManage ? (
        <>
          <UploadDropzone onFiles={handleFiles} />
          <label className="grid w-fit gap-1 text-sm">
            <span className="text-muted-foreground">Access level for new uploads</span>
            <select
              value={accessLevel}
              onChange={(event) => setAccessLevel(event.target.value as AccessLevel)}
              className="rounded-md border bg-background px-3 py-2"
            >
              <option value="all">Everyone (employees)</option>
              <option value="managers">Managers and admins</option>
              {user.role === "admin" ? <option value="admins">Admins only</option> : null}
            </select>
          </label>
          <UploadProgressList tasks={tasks} />
        </>
      ) : null}

      {loadFailed ? (
        <ErrorBanner message="We couldn't load the document list." onRetry={refresh} />
      ) : null}
      {documents === null && !loadFailed ? <Skeleton lines={6} /> : null}
      {documents?.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description={
            canManage
              ? "Drop a PDF, Markdown or text file above to get started."
              : "Ask a manager to upload onboarding docs, then come back here to browse them."
          }
        />
      ) : null}
      {documents && documents.length > 0 ? (
        <DocumentTable
          documents={documents}
          canManage={canManage}
          onView={setViewing}
          onDelete={handleDelete}
          onReupload={handleReupload}
        />
      ) : null}
      <DocumentViewDialog document={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}
