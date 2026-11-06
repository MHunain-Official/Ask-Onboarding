// Small display helpers. Kept pure so they are easy to read and test.

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

export function formatPercent(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined) return "–";
  return `${(fraction * 100).toFixed(1)}%`;
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function truncate(text: string, maxLength: number): string {
  return text.length <= maxLength ? text : `${text.slice(0, maxLength - 1)}…`;
}
