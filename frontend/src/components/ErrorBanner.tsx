import { AlertTriangle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorBannerProps {
  message: string;
  requestId?: string;
  onRetry?: () => void;
}

// role="alert" makes screen readers announce the error immediately.
export function ErrorBanner({ message, requestId, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-foreground">{message}</p>
        {requestId ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Quote this request ID to support: <code className="font-mono">{requestId}</code>
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCcw aria-hidden="true" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}
