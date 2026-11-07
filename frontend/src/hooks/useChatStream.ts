"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, getConversation, streamChat } from "@/lib/api";
import type { ChatEvent, Citation, StoredMessage, TicketOffer, TraceStep } from "@/lib/types";

export type ChatItemStatus =
  "streaming" | "ok" | "no_answer" | "error" | "refused" | "ungrounded" | "partial" | "stopped";

export interface ChatItem {
  id: string; // stable local React key
  messageId?: string; // server id, known after the "done" event
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  ticketOffer: TicketOffer | null;
  status: ChatItemStatus;
  errorMessage?: string;
  requestId?: string;
  cachedAt?: string;
  /** Live pipeline breadcrumbs from SSE `trace` events. */
  trace: TraceStep[];
}

let localIdCounter = 0;
function newLocalId(): string {
  localIdCounter += 1;
  return `local-${localIdCounter}`;
}

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "You're asking too fast. Wait a few seconds and try again.";
    if (error.status >= 500)
      return "The AI service is unavailable. Your question was saved; retry in a moment.";
    return error.message;
  }
  return "The connection was interrupted. Your question was saved; retry in a moment.";
}

// Pure reducer-style helper: apply one SSE event to the assistant message.
function applyEvent(item: ChatItem, event: ChatEvent): ChatItem {
  switch (event.event) {
    case "meta":
      return {
        ...item,
        requestId: event.data.request_id,
        cachedAt:
          event.data.cache_hit && event.data.cache_hit !== "none"
            ? (event.data.cached_at ?? "saved")
            : undefined,
      };
    case "trace":
      return {
        ...item,
        cachedAt:
          event.data.step === "cache" &&
          event.data.status === "done" &&
          event.data.data?.cache_hit === "exact"
            ? "saved"
            : item.cachedAt,
        trace: upsertTrace(item.trace, event.data),
      };
    case "token":
      return { ...item, content: item.content + event.data.text };
    case "citations":
      return { ...item, citations: event.data.items };
    case "ticket_offer":
      return { ...item, ticketOffer: event.data };
    case "done":
      return {
        ...item,
        messageId: event.data.message_id,
        status: event.data.status,
      };
    case "error":
      return {
        ...item,
        status: "error",
        errorMessage: event.data.message,
        requestId: event.data.request_id ?? item.requestId,
      };
  }
}

function upsertTrace(steps: TraceStep[], next: TraceStep): TraceStep[] {
  const index = steps.findIndex((step) => step.step === next.step);
  if (index === -1) return [...steps, next];
  const copy = steps.slice();
  copy[index] = next;
  return copy;
}

function fromStored(message: StoredMessage, previousQuestion: string): ChatItem {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations ?? [],
    ticketOffer: message.ticket_offer
      ? {
          suggested_title: previousQuestion.slice(0, 80),
          question: previousQuestion,
        }
      : null,
    status: "ok",
    trace: [],
  };
}

export function useChatStream(onConversationStarted: () => void) {
  const [items, setItems] = useState<ChatItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationRef = useRef<string | null>(null);

  const updateItem = useCallback((id: string, change: (item: ChatItem) => ChatItem) => {
    setItems((current) => current.map((item) => (item.id === id ? change(item) : item)));
  }, []);

  const runStream = useCallback(
    async (question: string, assistantId: string, bypassCache: boolean) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);
      const apply = (change: (item: ChatItem) => ChatItem) => updateItem(assistantId, change);
      let finished = false;

      try {
        const events = streamChat(
          {
            conversation_id: conversationRef.current,
            question,
            bypass_cache: bypassCache || undefined,
          },
          controller.signal,
        );
        for await (const event of events) {
          if (event.event === "meta") {
            const isNew = conversationRef.current === null;
            conversationRef.current = event.data.conversation_id;
            setConversationId(event.data.conversation_id);
            if (isNew) onConversationStarted();
          }
          if (event.event === "done" || event.event === "error") finished = true;
          apply((item) => applyEvent(item, event));
        }
        if (!finished) {
          // The stream closed without "done": keep what arrived, mark it partial (§5.12 #9).
          apply((item) => ({
            ...item,
            status: item.content ? "partial" : "error",
            errorMessage: item.content ? undefined : friendlyError(null),
          }));
        }
      } catch (error) {
        if (controller.signal.aborted) {
          apply((item) => ({ ...item, status: "stopped" }));
        } else {
          apply((item) => ({
            ...item,
            status: item.content ? "partial" : "error",
            errorMessage: friendlyError(error),
            requestId: error instanceof ApiError ? error.requestId : item.requestId,
          }));
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [onConversationStarted, updateItem],
  );

  const startAssistantItem = useCallback((): string => {
    const id = newLocalId();
    setItems((current) => [
      ...current,
      {
        id,
        role: "assistant",
        content: "",
        citations: [],
        ticketOffer: null,
        status: "streaming",
        trace: [],
      },
    ]);
    return id;
  }, []);

  const send = useCallback(
    (question: string) => {
      const userItem: ChatItem = {
        id: newLocalId(),
        role: "user",
        content: question,
        citations: [],
        ticketOffer: null,
        status: "ok",
        trace: [],
      };
      setItems((current) => [...current, userItem]);
      void runStream(question, startAssistantItem(), false);
    },
    [runStream, startAssistantItem],
  );

  // Retry and Regenerate both re-ask the question just before the assistant message.
  const reask = useCallback(
    (assistantId: string, bypassCache: boolean) => {
      const index = items.findIndex((item) => item.id === assistantId);
      const question = items[index - 1]?.content;
      if (index < 1 || !question) return;
      updateItem(assistantId, (item) => ({
        ...item,
        content: "",
        citations: [],
        ticketOffer: null,
        status: "streaming",
        errorMessage: undefined,
        cachedAt: undefined,
        trace: [],
      }));
      void runStream(question, assistantId, bypassCache);
    },
    [items, runStream, updateItem],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    conversationRef.current = null;
    setConversationId(null);
    setItems([]);
    setHistoryError(null);
  }, []);

  const openConversation = useCallback(async (id: string) => {
    abortRef.current?.abort();
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const detail = await getConversation(id);
      let previousQuestion = "";
      const loaded = detail.messages.map((message) => {
        if (message.role === "user") previousQuestion = message.content;
        return fromStored(message, previousQuestion);
      });
      conversationRef.current = id;
      setConversationId(id);
      setItems(loaded);
    } catch {
      setHistoryError("We couldn't load that conversation.");
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  return {
    items,
    conversationId,
    isStreaming,
    isLoadingHistory,
    historyError,
    send,
    retry: (assistantId: string) => reask(assistantId, false),
    regenerate: (assistantId: string) => reask(assistantId, true),
    stop,
    reset,
    openConversation,
  };
}
