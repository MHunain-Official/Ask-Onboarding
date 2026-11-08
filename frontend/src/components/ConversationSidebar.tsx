"use client";

import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useState } from "react";

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
  onDelete: (id: string) => Promise<void>;
}

export function ConversationSidebar({
  conversations,
  error,
  activeId,
  onSelect,
  onNewChat,
  onRetry,
  onDelete,
}: ConversationSidebarProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleDelete(id: string, title: string) {
    const label = title.trim() || "this chat";
    if (!window.confirm(`Delete “${label}”? This cannot be undone.`)) return;
    setDeletingId(id);
    try {
      await onDelete(id);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <Button onClick={onNewChat} className="w-full rounded-xl">
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
          <p className="px-2 text-sm leading-relaxed text-muted-foreground">
            No conversations yet. Ask your first question.
          </p>
        ) : (
          <ul className="grid gap-1">
            {conversations.map((conversation) => {
              const title = conversation.title?.trim() || "New chat";
              const isActive = conversation.id === activeId;
              const isDeleting = deletingId === conversation.id;
              return (
                <li key={conversation.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    disabled={isDeleting}
                    aria-current={isActive ? "true" : undefined}
                    className={cn(
                      "w-full rounded-xl py-2 pr-10 pl-2.5 text-left outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/60",
                      isActive
                        ? "bg-accent text-accent-foreground shadow-sm ring-1 ring-border/70"
                        : "hover:bg-muted/80",
                      isDeleting && "opacity-50",
                    )}
                  >
                    <span className="block truncate text-sm font-medium">{title}</span>
                    <span className="block text-xs text-muted-foreground">
                      {formatDate(conversation.created_at)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDelete(conversation.id, title);
                    }}
                    disabled={isDeleting}
                    aria-label={`Delete conversation ${title}`}
                    title="Delete chat"
                    className={cn(
                      "absolute top-1/2 right-1.5 flex size-7 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground outline-none transition-colors",
                      "hover:bg-destructive/15 hover:text-destructive focus-visible:ring-3 focus-visible:ring-ring/60",
                    )}
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
