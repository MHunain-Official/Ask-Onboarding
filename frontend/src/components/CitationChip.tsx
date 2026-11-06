import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CitationChipProps {
  citation: Citation;
  onOpen: (citation: Citation) => void;
  className?: string;
}

// The little "[1]" button inside an answer. Opens the SourceDrawer.
export function CitationChip({ citation, onOpen, className }: CitationChipProps) {
  const where = citation.page ? `, page ${citation.page}` : "";
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      aria-label={`Source ${citation.n}: ${citation.filename}${where}`}
      title={`${citation.filename}${where}`}
      className={cn(
        "mx-0.5 inline-flex min-w-5 -translate-y-px items-center justify-center rounded-md bg-accent px-1 font-mono text-[0.72rem] leading-5 font-medium text-accent-foreground outline-none",
        "hover:bg-ring/25 focus-visible:ring-3 focus-visible:ring-ring/60",
        className,
      )}
    >
      {citation.n}
    </button>
  );
}
