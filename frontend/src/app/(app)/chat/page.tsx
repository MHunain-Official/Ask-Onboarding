"use client";

import { History, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ChatComposer } from "@/components/ChatComposer";
import { ChatMessage } from "@/components/ChatMessage";
import { ConversationSidebar } from "@/components/ConversationSidebar";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { SourceDrawer } from "@/components/SourceDrawer";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useChatStream } from "@/hooks/useChatStream";
import { deleteConversation, listConversations } from "@/lib/api";
import type { Citation, ConversationSummary } from "@/lib/types";

const STARTER_QUESTIONS = [
  {
    label: "Expenses",
    question: "How do I submit an expense report?",
  },
  {
    label: "Holidays",
    question: "What is on the 2026 holiday calendar?",
  },
  {
    label: "IT help",
    question: "How do I get help from IT?",
  },
  {
    label: "Code review",
    question: "What are the code review guidelines?",
  },
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

  async function handleDeleteConversation(id: string) {
    try {
      await deleteConversation(id);
      setConversations((current) => current?.filter((item) => item.id !== id) ?? null);
      if (chat.conversationId === id) {
        setHistoryOpen(false);
        chat.reset();
      }
      toast.success("Chat deleted");
    } catch {
      toast.error("Couldn't delete that chat");
      throw new Error("delete failed");
    }
  }

  const sidebar = (
    <ConversationSidebar
      conversations={conversations}
      error={historyFailed}
      activeId={chat.conversationId}
      onSelect={selectConversation}
      onNewChat={startNewChat}
      onRetry={loadConversations}
      onDelete={handleDeleteConversation}
    />
  );

  return (
    <div className="flex h-full">
      <aside
        aria-label="Conversation history"
        className="hidden w-64 shrink-0 border-r border-border/70 bg-sidebar/80 backdrop-blur-sm md:block"
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
        <div className="flex items-center border-b border-border/70 px-3 py-1.5 md:hidden">
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
    <div className="grid gap-8 pt-8 sm:pt-14">
      <div className="animate-rise mx-auto max-w-lg text-center">
        <span className="mb-4 inline-flex size-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground ring-1 ring-border/70">
          <Sparkles className="size-5" aria-hidden="true" />
        </span>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          What do you need to know?
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          Answers come only from uploaded documents, with sources you can open. If it isn&apos;t in
          the library, I&apos;ll say so and offer a help-desk ticket.
        </p>
      </div>
      <div className="animate-rise stagger-2">
        <h2 className="mb-3 text-center text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Try asking
        </h2>
        <ul className="grid gap-2.5 sm:grid-cols-2">
          {STARTER_QUESTIONS.map(({ label, question }, index) => (
            <li key={question} className={index > 1 ? "stagger-3 animate-rise" : undefined}>
              <button
                type="button"
                onClick={() => onPick(question)}
                className="group flex h-full w-full flex-col gap-1.5 rounded-2xl border border-border/70 bg-card/80 p-4 text-left outline-none transition-all hover:-translate-y-0.5 hover:border-ring hover:bg-accent/35 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/60"
              >
                <span className="text-xs font-medium tracking-wide text-ring uppercase">{label}</span>
                <span className="text-sm leading-snug font-medium">{question}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
