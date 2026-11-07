"use client";

import { Ticket as TicketIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/AuthProvider";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { StatusChip } from "@/components/StatusChip";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listTickets, updateTicketStatus } from "@/lib/api";
import { formatDateTime, shortId } from "@/lib/format";
import type { Ticket, TicketStatus } from "@/lib/types";

const STAFF_STATUSES: { value: TicketStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "in_review", label: "In review" },
  { value: "in_progress", label: "In progress" },
  { value: "answered", label: "Answered" },
  { value: "closed", label: "Closed" },
];

export default function TicketsPage() {
  const { user } = useAuth();
  const canManage = user.role === "manager" || user.role === "admin";
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    listTickets()
      .then(setTickets)
      .catch(() => setFailed(true));
  }, []);

  useEffect(load, [load]);

  async function changeStatus(ticket: Ticket, status: TicketStatus) {
    try {
      const updated = await updateTicketStatus(ticket.id, status);
      setTickets((current) =>
        current?.map((row) => (row.id === updated.id ? updated : row)) ?? null,
      );
      toast.success(`Ticket marked ${status.replaceAll("_", " ")}`);
    } catch {
      toast.error("Couldn't update ticket status");
    }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-5 p-4 sm:p-6">
      <header>
        <h1 className="font-heading text-2xl font-semibold">Help-desk tickets</h1>
        <p className="text-sm text-muted-foreground">
          {canManage
            ? "Triage every ticket. Update status so employees can see progress."
            : "Tickets you asked the assistant to open, with live status from the help desk."}
        </p>
      </header>

      {failed ? <ErrorBanner message="We couldn't load tickets." onRetry={load} /> : null}
      {tickets === null && !failed ? <Skeleton lines={5} /> : null}
      {tickets?.length === 0 ? (
        <EmptyState
          icon={TicketIcon}
          title="No tickets yet"
          description="When the assistant can't find an answer, it offers to open a ticket. Accepted tickets show up here."
          action={
            <Link href="/chat" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Ask a question
            </Link>
          }
        />
      ) : null}
      {tickets && tickets.length > 0 ? (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Question</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tickets.map((ticket) => (
                <TableRow key={ticket.id}>
                  <TableCell className="max-w-56 font-medium whitespace-normal break-words">
                    {ticket.title}
                  </TableCell>
                  <TableCell className="max-w-80 whitespace-normal break-words text-muted-foreground">
                    {ticket.question}
                  </TableCell>
                  <TableCell>{ticket.user_name ?? shortId(ticket.user_id)}</TableCell>
                  <TableCell>
                    {canManage ? (
                      <select
                        aria-label={`Status for ${ticket.title}`}
                        className="rounded-md border bg-background px-2 py-1 text-sm"
                        value={ticket.status}
                        onChange={(event) =>
                          void changeStatus(ticket, event.target.value as TicketStatus)
                        }
                      >
                        {STAFF_STATUSES.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <StatusChip status={ticket.status} />
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {formatDateTime(ticket.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  );
}
