"use client";

import { BookOpen, FileText, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { DocMarkdown } from "@/components/admin/DocMarkdown";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { Input } from "@/components/ui/input";
import { getProjectDoc, listProjectDocs } from "@/lib/api";
import type { ProjectDocContent, ProjectDocMeta } from "@/lib/types";
import { cn } from "@/lib/utils";

const GROUP_ORDER = [
  "Overview",
  "Build & process",
  "Deep dive",
  "Agent rules",
  "Eval",
  "Sample data",
];

export function ProjectDocsPanel() {
  const [docs, setDocs] = useState<ProjectDocMeta[] | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [content, setContent] = useState<ProjectDocContent | null>(null);
  const [contentFailed, setContentFailed] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    listProjectDocs()
      .then((items) => {
        setDocs(items);
        setListFailed(false);
        if (items.length > 0) {
          const preferred =
            items.find((doc) => doc.path === "ARCHITECTURE.md") ??
            items.find((doc) => doc.path === "README.md") ??
            items[0];
          setSelectedPath(preferred.path);
        }
      })
      .catch(() => setListFailed(true));
  }, []);

  useEffect(() => {
    if (!selectedPath) return;
    setLoadingContent(true);
    setContentFailed(false);
    getProjectDoc(selectedPath)
      .then((doc) => {
        setContent(doc);
        setLoadingContent(false);
      })
      .catch(() => {
        setContent(null);
        setContentFailed(true);
        setLoadingContent(false);
      });
  }, [selectedPath]);

  const knownPaths = useMemo(() => new Set((docs ?? []).map((doc) => doc.path)), [docs]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle || !docs) return docs ?? [];
    return docs.filter(
      (doc) =>
        doc.title.toLowerCase().includes(needle) ||
        doc.path.toLowerCase().includes(needle) ||
        doc.group.toLowerCase().includes(needle),
    );
  }, [docs, query]);

  const grouped = useMemo(() => groupDocs(filtered), [filtered]);

  function openDoc(path: string) {
    setSelectedPath(path);
    setQuery("");
  }

  if (listFailed) {
    return (
      <div className="p-6">
        <ErrorBanner message="We couldn't load the project docs catalogue. Is PROJECT_DOCS_ROOT mounted?" />
      </div>
    );
  }
  if (docs === null) {
    return (
      <div className="p-6">
        <Skeleton lines={8} />
      </div>
    );
  }
  if (docs.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          icon={BookOpen}
          title="No project docs found"
          description="Mount the repo at PROJECT_DOCS_ROOT (Compose uses /app/repo) so ARCHITECTURE, ADRs, and rules are readable here."
        />
      </div>
    );
  }

  // Full-bleed split pane — no centered max-width island.
  return (
    <div className="grid h-full min-h-0 lg:grid-cols-[19rem_minmax(0,1fr)] xl:grid-cols-[21rem_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col border-b border-border/70 bg-sidebar/90 lg:border-r lg:border-b-0">
        <div className="shrink-0 border-b border-border/60 p-3 sm:p-4">
          <label className="relative block">
            <span className="sr-only">Search docs</span>
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search docs…"
              className="h-9 pl-8"
            />
          </label>
          <p className="mt-2 px-0.5 text-xs text-muted-foreground">
            {filtered.length} of {docs.length} files
          </p>
        </div>
        <nav aria-label="Project documents" className="min-h-0 flex-1 overflow-y-auto p-2 sm:p-3">
          {grouped.length === 0 ? (
            <p className="px-2 py-4 text-sm text-muted-foreground">No docs match that search.</p>
          ) : (
            grouped.map(({ group, items }) => (
              <div key={group} className="mb-3 last:mb-0">
                <h3 className="px-2 pb-1.5 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase">
                  {group}
                </h3>
                <ul className="grid gap-0.5">
                  {items.map((doc) => {
                    const active = doc.path === selectedPath;
                    return (
                      <li key={doc.path}>
                        <button
                          type="button"
                          onClick={() => openDoc(doc.path)}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left text-sm outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/60",
                            active
                              ? "bg-primary text-primary-foreground shadow-sm"
                              : "hover:bg-muted/80",
                          )}
                        >
                          <FileText
                            className="mt-0.5 size-3.5 shrink-0 opacity-70"
                            aria-hidden="true"
                          />
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{doc.title}</span>
                            <span
                              className={cn(
                                "block truncate font-mono text-[0.65rem]",
                                active ? "opacity-80" : "text-muted-foreground",
                              )}
                            >
                              {doc.path}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
        </nav>
      </aside>

      <article
        key={selectedPath ?? "empty"}
        className="min-h-0 overflow-y-auto bg-background/40"
      >
        {contentFailed ? (
          <div className="p-6">
            <ErrorBanner message="We couldn't open that document." />
          </div>
        ) : null}
        {loadingContent ? (
          <div className="p-6 sm:p-8">
            <Skeleton lines={14} />
          </div>
        ) : null}
        {!loadingContent && content ? (
          <div className="w-full px-5 py-6 sm:px-8 lg:px-10 xl:px-12 2xl:px-16">
            <header className="mb-8 border-b border-border/60 pb-5">
              <p className="text-xs font-medium tracking-wide text-ring uppercase">
                {content.group}
              </p>
              <h2 className="font-heading mt-1 text-3xl font-semibold tracking-tight">
                {content.title}
              </h2>
              <p className="mt-1.5 font-mono text-xs text-muted-foreground">{content.path}</p>
            </header>
            {/* Full reader width — uses the right-side space for tables and diagrams. */}
            <div className="w-full max-w-none">
              <DocMarkdown
                text={content.content}
                currentPath={content.path}
                knownPaths={knownPaths}
                onOpenDoc={openDoc}
              />
            </div>
          </div>
        ) : null}
      </article>
    </div>
  );
}

function groupDocs(docs: ProjectDocMeta[]): { group: string; items: ProjectDocMeta[] }[] {
  const buckets = new Map<string, ProjectDocMeta[]>();
  for (const doc of docs) {
    const list = buckets.get(doc.group) ?? [];
    list.push(doc);
    buckets.set(doc.group, list);
  }
  const ordered = GROUP_ORDER.filter((group) => buckets.has(group)).map((group) => ({
    group,
    items: buckets.get(group) ?? [],
  }));
  for (const [group, items] of buckets) {
    if (!GROUP_ORDER.includes(group)) ordered.push({ group, items });
  }
  return ordered;
}
