"use client";

import { Check, ChevronDown, Circle, Loader2, Route, SkipForward, X } from "lucide-react";
import { useEffect, useState } from "react";

import type { TraceStep } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RetrievalTrackProps {
  steps: TraceStep[];
  isStreaming: boolean;
}

const STATUS_ICON = {
  running: Loader2,
  done: Check,
  skipped: SkipForward,
  failed: X,
} as const;

export function RetrievalTrack({ steps, isStreaming }: RetrievalTrackProps) {
  const [open, setOpen] = useState(false);

  // Auto-open while the pipeline is running so the track feels live.
  useEffect(() => {
    if (isStreaming && steps.length > 0) setOpen(true);
  }, [isStreaming, steps.length]);

  if (steps.length === 0) return null;

  const running = steps.some((step) => step.status === "running");
  const failed = steps.some((step) => step.status === "failed");
  const summary = running
    ? "Working…"
    : failed
      ? "Finished with a gate / check stop"
      : `${steps.filter((step) => step.status === "done").length} steps`;

  return (
    <div className="rounded-2xl border border-border/70 bg-muted/30">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-2xl px-3 py-2.5 text-left text-sm outline-none transition-colors hover:bg-muted/60 focus-visible:ring-3 focus-visible:ring-ring/60"
      >
        <Route className="size-4 shrink-0 text-ring" aria-hidden="true" />
        <span className="font-medium">Retrieval track</span>
        <span className="text-muted-foreground">· {summary}</span>
        <ChevronDown
          className={cn(
            "ml-auto size-4 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>

      {open ? (
        <ol className="border-t border-border/60 px-3 py-3">
          {steps.map((step, index) => (
            <TraceRow key={`${step.step}-${index}`} step={step} isLast={index === steps.length - 1} />
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function TraceRow({ step, isLast }: { step: TraceStep; isLast: boolean }) {
  const Icon = STATUS_ICON[step.status] ?? Circle;
  const topHits = Array.isArray(step.data?.top)
    ? (step.data.top as { filename?: string; heading?: string | null; score?: number }[])
    : null;

  return (
    <li className="relative flex gap-3 pb-3 last:pb-0">
      {!isLast ? (
        <span
          aria-hidden="true"
          className="absolute top-6 left-[0.7rem] h-[calc(100%-0.75rem)] w-px bg-border"
        />
      ) : null}
      <span
        className={cn(
          "relative z-10 mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border",
          step.status === "running" && "border-ring bg-accent text-ring",
          step.status === "done" && "border-success/40 bg-success-soft text-success",
          step.status === "skipped" && "border-border bg-muted text-muted-foreground",
          step.status === "failed" && "border-destructive/40 bg-destructive/10 text-destructive",
        )}
      >
        <Icon
          className={cn("size-3.5", step.status === "running" && "animate-spin")}
          aria-hidden="true"
        />
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <p className="text-sm font-medium leading-snug">{step.title}</p>
        {step.detail ? (
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.detail}</p>
        ) : null}
        {topHits && topHits.length > 0 ? (
          <ul className="mt-1.5 grid gap-1">
            {topHits.map((hit, index) => (
              <li
                key={`${hit.filename}-${index}`}
                className="truncate rounded-lg bg-card/80 px-2 py-1 font-mono text-[0.7rem] text-muted-foreground"
              >
                #{index + 1} {hit.filename}
                {hit.heading ? ` · ${hit.heading}` : ""}
                {typeof hit.score === "number" ? ` · ${hit.score.toFixed(2)}` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </li>
  );
}
