"use client";

import { useEffect, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { StatusChip } from "@/components/StatusChip";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { getLlmCall } from "@/lib/api";
import { formatDateTime, formatMs, formatUsd } from "@/lib/format";
import type { LlmCallDetail } from "@/lib/types";

interface LlmCallDrawerProps {
  callId: string | null;
  onClose: () => void;
}

export function LlmCallDrawer({ callId, onClose }: LlmCallDrawerProps) {
  return (
    <Sheet open={callId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-2xl">
        <SheetHeader className="border-b pr-12">
          <SheetTitle>Request detail</SheetTitle>
          <SheetDescription>
            Exact prompt, response, retrieval and cost for one request.
          </SheetDescription>
        </SheetHeader>
        {callId ? <Detail key={callId} callId={callId} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function Detail({ callId }: { callId: string }) {
  const [call, setCall] = useState<LlmCallDetail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getLlmCall(callId)
      .then((value) => !cancelled && setCall(value))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [callId]);

  if (failed)
    return (
      <div className="p-4">
        <ErrorBanner message="We couldn't load this request." />
      </div>
    );
  if (!call)
    return (
      <div className="p-4">
        <Skeleton lines={8} />
      </div>
    );

  return (
    <div className="grid gap-5 p-4 text-sm">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        <Field label="Status">
          <StatusChip status={call.status} />
        </Field>
        <Field label="When">{formatDateTime(call.created_at)}</Field>
        <Field label="Request ID">
          <code className="font-mono text-xs">{call.request_id}</code>
        </Field>
        <Field label="Model">
          {call.model_used ?? "–"}
          {call.fallback_used ? " (fallback)" : ""}
        </Field>
        <Field label="Tokens in / out">
          {call.input_tokens ?? "–"} / {call.output_tokens ?? "–"}
          {call.usage_estimated ? " (estimated)" : ""}
        </Field>
        <Field label="Cost">{formatUsd(call.estimated_cost_usd)}</Field>
        <Field label="Latency total">{formatMs(call.latency_ms_total)}</Field>
        <Field label="Retrieval / first token / generation">
          {formatMs(call.latency_ms_retrieval)} / {formatMs(call.latency_ms_first_token)} /{" "}
          {formatMs(call.latency_ms_generation)}
        </Field>
        <Field label="Cache">{call.cache_hit}</Field>
        <Field label="Prompt version">{call.prompt_version ?? "–"}</Field>
      </dl>
      {call.error_message ? (
        <ErrorBanner message={`${call.error_type ?? "Error"}: ${call.error_message}`} />
      ) : null}
      <Block title="Question" text={call.question} />
      <Chunks call={call} />
      <Block title="System prompt (admin only)" text={call.system_prompt} />
      <Block
        title="Messages sent"
        text={call.messages_sent === null ? null : JSON.stringify(call.messages_sent, null, 2)}
      />
      <Block title="Model response" text={call.model_response} />
      <Block
        title="Tool calls"
        text={call.tool_calls === null ? null : JSON.stringify(call.tool_calls, null, 2)}
      />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}

function Block({ title, text }: { title: string; text: string | null }) {
  return (
    <section>
      <h3 className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {/* Rendered as text in a <pre>: prompts may contain anything, including markup. */}
      <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap break-words">
        {text ?? "–"}
      </pre>
    </section>
  );
}

function Chunks({ call }: { call: LlmCallDetail }) {
  const chunks = call.retrieved_chunks ?? [];
  return (
    <section>
      <h3 className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Retrieved chunks ({call.retrieval_mode ?? "n/a"})
      </h3>
      {chunks.length === 0 ? (
        <p className="text-muted-foreground">None retrieved.</p>
      ) : (
        <ul className="grid gap-1">
          {chunks.map((chunk) => (
            <li
              key={chunk.chunk_id}
              className="flex justify-between gap-2 rounded-md bg-muted px-2 py-1 font-mono text-xs"
            >
              <span className="truncate">{chunk.chunk_id}</span>
              <span className="tabular-nums">{chunk.score.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
