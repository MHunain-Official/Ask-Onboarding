"use client";

import { SendHorizontal, Square } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const MAX_QUESTION_CHARS = 1000; // keep in sync with MAX_QUESTION_CHARS in .env
const DRAFT_KEY = "ask-onboarding:draft";

interface ChatComposerProps {
  isStreaming: boolean;
  onSend: (question: string) => void;
  onStop: () => void;
}

export function ChatComposer({ isStreaming, onSend, onStop }: ChatComposerProps) {
  const [text, setText] = useState("");

  // The draft survives a session-expiry redirect to /login (§5.12 #12).
  useEffect(() => {
    setText(sessionStorage.getItem(DRAFT_KEY) ?? "");
  }, []);

  function update(value: string) {
    setText(value);
    sessionStorage.setItem(DRAFT_KEY, value);
  }

  function submit() {
    const question = text.trim();
    if (!question || isStreaming) return;
    onSend(question);
    update("");
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="border-t border-border/60 bg-background/70 p-3 backdrop-blur-md sm:p-4"
    >
      <div className="surface-glass mx-auto flex max-w-3xl items-end gap-2 rounded-2xl p-2 sm:gap-3 sm:p-2.5">
        <div className="min-w-0 flex-1">
          <label htmlFor="question" className="sr-only">
            Your question
          </label>
          <Textarea
            id="question"
            value={text}
            maxLength={MAX_QUESTION_CHARS}
            rows={2}
            placeholder="Ask about policies, benefits, tools…"
            onChange={(event) => update(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            className="max-h-40 min-h-12 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
          />
          <p className="px-3 pb-1 text-xs text-muted-foreground">
            Enter to send · Shift+Enter for a new line · {text.length}/{MAX_QUESTION_CHARS}
          </p>
        </div>
        {isStreaming ? (
          <Button type="button" variant="outline" size="lg" className="rounded-xl" onClick={onStop}>
            <Square aria-hidden="true" />
            Stop
          </Button>
        ) : (
          <Button
            type="submit"
            size="lg"
            className="rounded-xl"
            disabled={text.trim() === ""}
            aria-label="Send question"
          >
            <SendHorizontal aria-hidden="true" />
            <span className="hidden sm:inline">Send</span>
          </Button>
        )}
      </div>
    </form>
  );
}
