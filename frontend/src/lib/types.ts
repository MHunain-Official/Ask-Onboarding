// API shapes. They mirror backend/app/schemas.py and the SSE contract in
// AGENTS.md §5.4 / §6. Keep this file in sync when the backend changes.

export type UserRole = "employee" | "manager" | "admin";
export type AccessLevel = "all" | "managers" | "admins";
export type DocumentStatus = "queued" | "processing" | "ready" | "failed";
export type TicketStatus = "open" | "in_review" | "in_progress" | "answered" | "closed";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

export interface DocumentItem {
  id: string;
  filename: string;
  content_type: string;
  access_level: AccessLevel;
  version: number;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentContent {
  filename: string;
  content_type: string;
  text: string;
  highlight_char_start: number | null;
  highlight_char_end: number | null;
  highlight_page: number | null;
}

export interface Chunk {
  id: string;
  document_id: string;
  filename: string;
  heading: string | null;
  page_number: number | null;
  text: string;
  char_start: number;
  char_end: number;
}

export interface Citation {
  n: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number | null;
  heading: string | null;
  snippet: string;
  /** Offsets of this chunk in the full document text (exact passage). */
  char_start?: number | null;
  char_end?: number | null;
}

export interface TicketOffer {
  suggested_title: string;
  question: string;
}

export interface Ticket {
  id: string;
  title: string;
  question: string;
  user_id: string;
  user_name?: string | null;
  status: TicketStatus;
  conversation_id: string | null;
  created_at: string;
}

export interface TicketCreateRequest {
  title: string;
  question: string;
  conversation_id?: string | null;
}

// --- Chat ---

export type MessageRole = "user" | "assistant";

// `done` event status plus the states the UI adds itself.
export type AnswerStatus = "ok" | "no_answer" | "error" | "refused" | "ungrounded" | "partial";

export interface StoredMessage {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[] | null;
  ticket_offer: boolean;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: StoredMessage[];
}

export interface ChatRequest {
  conversation_id?: string | null;
  question: string;
  // "Regenerate" asks the server to skip the answer cache (§5.10 rule 6).
  bypass_cache?: boolean;
}

export type TraceStatus = "running" | "done" | "skipped" | "failed";

export interface TraceStep {
  step: string;
  status: TraceStatus;
  title: string;
  detail?: string;
  data?: Record<string, unknown>;
}

export type ChatEvent =
  | {
      event: "meta";
      data: {
        request_id: string;
        conversation_id: string;
        // Present when the answer is replayed from the answer cache (§5.10).
        cache_hit?: "none" | "exact" | "semantic";
        cached_at?: string;
      };
    }
  | { event: "trace"; data: TraceStep }
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: { items: Citation[] } }
  | { event: "ticket_offer"; data: TicketOffer }
  | { event: "done"; data: { message_id: string; status: AnswerStatus } }
  | {
      event: "error";
      data: { code: string; message: string; request_id?: string };
    };

// --- Admin ---

export interface AdminStats {
  total_requests: number;
  error_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  total_cost_usd: number;
  no_answer_rate: number;
  // Added in Phase 5 for the cache tiles (§5.10); optional until the backend ships them.
  cache_hit_rate?: number;
  llm_calls_avoided?: number;
  estimated_saved_usd?: number;
}

export interface LlmCallSummary {
  id: string;
  request_id: string;
  user_id: string;
  user_name?: string | null;
  question: string;
  status: AnswerStatus;
  cache_hit: "none" | "exact" | "semantic";
  model_used: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  latency_ms_total: number | null;
  created_at: string;
}

export interface RetrievedChunkScore {
  chunk_id: string;
  score: number;
}

export interface LlmCallDetail extends LlmCallSummary {
  conversation_id: string | null;
  retrieval_mode: string | null;
  retrieved_chunks: RetrievedChunkScore[] | null;
  system_prompt: string | null;
  messages_sent: unknown;
  model_response: string | null;
  tool_calls: unknown;
  provider: string | null;
  model_requested: string | null;
  fallback_used: boolean;
  usage_estimated: boolean;
  error_type: string | null;
  error_message: string | null;
  prompt_version: string | null;
  latency_ms_retrieval: number | null;
  latency_ms_first_token: number | null;
  latency_ms_generation: number | null;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  user_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface ProjectDocMeta {
  path: string;
  title: string;
  group: string;
}

export interface ProjectDocContent extends ProjectDocMeta {
  content: string;
}

export interface ProjectDocListResponse {
  items: ProjectDocMeta[];
  root_configured: boolean;
}

export interface ListResponse<T> {
  items: T[];
  total?: number;
}
