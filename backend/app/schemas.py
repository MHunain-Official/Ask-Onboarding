"""Pydantic request/response models.

These are the shapes that cross the HTTP boundary. They stay separate from
`app.models` (the DB tables) so a column can change without silently
changing the API, and vice versa.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import (
    AccessLevel,
    CacheHit,
    DocumentStatus,
    LlmCallStatus,
    MessageRole,
    TicketStatus,
    UserRole,
)

# --- Auth ---

# A light shape check, not full EmailStr validation: EmailStr's
# email-validator rejects reserved/special-use TLDs like ".local" as
# "not deliverable", but the seeded demo accounts intentionally use
# "@demo.local" (AGENTS.md §8.3 — this is a demo login, not a real mailbox).
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200, pattern=_EMAIL_PATTERN)


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: UserRole

    model_config = {"from_attributes": True}


# --- Documents ---


class DocumentPublic(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    access_level: AccessLevel
    version: int
    status: DocumentStatus
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentPublic]


class DocumentContentResponse(BaseModel):
    """Full document text plus, if `highlight_chunk` was requested, the
    offsets of the exact passage a citation points to (AGENTS.md §6)."""

    filename: str
    content_type: str
    text: str
    highlight_char_start: int | None = None
    highlight_char_end: int | None = None
    highlight_page: int | None = None


class ChunkPublic(BaseModel):
    """One retrievable passage, returned for the citation source-drawer."""

    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    heading: str | None
    page_number: int | None
    text: str
    char_start: int
    char_end: int


# --- Retrieval (debug/eval endpoint, §5.3) ---


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class RetrievedChunkItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int | None
    heading: str | None
    text: str
    score: float


class RetrieveResponse(BaseModel):
    items: list[RetrievedChunkItem]
    best_similarity: float
    passes_gate: bool


# --- Chat ---


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=1000)


class CitationItem(BaseModel):
    n: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int | None = None
    heading: str | None = None
    snippet: str
    # Offsets of this chunk in the full document text — used by the source
    # drawer to highlight the exact passage, not a fuzzy snippet match.
    char_start: int | None = None
    char_end: int | None = None


class TicketOfferPayload(BaseModel):
    suggested_title: str
    question: str


class MessagePublic(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[dict[str, object]] | None
    ticket_offer: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPublic(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    items: list[ConversationPublic]


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    messages: list[MessagePublic]


# --- Tickets ---


class TicketCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class TicketPublic(BaseModel):
    id: uuid.UUID
    title: str
    question: str
    user_id: uuid.UUID
    user_name: str | None = None
    status: TicketStatus
    conversation_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus


class TicketListResponse(BaseModel):
    items: list[TicketPublic]


# --- Admin (AGENTS.md §3.6: stats tiles, full llm_calls/audit_events trail) ---


class AdminStats(BaseModel):
    total_requests: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float
    no_answer_rate: float
    # Added in Phase 5 for the cache/efficiency tiles (§5.10).
    cache_hit_rate: float
    llm_calls_avoided: int
    estimated_saved_usd: float


class LlmCallSummary(BaseModel):
    """One row in the admin `/admin` request table."""

    id: uuid.UUID
    request_id: str
    user_id: uuid.UUID | None
    user_name: str | None = None
    question: str
    status: LlmCallStatus
    cache_hit: CacheHit
    model_used: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms_total: int | None
    created_at: datetime


class RetrievedChunkScore(BaseModel):
    chunk_id: str
    score: float


class LlmCallDetail(LlmCallSummary):
    """The full audit record for one answer attempt: exact prompt, exact
    response, every retrieved chunk and score, every timing (§3.6). Never
    served to a non-admin — see `require_role(UserRole.ADMIN)` on the router.
    """

    conversation_id: uuid.UUID | None
    retrieval_mode: str | None
    retrieved_chunks: list[RetrievedChunkScore] | None
    system_prompt: str | None
    messages_sent: list[dict[str, object]] | None
    model_response: str | None
    tool_calls: list[dict[str, object]] | None
    provider: str | None
    model_requested: str | None
    fallback_used: bool
    usage_estimated: bool
    error_type: str | None
    error_message: str | None
    prompt_version: str | None
    latency_ms_retrieval: int | None
    latency_ms_first_token: int | None
    latency_ms_generation: int | None


class LlmCallListResponse(BaseModel):
    items: list[LlmCallSummary]
    total: int


class AuditEventPublic(BaseModel):
    """One append-only audit row (§3.6), as shown on the admin-only audit
    tab. Admin role is enforced in `routers/admin.py`, not here."""

    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None
    # Named `detail` (not `details`) to match `frontend/src/lib/types.ts`;
    # mapped explicitly from the `AuditEvent.details` column in the service.
    detail: dict[str, object] | None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventPublic]
    total: int


# --- Admin project docs (review ARCHITECTURE / ADRs / rules in-app) ---


class ProjectDocMeta(BaseModel):
    path: str
    title: str
    group: str


class ProjectDocListResponse(BaseModel):
    items: list[ProjectDocMeta]
    root_configured: bool


class ProjectDocContent(BaseModel):
    path: str
    title: str
    group: str
    content: str
