"use client";

import { Expand, ExternalLink, ZoomIn, ZoomOut } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface MermaidDiagramProps {
  chart: string;
}

/** Client-only Mermaid render with click-to-zoom and open-in-new-tab. */
export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const reactId = useId().replace(/:/g, "");
  const renderCount = useRef(0);
  const { resolvedTheme } = useTheme();
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const source = chart.trim();
    if (!source) {
      setFailed(true);
      return;
    }

    renderCount.current += 1;
    const renderId = `doc-mermaid-${reactId}-${renderCount.current}`;

    void (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: resolvedTheme === "dark" ? "dark" : "neutral",
          fontFamily: "var(--font-dm-sans), ui-sans-serif, system-ui, sans-serif",
        });
        const { svg: rendered } = await mermaid.render(renderId, source);
        if (!cancelled) {
          setSvg(rendered);
          setFailed(false);
        }
      } catch {
        if (!cancelled) {
          setSvg(null);
          setFailed(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chart, reactId, resolvedTheme]);

  function openInNewTab() {
    if (!svg) return;
    const html = [
      "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Diagram</title>",
      "<style>html,body{margin:0;background:#0b1220;display:grid;place-items:center;min-height:100%;padding:24px}",
      "svg{max-width:100%;height:auto}</style></head><body>",
      svg,
      "</body></html>",
    ].join("");
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    // Revoke after the new tab has a chance to load.
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  if (failed) {
    return (
      <pre className="mb-6 overflow-x-auto rounded-2xl border border-border/70 bg-muted/50 p-4 font-mono text-xs leading-relaxed">
        {chart}
      </pre>
    );
  }

  if (!svg) {
    return (
      <div
        className="mb-6 flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-border/70 bg-muted/30 text-sm text-muted-foreground"
        aria-busy="true"
      >
        Drawing diagram…
      </div>
    );
  }

  return (
    <>
      <figure className="mermaid-diagram group relative mb-6 overflow-hidden rounded-2xl border border-border/70 bg-card/80 shadow-sm">
        <div className="absolute top-2 right-2 z-10 flex gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="rounded-full"
            onClick={() => {
              setZoom(1);
              setPreviewOpen(true);
            }}
          >
            <Expand aria-hidden="true" />
            Preview
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="rounded-full"
            onClick={openInNewTab}
          >
            <ExternalLink aria-hidden="true" />
            New tab
          </Button>
        </div>
        <button
          type="button"
          onClick={() => {
            setZoom(1);
            setPreviewOpen(true);
          }}
          className="block w-full cursor-zoom-in overflow-x-auto p-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/60 [&_svg]:mx-auto [&_svg]:max-w-full"
          aria-label="Open diagram preview"
          // Mermaid returns sanitised SVG under securityLevel: "strict".
          dangerouslySetInnerHTML={{ __html: svg }}
        />
        <figcaption className="border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
          Click to zoom · Preview or open in a new tab
        </figcaption>
      </figure>

      <Dialog
        open={previewOpen}
        onOpenChange={(open) => {
          setPreviewOpen(open);
          if (!open) setZoom(1);
        }}
      >
        <DialogContent
          className="flex h-[min(92vh,900px)] w-[min(96vw,1200px)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:max-w-none"
          showCloseButton
        >
          <DialogHeader className="shrink-0 border-b border-border/70 px-4 py-3 sm:px-5">
            <DialogTitle>Diagram preview</DialogTitle>
            <DialogDescription className="sr-only">
              Zoomable Mermaid diagram from the project docs.
            </DialogDescription>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full"
                onClick={() => setZoom((value) => Math.max(0.5, Number((value - 0.25).toFixed(2))))}
              >
                <ZoomOut aria-hidden="true" />
                Zoom out
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="rounded-full"
                onClick={() => setZoom((value) => Math.min(3, Number((value + 0.25).toFixed(2))))}
              >
                <ZoomIn aria-hidden="true" />
                Zoom in
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="rounded-full"
                onClick={() => setZoom(1)}
              >
                {Math.round(zoom * 100)}%
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="rounded-full"
                onClick={openInNewTab}
              >
                <ExternalLink aria-hidden="true" />
                Open in new tab
              </Button>
            </div>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-auto bg-muted/20 p-6">
            <div
              className="origin-top-left transition-transform [&_svg]:max-w-none"
              style={{ transform: `scale(${zoom})` }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
