// A tiny Server-Sent Events parser for fetch() streams.
//
// Why not EventSource? It can only send GET requests, and our chat endpoint
// is a POST with a JSON body. So we read the response body ourselves.
//
// SSE wire format (the part we need):
//   event: token          <- optional event name
//   data: {"text":"hi"}   <- one or more data lines
//   <blank line>          <- ends the event
//   : heartbeat           <- comment line, ignored

export interface SseMessage {
  event: string;
  data: string;
}

// Incremental parser: feed it text pieces as they arrive, get finished events back.
export class SseParser {
  private buffer = "";
  private eventName = "";
  private dataLines: string[] = [];

  feed(piece: string): SseMessage[] {
    this.buffer += piece;
    const messages: SseMessage[] = [];
    // A line ends with \r\n, \n or \r. A trailing lone \r might be half of
    // \r\n, so we keep it in the buffer until the next piece arrives.
    const lines = this.buffer.split(/\r\n|\n|\r(?!$)/);
    this.buffer = lines.pop() ?? "";
    for (const line of lines) {
      const message = this.handleLine(line);
      if (message) messages.push(message);
    }
    return messages;
  }

  // Call when the stream closes: flushes a final event with no blank line after it.
  finish(): SseMessage[] {
    const messages: SseMessage[] = [];
    if (this.buffer !== "") {
      const message = this.handleLine(this.buffer.replace(/\r$/, ""));
      if (message) messages.push(message);
      this.buffer = "";
    }
    const last = this.dispatch();
    if (last) messages.push(last);
    return messages;
  }

  private handleLine(line: string): SseMessage | null {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return null; // comment / heartbeat

    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "event") this.eventName = value;
    else if (field === "data") this.dataLines.push(value);
    return null;
  }

  private dispatch(): SseMessage | null {
    if (this.dataLines.length === 0) {
      this.eventName = "";
      return null;
    }
    const message = {
      event: this.eventName || "message",
      data: this.dataLines.join("\n"),
    };
    this.eventName = "";
    this.dataLines = [];
    return message;
  }
}

// Reads a fetch() response body and yields one SseMessage per event.
export async function* readSseStream(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  // stream:true keeps multi-byte characters intact when they are split across chunks.
  const decoder = new TextDecoder("utf-8");
  const parser = new SseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.feed(decoder.decode(value, { stream: true }));
    }
    yield* parser.feed(decoder.decode());
    yield* parser.finish();
  } finally {
    reader.releaseLock();
  }
}
