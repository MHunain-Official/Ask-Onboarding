"use client";

import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void;
}

// A drop target that is also a real button, so keyboard users can open the file picker.
export function UploadDropzone({ onFiles }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        onFiles(Array.from(event.dataTransfer.files));
      }}
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed bg-card px-6 py-8 text-center transition-colors",
        dragging ? "border-ring bg-accent/60" : "border-input",
      )}
    >
      <UploadCloud className="size-8 text-ring" aria-hidden="true" />
      <p className="text-sm">
        Drag files here, or{" "}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-sm font-medium underline underline-offset-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/60"
        >
          browse
        </button>
      </p>
      <p className="text-xs text-muted-foreground">PDF, Markdown or text · up to 10 MB each</p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.md,.txt"
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose files to upload"
        onChange={(event) => {
          onFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
    </div>
  );
}
