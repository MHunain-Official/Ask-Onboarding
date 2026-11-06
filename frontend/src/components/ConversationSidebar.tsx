"use client";

import { MessageSquarePlus } from "lucide-react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import type { ConversationSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ConversationSidebarProps {
  conversations: ConversationSummary[] | null;
  error: boolean;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onRetry: () => void;
}

export function ConversationSidebar({
  conversations,
  error,
  activeId,
  onSelect,
  onNewChat,
  onRetry,
}: ConversationSidebarProps) {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <Button onClick={onNewChat} className="w-full">
        <MessageSquarePlus aria-hidden="true" />
        New chat
      </Button>
      <h2 className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        History
      </h2>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <ErrorBanner message="Couldn't load history." onRetry={onRetry} />
        ) : conversations === null ? (
          <Skeleton lines={5} />
        ) : conversations.length === 0 ? (
          <p className="px-1 text-sm text-muted-foreground">
            No conversations yet. Ask your first question.
          </p>
        ) : (
          <ul className="grid gap-0.5">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => onSelect(conversation.id)}
                  aria-current={conversation.id === activeId ? "true" : undefined}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/60",
                    conversation.id === activeId
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-muted",
                  )}
                >
                  <span className="block truncate text-sm font-medium">{conversation.title}</span>
                  <span className="block text-xs text-muted-foreground">
                    {formatDate(conversation.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
