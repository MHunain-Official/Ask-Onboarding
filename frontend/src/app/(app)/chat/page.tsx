"use client";

import { History, Library } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ChatComposer } from "@/components/ChatComposer";
import { ChatMessage } from "@/components/ChatMessage";
import { ConversationSidebar } from "@/components/ConversationSidebar";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { SourceDrawer } from "@/components/SourceDrawer";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useChatStream } from "@/hooks/useChatStream";
import { listConversations } from "@/lib/api";
import type { Citation, ConversationSummary } from "@/lib/types";

const STARTER_QUESTIONS = [
  "How do I submit an expense report?",
  "What is on the 2026 holiday calendar?",
  "How do I get help from IT?",
  "What are the code review guidelines?",
];

export default function ChatPage() {
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [historyFailed, setHistoryFailed] = useState(false);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => {
    setHistoryFailed(false);
    listConversations()
      .then(setConversations)
      .catch(() => setHistoryFailed(true));
  }, []);

  useEffect(loadConversations, [loadConversations]);

  const chat = useChatStream(loadConversations);
  const { items } = chat;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [items]);

  // Refresh history titles once an answer finishes.
  useEffect(() => {
    if (!chat.isStreaming && chat.conversationId) loadConversations();
  }, [chat.isStreaming, chat.conversationId, loadConversations]);

  function selectConversation(id: string) {
    setHistoryOpen(false);
    void chat.openConversation(id);
  }

  function startNewChat() {
    setHistoryOpen(false);
    chat.reset();
  }

  const sidebar = (
    <ConversationSidebar
      conversations={conversations}
      error={historyFailed}
      activeId={chat.conversationId}
      onSelect={selectConversation}
      onNewChat={startNewChat}
      onRetry={loadConversations}
    />
  );

  return (
    <div className="flex h-full">
      <aside
        aria-label="Conversation history"
        className="hidden w-64 shrink-0 border-r bg-sidebar md:block"
      >
        {sidebar}
      </aside>
      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent side="left" className="w-72">
          <SheetHeader>
            <SheetTitle>Conversations</SheetTitle>
          </SheetHeader>
          {sidebar}
        </SheetContent>
      </Sheet>

      <section aria-label="Chat" className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center border-b px-3 py-1.5 md:hidden">
          <Button variant="ghost" size="sm" onClick={() => setHistoryOpen(true)}>
            <History aria-hidden="true" />
            History
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid max-w-3xl gap-5 p-4 sm:p-6">
            {chat.historyError ? <ErrorBanner message={chat.historyError} /> : null}
            {chat.isLoadingHistory ? (
              <Skeleton lines={8} />
            ) : items.length === 0 ? (
              <EmptyChat onPick={chat.send} />
            ) : (
              items.map((item) => (
                <ChatMessage
                  key={item.id}
                  item={item}
                  conversationId={chat.conversationId}
                  onOpenCitation={setOpenCitation}
                  onRetry={chat.retry}
                  onRegenerate={chat.regenerate}
                  onExplainSimpler={
                    item.role === "assistant" && item.status === "ok"
                      ? () => chat.send("Explain in easier wording")
                      : undefined
                  }
                />
              ))
            )}
            <div ref={endRef} />
          </div>
        </div>
        <ChatComposer isStreaming={chat.isStreaming} onSend={chat.send} onStop={chat.stop} />
      </section>

      <SourceDrawer citation={openCitation} onClose={() => setOpenCitation(null)} />
    </div>
  );
}

function EmptyChat({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="grid gap-5 pt-6">
      <EmptyState
        icon={Library}
        title="Ask anything about the company"
        description="Answers come only from uploaded documents, with sources you can open. If I can't find it, I'll say so and offer a help-desk ticket."
      />
      <div>
        <h2 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Try asking
        </h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {STARTER_QUESTIONS.map((question) => (
            <li key={question}>
              <button
                type="button"
                onClick={() => onPick(question)}
                className="w-full rounded-lg border bg-card p-3 text-left text-sm outline-none transition-colors hover:border-ring hover:bg-accent/50 focus-visible:ring-3 focus-visible:ring-ring/60"
              >
                {question}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
