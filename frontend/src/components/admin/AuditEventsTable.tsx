import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime, shortId } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

export function AuditEventsTable({ events }: { events: AuditEvent[] }) {
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Event</TableHead>
            <TableHead>User</TableHead>
            <TableHead>Detail</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event) => (
            <TableRow key={event.id}>
              <TableCell className="whitespace-nowrap">
                {formatDateTime(event.created_at)}
              </TableCell>
              <TableCell className="font-medium">{event.event_type}</TableCell>
              <TableCell>{event.user_id ? shortId(event.user_id) : "–"}</TableCell>
              <TableCell className="max-w-96 whitespace-normal break-words font-mono text-xs">
                {event.detail ? JSON.stringify(event.detail) : "–"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
