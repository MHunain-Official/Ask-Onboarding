import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="animate-rise flex flex-col items-center justify-center gap-4 rounded-3xl border border-border/70 bg-card/60 px-6 py-14 text-center shadow-[inset_0_1px_0_oklch(1_0_0/0.45)] backdrop-blur-sm">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground ring-1 ring-border/60">
        <Icon className="size-6" aria-hidden="true" />
      </span>
      <div className="grid gap-1.5">
        <h2 className="font-heading text-xl font-semibold tracking-tight">{title}</h2>
        <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}
