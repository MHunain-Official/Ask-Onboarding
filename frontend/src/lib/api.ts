// The one typed API client. Every call goes to our own backend under /api/*
// (Next.js rewrites it), so the session cookie is same-origin and no key
// ever reaches the browser.

import { readSseStream } from "@/lib/sse";
import type {
  AccessLevel,
  AdminStats,
  AuditEvent,
  Chunk,
  ChatEvent,
  ChatRequest,
  ConversationDetail,
  ConversationSummary,
  DocumentContent,
  DocumentItem,
  ListResponse,
  LlmCallDetail,
  LlmCallSummary,
  Ticket,
  TicketCreateRequest,
  User,
} from "@/lib/types";

// State-changing requests must send this header. Browsers cannot add a custom
// header to a cross-site form post, so together with SameSite=Lax cookies it
// blocks CSRF (AGENTS.md §3.2).
export const CSRF_HEADER_NAME = "X-Requested-With";
export const CSRF_HEADER_VALUE = "ask-onboarding";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function csrfHeaders(): Record<string, string> {
  return { [CSRF_HEADER_NAME]: CSRF_HEADER_VALUE };
}

// Where to send the user when the session is gone. Draft questions live in
// sessionStorage (see useChatStream), so they survive the round trip.
function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  const next = encodeURIComponent(window.location.pathname);
  window.location.assign(`/login?next=${next}`);
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  let message = `Request failed (${response.status})`;
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") message = detail;
    }
  } catch {
    // Not JSON: keep the generic message. Never show raw server text.
  }
  return new ApiError(response.status, message, requestId);
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  json?: unknown;
  signal?: AbortSignal;
  // The login call itself must not bounce to /login on 401.
  redirectOn401?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  if (method !== "GET") Object.assign(headers, csrfHeaders());
  if (options.json !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: options.json === undefined ? undefined : JSON.stringify(options.json),
    signal: options.signal,
  });

  if (response.status === 401 && options.redirectOn401 !== false) redirectToLogin();
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Auth ---

export function login(email: string): Promise<User> {
  return request<User>("/api/auth/login", {
    method: "POST",
    json: { email },
    redirectOn401: false,
  });
}

export function logout(): Promise<void> {
  return request<void>("/api/auth/logout", {
    method: "POST",
    redirectOn401: false,
  });
}

export function getMe(): Promise<User> {
  return request<User>("/api/auth/me", { redirectOn401: false });
}

// --- Documents ---

export async function listDocuments(): Promise<DocumentItem[]> {
  const body = await request<ListResponse<DocumentItem>>("/api/documents");
  return body.items;
}

export function deleteDocument(documentId: string): Promise<void> {
  return request<void>(`/api/documents/${documentId}`, { method: "DELETE" });
}

export function getDocumentContent(
  documentId: string,
  highlightChunkId?: string,
): Promise<DocumentContent> {
  const query = highlightChunkId ? `?highlight_chunk=${highlightChunkId}` : "";
  return request<DocumentContent>(`/api/documents/${documentId}/content${query}`);
}

export function getChunk(chunkId: string): Promise<Chunk> {
  return request<Chunk>(`/api/chunks/${chunkId}`);
}

// Upload uses XMLHttpRequest instead of fetch because fetch cannot report
// upload progress, and the upload page shows a progress bar per file.
export function uploadDocument(
  file: File,
  accessLevel: AccessLevel,
  onProgress: (fraction: number) => void,
): Promise<DocumentItem> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("access_level", accessLevel);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/documents");
    xhr.withCredentials = true;
    xhr.setRequestHeader(CSRF_HEADER_NAME, CSRF_HEADER_VALUE);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error while uploading"));
    xhr.onload = () => {
      if (xhr.status === 401) redirectToLogin();
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as DocumentItem);
        return;
      }
      reject(new ApiError(xhr.status, uploadErrorMessage(xhr)));
    };
    xhr.send(form);
  });
}

function uploadErrorMessage(xhr: XMLHttpRequest): string {
  try {
    const body = JSON.parse(xhr.responseText) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // fall through to the generic message
  }
  return `Upload failed (${xhr.status})`;
}

// --- Conversations ---

export async function listConversations(): Promise<ConversationSummary[]> {
  const body = await request<ListResponse<ConversationSummary>>("/api/conversations");
  return body.items;
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/api/conversations/${conversationId}`);
}

// --- Tickets ---

export async function listTickets(): Promise<Ticket[]> {
  const body = await request<ListResponse<Ticket>>("/api/tickets");
  return body.items;
}

export function createTicket(payload: TicketCreateRequest): Promise<Ticket> {
  return request<Ticket>("/api/tickets", { method: "POST", json: payload });
}

// --- Admin ---

export function getAdminStats(): Promise<AdminStats> {
  return request<AdminStats>("/api/admin/stats");
}

export interface LlmCallFilters {
  status?: string;
  // Exact match only (AGENTS.md §6: `GET /api/admin/llm-calls?user_id=`).
  // The admin page validates this looks like a UUID before sending it.
  userId?: string;
}

export async function listLlmCalls(filters: LlmCallFilters): Promise<LlmCallSummary[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.userId) params.set("user_id", filters.userId);
  const query = params.toString();
  const body = await request<ListResponse<LlmCallSummary>>(
    `/api/admin/llm-calls${query ? `?${query}` : ""}`,
  );
  return body.items;
}

export function getLlmCall(callId: string): Promise<LlmCallDetail> {
  return request<LlmCallDetail>(`/api/admin/llm-calls/${callId}`);
}

export async function listAuditEvents(): Promise<AuditEvent[]> {
  const body = await request<ListResponse<AuditEvent>>("/api/admin/audit-events");
  return body.items;
}

// --- Chat streaming (SSE over POST) ---

const CHAT_EVENT_NAMES = new Set(["meta", "token", "citations", "ticket_offer", "done", "error"]);

// Turns one raw SSE message into a typed ChatEvent, or null if it is
// unknown or malformed (we ignore those instead of crashing the stream).
export function parseChatEvent(name: string, data: string): ChatEvent | null {
  if (!CHAT_EVENT_NAMES.has(name)) return null;
  try {
    return { event: name, data: JSON.parse(data) } as ChatEvent;
  } catch {
    return null;
  }
}

export async function* streamChat(
  payload: ChatRequest,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...csrfHeaders(),
    },
    credentials: "include",
    body: JSON.stringify(payload),
    signal,
  });

  if (response.status === 401) redirectToLogin();
  if (!response.ok || !response.body) throw await errorFromResponse(response);

  for await (const message of readSseStream(response.body)) {
    const event = parseChatEvent(message.event, message.data);
    if (event) yield event;
  }
}
