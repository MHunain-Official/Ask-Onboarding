import { Card, CardContent } from "@/components/ui/card";
import { formatMs, formatPercent, formatUsd } from "@/lib/format";
import type { AdminStats } from "@/lib/types";

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Card size="sm">
      <CardContent>
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <p className="mt-1 font-heading text-2xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}

export function StatsTiles({ stats }: { stats: AdminStats }) {
  const tiles = [
    { label: "Requests", value: String(stats.total_requests) },
    { label: "Error rate", value: formatPercent(stats.error_rate) },
    { label: "No-answer rate", value: formatPercent(stats.no_answer_rate) },
    { label: "Latency p50", value: formatMs(stats.p50_latency_ms) },
    { label: "Latency p95", value: formatMs(stats.p95_latency_ms) },
    { label: "Total cost", value: formatUsd(stats.total_cost_usd) },
    { label: "Cache hit rate", value: formatPercent(stats.cache_hit_rate) },
    {
      label: "LLM calls avoided",
      value: stats.llm_calls_avoided?.toString() ?? "–",
    },
    { label: "Estimated saved", value: formatUsd(stats.estimated_saved_usd) },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {tiles.map((tile) => (
        <div key={tile.label}>
          <dt className="sr-only">{tile.label}</dt>
          <dd>
            <Tile {...tile} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
