import { describe, expect, it } from "vitest";

import { parseChatEvent } from "@/lib/api";
import { readSseStream, SseParser } from "@/lib/sse";

function streamFrom(pieces: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const piece of pieces) controller.enqueue(encoder.encode(piece));
      controller.close();
    },
  });
}

async function collect(pieces: string[]) {
  const messages = [];
  for await (const message of readSseStream(streamFrom(pieces))) messages.push(message);
  return messages;
}

describe("SseParser", () => {
  it("parses an event with a name and data", () => {
    const parser = new SseParser();
    const messages = parser.feed('event: token\ndata: {"text":"hi"}\n\n');
    expect(messages).toEqual([{ event: "token", data: '{"text":"hi"}' }]);
  });

  it("defaults the event name to message", () => {
    const messages = new SseParser().feed("data: hello\n\n");
    expect(messages).toEqual([{ event: "message", data: "hello" }]);
  });

  it("joins multiple data lines with a newline", () => {
    const messages = new SseParser().feed("data: a\ndata: b\n\n");
    expect(messages[0].data).toBe("a\nb");
  });

  it("handles CRLF line endings (sse-starlette default)", () => {
    const messages = new SseParser().feed("event: done\r\ndata: {}\r\n\r\n");
    expect(messages).toEqual([{ event: "done", data: "{}" }]);
  });

  it("ignores comment and heartbeat lines", () => {
    const messages = new SseParser().feed(": ping\n\nevent: meta\ndata: {}\n\n");
    expect(messages).toEqual([{ event: "meta", data: "{}" }]);
  });

  it("waits for the blank line before emitting", () => {
    const parser = new SseParser();
    expect(parser.feed("event: token\ndata: x\n")).toEqual([]);
    expect(parser.feed("\n")).toHaveLength(1);
  });

  it("reassembles an event split across pieces, even mid-line", () => {
    const parser = new SseParser();
    expect(parser.feed("event: tok")).toEqual([]);
    expect(parser.feed('en\ndata: {"te')).toEqual([]);
    expect(parser.feed('xt":"a"}\n\n')).toEqual([{ event: "token", data: '{"text":"a"}' }]);
  });

  it("does not split a CRLF that arrives in two pieces", () => {
    const parser = new SseParser();
    expect(parser.feed("data: a\r")).toEqual([]);
    expect(parser.feed("\n\r\n")).toEqual([{ event: "message", data: "a" }]);
  });

  it("emits several events from one piece", () => {
    const messages = new SseParser().feed("data: 1\n\ndata: 2\n\n");
    expect(messages.map((message) => message.data)).toEqual(["1", "2"]);
  });

  it("keeps a value that contains a colon", () => {
    const messages = new SseParser().feed('data: {"url":"http://x"}\n\n');
    expect(messages[0].data).toBe('{"url":"http://x"}');
  });

  it("flushes a final event that has no trailing blank line", () => {
    const parser = new SseParser();
    parser.feed("event: done\ndata: {}");
    expect(parser.finish()).toEqual([{ event: "done", data: "{}" }]);
  });
});

describe("readSseStream", () => {
  it("yields events from a byte stream", async () => {
    const messages = await collect(["event: token\ndata: 1\n\n", "event: done\ndata: 2\n\n"]);
    expect(messages.map((message) => message.event)).toEqual(["token", "done"]);
  });

  it("keeps multi-byte characters that are split across chunks", async () => {
    const bytes = new TextEncoder().encode("data: héllo €\n\n");
    const cut = 8; // inside the two-byte "é"
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, cut));
        controller.enqueue(bytes.slice(cut));
        controller.close();
      },
    });
    const messages = [];
    for await (const message of readSseStream(stream)) messages.push(message);
    expect(messages[0].data).toBe("héllo €");
  });
});

describe("parseChatEvent", () => {
  it("returns a typed event for known names", () => {
    expect(parseChatEvent("token", '{"text":"a"}')).toEqual({
      event: "token",
      data: { text: "a" },
    });
  });

  it("parses retrieval-track breadcrumbs", () => {
    expect(
      parseChatEvent(
        "trace",
        JSON.stringify({
          step: "retrieve",
          status: "done",
          title: "Searching documents",
          detail: "hybrid · 3 passages",
        }),
      ),
    ).toEqual({
      event: "trace",
      data: {
        step: "retrieve",
        status: "done",
        title: "Searching documents",
        detail: "hybrid · 3 passages",
      },
    });
  });

  it("ignores unknown event names", () => {
    expect(parseChatEvent("surprise", "{}")).toBeNull();
  });

  it("ignores malformed JSON instead of throwing", () => {
    expect(parseChatEvent("token", "{oops")).toBeNull();
  });
});
