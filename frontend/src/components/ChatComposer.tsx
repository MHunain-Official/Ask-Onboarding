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
      className="border-t bg-card p-3"
    >
      <div className="mx-auto flex max-w-3xl items-end gap-2">
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
            className="max-h-40 min-h-12 resize-none"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Enter to send, Shift+Enter for a new line · {text.length}/{MAX_QUESTION_CHARS}
          </p>
        </div>
        {isStreaming ? (
          <Button type="button" variant="outline" size="lg" onClick={onStop}>
            <Square aria-hidden="true" />
            Stop
          </Button>
        ) : (
          <Button type="submit" size="lg" disabled={text.trim() === ""}>
            <SendHorizontal aria-hidden="true" />
            Send
          </Button>
        )}
      </div>
    </form>
  );
}
