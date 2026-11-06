import { StatusChip } from "@/components/StatusChip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime, formatMs, formatUsd, shortId, truncate } from "@/lib/format";
import type { LlmCallSummary } from "@/lib/types";

interface LlmCallTableProps {
  calls: LlmCallSummary[];
  onSelect: (call: LlmCallSummary) => void;
}

export function LlmCallTable({ calls, onSelect }: LlmCallTableProps) {
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>User</TableHead>
            <TableHead>Question</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Cache</TableHead>
            <TableHead className="text-right">Tokens in/out</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead className="text-right">Latency</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {calls.map((call) => (
            <TableRow key={call.id}>
              <TableCell className="whitespace-nowrap">{formatDateTime(call.created_at)}</TableCell>
              <TableCell>{call.user_name ?? shortId(call.user_id)}</TableCell>
              <TableCell className="max-w-72 whitespace-normal">
                <button
                  type="button"
                  onClick={() => onSelect(call)}
                  className="rounded-sm text-left font-medium underline-offset-2 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/60"
                >
                  {truncate(call.question, 90)}
                </button>
              </TableCell>
              <TableCell>
                <StatusChip status={call.status} />
              </TableCell>
              <TableCell>{call.cache_hit}</TableCell>
              <TableCell className="text-right tabular-nums">
                {call.input_tokens ?? "–"} / {call.output_tokens ?? "–"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatUsd(call.estimated_cost_usd)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatMs(call.latency_ms_total)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
