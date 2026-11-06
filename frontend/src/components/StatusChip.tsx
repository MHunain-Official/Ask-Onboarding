import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  MinusCircle,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Tone = "success" | "warning" | "danger" | "info" | "neutral";

interface ChipStyle {
  label: string;
  tone: Tone;
  icon: LucideIcon;
  spin?: boolean;
}

// One map for document statuses and answer statuses. Each chip has an icon
// and a text label, so meaning never depends on color alone (WCAG).
const CHIP_STYLES: Record<string, ChipStyle> = {
  queued: { label: "Queued", tone: "neutral", icon: Clock },
  processing: { label: "Processing", tone: "info", icon: Loader2, spin: true },
  ready: { label: "Ready", tone: "success", icon: CheckCircle2 },
  failed: { label: "Failed", tone: "danger", icon: AlertCircle },
  ok: { label: "OK", tone: "success", icon: CheckCircle2 },
  no_answer: { label: "No answer", tone: "neutral", icon: MinusCircle },
  error: { label: "Error", tone: "danger", icon: AlertCircle },
  refused: { label: "Refused", tone: "warning", icon: MinusCircle },
  ungrounded: { label: "Ungrounded", tone: "warning", icon: AlertCircle },
  partial: { label: "Partial", tone: "warning", icon: AlertCircle },
  open: { label: "Open", tone: "info", icon: Clock },
  closed: { label: "Closed", tone: "neutral", icon: CheckCircle2 },
};

const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-destructive/10 text-destructive",
  info: "bg-info-soft text-info",
  neutral: "bg-muted text-muted-foreground",
};

interface StatusChipProps {
  status: string;
  title?: string;
  className?: string;
}

export function StatusChip({ status, title, className }: StatusChipProps) {
  const style = CHIP_STYLES[status] ?? {
    label: status,
    tone: "neutral" as Tone,
    icon: MinusCircle,
  };
  const Icon = style.icon;
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONE_CLASSES[style.tone],
        className,
      )}
    >
      <Icon
        className={cn("size-3", style.spin && "animate-spin motion-reduce:animate-none")}
        aria-hidden="true"
      />
      {style.label}
    </span>
  );
}
