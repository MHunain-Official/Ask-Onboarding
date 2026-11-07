"use client";

import { Activity, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AuditEventsTable } from "@/components/admin/AuditEventsTable";
import { LlmCallDrawer } from "@/components/admin/LlmCallDrawer";
import { LlmCallTable } from "@/components/admin/LlmCallTable";
import { ProjectDocsPanel } from "@/components/admin/ProjectDocsPanel";
import { StatsTiles } from "@/components/admin/StatsTiles";
import { useAuth } from "@/components/AuthProvider";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/Skeleton";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getAdminStats, listAuditEvents, listLlmCalls } from "@/lib/api";
import type { AdminStats, AuditEvent, LlmCallSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_FILTERS = ["", "ok", "no_answer", "error", "refused", "ungrounded", "partial"];
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type MainTab = "docs" | "overview";
type OverviewSection = "stats" | "requests" | "audit";

export default function AdminPage() {
  const { user } = useAuth();
  if (user.role !== "admin") {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <EmptyState
          icon={ShieldAlert}
          title="Admins only"
          description="The audit dashboard is limited to administrators. Sign in as the demo admin to see it."
        />
      </div>
    );
  }
  return <AdminDashboard />;
}

function AdminDashboard() {
  const [tab, setTab] = useState<MainTab>("docs");

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 space-y-4 border-b border-border/70 px-4 pt-5 pb-3 sm:px-6">
        <PageHeader
          title="Admin"
          description="Browse project docs full-width, or open Overview for KPIs, requests, and audit."
        />
        <Tabs value={tab} onValueChange={(value) => setTab(value as MainTab)}>
          <TabsList className="h-auto w-fit flex-wrap rounded-full p-1">
            <TabsTrigger value="docs" className="rounded-full px-4">
              Docs
            </TabsTrigger>
            <TabsTrigger value="overview" className="rounded-full px-4">
              Overview
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "docs" ? <ProjectDocsPanel /> : <OverviewPanel />}
      </div>
    </div>
  );
}

function OverviewPanel() {
  const [section, setSection] = useState<OverviewSection>("stats");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [statsFailed, setStatsFailed] = useState(false);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch(() => setStatsFailed(true));
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b border-border/60 px-4 py-3 sm:px-6">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Overview sections">
          {(
            [
              ["stats", "Stats"],
              ["requests", "Requests"],
              ["audit", "Audit events"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={section === id}
              onClick={() => setSection(id)}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm font-medium outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/60",
                section === id
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border/70 bg-card/60 text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        {section === "stats" ? (
          <div className="grid w-full gap-4">
            {statsFailed ? <ErrorBanner message="We couldn't load the summary tiles." /> : null}
            {stats ? <StatsTiles stats={stats} /> : statsFailed ? null : <Skeleton lines={3} />}
          </div>
        ) : null}
        {section === "requests" ? <RequestsPanel /> : null}
        {section === "audit" ? <AuditPanel /> : null}
      </div>
    </div>
  );
}

function RequestsPanel() {
  const [status, setStatus] = useState("");
  const [userFilter, setUserFilter] = useState("");
  const [calls, setCalls] = useState<LlmCallSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(() => {
    setFailed(false);
    setCalls(null);
    const trimmed = userFilter.trim();
    listLlmCalls({ status, userId: UUID_PATTERN.test(trimmed) ? trimmed : undefined })
      .then(setCalls)
      .catch(() => setFailed(true));
  }, [status, userFilter]);

  useEffect(load, [load]);

  return (
    <div className="grid w-full gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">
          Status
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {STATUS_FILTERS.map((value) => (
              <option key={value} value={value}>
                {value === "" ? "All statuses" : value}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          User ID
          <Input
            value={userFilter}
            onChange={(event) => setUserFilter(event.target.value)}
            placeholder="Full user UUID"
            className="w-56"
          />
        </label>
      </div>
      {failed ? <ErrorBanner message="We couldn't load requests." onRetry={load} /> : null}
      {calls === null && !failed ? <Skeleton lines={6} /> : null}
      {calls?.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No requests match"
          description="Ask a question in the chat, or clear the filters."
        />
      ) : null}
      {calls && calls.length > 0 ? (
        <LlmCallTable calls={calls} onSelect={(call) => setSelectedId(call.id)} />
      ) : null}
      <LlmCallDrawer callId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}

function AuditPanel() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    listAuditEvents()
      .then(setEvents)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <ErrorBanner message="We couldn't load audit events." />;
  if (events === null) return <Skeleton lines={6} />;
  if (events.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No audit events yet"
        description="Logins, uploads, and denied requests will appear here."
      />
    );
  }
  return <AuditEventsTable events={events} />;
}
