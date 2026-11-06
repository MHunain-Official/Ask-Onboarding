"use client";

import { Activity, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AuditEventsTable } from "@/components/admin/AuditEventsTable";
import { LlmCallDrawer } from "@/components/admin/LlmCallDrawer";
import { LlmCallTable } from "@/components/admin/LlmCallTable";
import { StatsTiles } from "@/components/admin/StatsTiles";
import { useAuth } from "@/components/AuthProvider";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getAdminStats, listAuditEvents, listLlmCalls } from "@/lib/api";
import type { AdminStats, AuditEvent, LlmCallSummary } from "@/lib/types";

const STATUS_FILTERS = ["", "ok", "no_answer", "error", "refused", "ungrounded", "partial"];
// The backend filters by exact `user_id` (a UUID), not a name/email
// substring (AGENTS.md §6) — validate client-side so a partially typed id
// never turns into a 422 from the server instead of just "no results yet".
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [statsFailed, setStatsFailed] = useState(false);

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch(() => setStatsFailed(true));
  }, []);

  return (
    <div className="mx-auto grid max-w-7xl gap-5 p-4 sm:p-6">
      <header>
        <h1 className="font-heading text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Every answer request and sensitive action, recorded.
        </p>
      </header>
      {statsFailed ? <ErrorBanner message="We couldn't load the summary tiles." /> : null}
      {stats ? <StatsTiles stats={stats} /> : statsFailed ? null : <Skeleton lines={3} />}

      <Tabs defaultValue="requests">
        <TabsList>
          <TabsTrigger value="requests">Requests</TabsTrigger>
          <TabsTrigger value="audit">Audit events</TabsTrigger>
        </TabsList>
        <TabsContent value="requests" className="mt-3">
          <RequestsPanel />
        </TabsContent>
        <TabsContent value="audit" className="mt-3">
          <AuditPanel />
        </TabsContent>
      </Tabs>
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
    <div className="grid gap-3">
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
