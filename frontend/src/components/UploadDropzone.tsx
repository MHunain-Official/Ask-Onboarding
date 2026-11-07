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
        "flex flex-col items-center gap-3 rounded-3xl border-2 border-dashed bg-card/70 px-6 py-10 text-center backdrop-blur-sm transition-all",
        dragging ? "scale-[1.01] border-ring bg-accent/50 shadow-md" : "border-border/80",
      )}
    >
      <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground ring-1 ring-border/60">
        <UploadCloud className="size-6" aria-hidden="true" />
      </span>
      <p className="text-sm">
        Drag files here, or{" "}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-sm font-medium text-ring underline underline-offset-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/60"
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
