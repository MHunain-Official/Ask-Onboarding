"use client";

import { CheckCircle2, LifeBuoy, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button, buttonVariants } from "@/components/ui/button";
import { createTicket } from "@/lib/api";
import type { TicketOffer } from "@/lib/types";

type OfferState = "asking" | "creating" | "created" | "dismissed";

interface TicketOfferCardProps {
  offer: TicketOffer;
  conversationId: string | null;
}

// The model only *offers* a ticket. Nothing is saved until the user clicks
// Yes, which calls the authenticated POST /api/tickets (AGENTS.md §5.6).
export function TicketOfferCard({ offer, conversationId }: TicketOfferCardProps) {
  const [state, setState] = useState<OfferState>("asking");

  async function openTicket() {
    setState("creating");
    try {
      await createTicket({
        title: offer.suggested_title,
        question: offer.question,
        conversation_id: conversationId,
      });
      setState("created");
    } catch {
      toast.error("We couldn't open the ticket. Please try again.");
      setState("asking");
    }
  }

  if (state === "dismissed") {
    return <p className="text-sm text-muted-foreground">No ticket opened.</p>;
  }

  if (state === "created") {
    return (
      <div
        role="status"
        className="flex flex-wrap items-center gap-3 rounded-2xl border border-success/40 bg-success-soft p-4 text-sm text-success"
      >
        <CheckCircle2 className="size-4" aria-hidden="true" />
        <span className="font-medium">Ticket opened. The help desk will follow up.</span>
        <Link
          href="/tickets"
          className={buttonVariants({ variant: "outline", size: "sm", className: "rounded-full" })}
        >
          View my tickets
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border/70 bg-card/90 p-4 text-sm shadow-sm">
      <p className="flex items-start gap-2 font-medium">
        <LifeBuoy className="mt-0.5 size-4 shrink-0 text-ring" aria-hidden="true" />
        <span>I couldn&apos;t find this in the documents. Want me to open a help-desk ticket?</span>
      </p>
      <p className="mt-2 pl-6 text-muted-foreground">&ldquo;{offer.suggested_title}&rdquo;</p>
      <div className="mt-4 flex flex-wrap gap-2 pl-6">
        <Button
          size="sm"
          className="rounded-full"
          disabled={state === "creating"}
          onClick={() => void openTicket()}
        >
          {state === "creating" ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          Yes, open ticket
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-full"
          disabled={state === "creating"}
          onClick={() => setState("dismissed")}
        >
          No thanks
        </Button>
      </div>
    </div>
  );
}
