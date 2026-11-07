"""SQLAlchemy ORM models for every table in the playbook data model (§4).

One file, on purpose: the owner needs to see the whole schema at a glance.
Enums mirror the Postgres ENUM types created in the first migration.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Computed, ForeignKey, Index, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

EMBEDDING_DIMENSIONS = 1536


def pg_enum(enum_cls: type[StrEnum], name: str) -> SqlEnum:
    """Build a Postgres ENUM column type that stores `.value` (e.g. "employee"),
    not `.name` (e.g. "EMPLOYEE").

    SQLAlchemy's default is `.name` — easy to miss, and it only shows up once
    you insert against a real Postgres enum type, which is exactly how this
    was caught. `values_callable` fixes it; the migration's CREATE TYPE
    statements use the same lowercase values.
    """
    return SqlEnum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class UserRole(StrEnum):
    """Access level for a human user. Higher roles see strictly more."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    ADMIN = "admin"


class AccessLevel(StrEnum):
    """Who may read a document or chunk.

    `all` = every employee · `managers` = managers+admins · `admins` = admins only.
    """

    ALL = "all"
    MANAGERS = "managers"
    ADMINS = "admins"


class DocumentStatus(StrEnum):
    """Lifecycle of one uploaded document version."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MessageRole(StrEnum):
    """Who authored a chat message."""

    USER = "user"
    ASSISTANT = "assistant"


class TicketStatus(StrEnum):
    """Lifecycle of a help-desk ticket (staff update these; employees read them)."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    CLOSED = "closed"


class LlmCallStatus(StrEnum):
    """Outcome of one answer-generation attempt, recorded for every call."""

    OK = "ok"
    NO_ANSWER = "no_answer"
    ERROR = "error"
    REFUSED = "refused"
    UNGROUNDED = "ungrounded"
    PARTIAL = "partial"


class CacheHit(StrEnum):
    """Which cache layer served an answer, if any (§5.10)."""

    NONE = "none"
    EXACT = "exact"
    SEMANTIC = "semantic"


def _uuid_pk() -> Mapped[uuid.UUID]:
    """Shared primary-key column: random UUID generated in Python."""
    return mapped_column(primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("filename", name="uq_documents_filename"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    filename: Mapped[str]
    content_type: Mapped[str]
    storage_path: Mapped[str]
    content_hash: Mapped[str]
    access_level: Mapped[AccessLevel] = mapped_column(
        pg_enum(AccessLevel, "access_level"), default=AccessLevel.ALL
    )
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"), default=DocumentStatus.QUEUED
    )
    error_message: Mapped[str | None] = mapped_column(default=None)
    chunk_count: Mapped[int] = mapped_column(default=0)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    document_version: Mapped[int]
    chunk_index: Mapped[int]
    text: Mapped[str]
    text_hash: Mapped[str]
    page_number: Mapped[int | None] = mapped_column(default=None)
    char_start: Mapped[int]
    char_end: Mapped[int]
    heading: Mapped[str | None] = mapped_column(default=None)
    token_count: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    # Generated column (STORED tsvector); the migration creates it with raw
    # SQL (its real source of truth). `Computed()` here is only a hint that
    # tells the ORM this column is server-generated, so it is left out of
    # every INSERT/UPDATE — Postgres rejects any value, even NULL, sent for
    # a GENERATED ALWAYS column, which is exactly the bug this caught.
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(text, ''))"), nullable=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(pg_enum(AccessLevel, "access_level"))

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(pg_enum(MessageRole, "message_role"))
    content: Mapped[str]
    citations: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    ticket_offer: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str]
    question: Mapped[str]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus, "ticket_status"), default=TicketStatus.OPEN
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user: Mapped["User"] = relationship()


class LlmCall(Base):
    """One row per answer-generation attempt. Full audit trail (§3.6).

    Never truncated except the 100 KB per-field cap enforced in application
    code before insert; never log API keys or cookies here.
    """

    __tablename__ = "llm_calls"
    __table_args__ = (Index("ix_llm_calls_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    request_id: Mapped[str]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )
    question: Mapped[str]
    retrieval_mode: Mapped[str | None] = mapped_column(default=None)
    retrieved_chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    retrieved_scores: Mapped[list[float] | None] = mapped_column(JSON, default=None)
    system_prompt: Mapped[str | None] = mapped_column(default=None)
    messages_sent: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    model_response: Mapped[str | None] = mapped_column(default=None)
    tool_calls: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    model: Mapped[str | None] = mapped_column(default=None)
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)
    estimated_cost_usd: Mapped[float | None] = mapped_column(default=None)
    latency_ms_total: Mapped[int | None] = mapped_column(default=None)
    latency_ms_retrieval: Mapped[int | None] = mapped_column(default=None)
    latency_ms_first_token: Mapped[int | None] = mapped_column(default=None)
    latency_ms_generation: Mapped[int | None] = mapped_column(default=None)
    status: Mapped[LlmCallStatus] = mapped_column(pg_enum(LlmCallStatus, "llm_call_status"))
    cache_hit: Mapped[CacheHit] = mapped_column(
        pg_enum(CacheHit, "cache_hit"), default=CacheHit.NONE
    )
    provider: Mapped[str | None] = mapped_column(default=None)
    model_requested: Mapped[str | None] = mapped_column(default=None)
    model_used: Mapped[str | None] = mapped_column(default=None)
    fallback_used: Mapped[bool] = mapped_column(default=False)
    usage_estimated: Mapped[bool] = mapped_column(default=False)
    error_type: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    prompt_version: Mapped[str] = mapped_column(default="v1")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AnswerCache(Base):
    """ACL-scoped exact/semantic answer cache (§5.10). `scope` isolates roles."""

    __tablename__ = "answer_cache"
    __table_args__ = (
        UniqueConstraint(
            "scope", "question_hash", "prompt_version", "model", name="uq_answer_cache_key"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    scope: Mapped[str]
    question_hash: Mapped[str]
    question_text: Mapped[str]
    question_embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    answer_text: Mapped[str]
    citations: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    source_docs: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    prompt_version: Mapped[str]
    model: Mapped[str]
    hit_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    invalidated_at: Mapped[datetime | None] = mapped_column(default=None)


class QueryEmbeddingCache(Base):
    """Caches query embeddings so repeated/paraphrased questions skip a call."""

    __tablename__ = "query_embedding_cache"

    question_hash: Mapped[str] = mapped_column(primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UsageDaily(Base):
    """Per-user, per-day token/cost rollup used for budget enforcement (§5.10 L7)."""

    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("date", "user_id", name="uq_usage_daily_date_user"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    date: Mapped[datetime]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    requests: Mapped[int] = mapped_column(default=0)
    cache_hits: Mapped[int] = mapped_column(default=0)


class AuditEvent(Base):
    """Append-only security/activity log (§3.6). The app DB user may only
    INSERT and SELECT on this table — enforced by a DB grant, not by code."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    request_id: Mapped[str | None] = mapped_column(default=None)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    event_type: Mapped[str]
    details: Mapped[dict[str, object] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Feedback(Base):
    """Optional thumbs up/down on an assistant message. Built only if time
    remains (AGENTS.md §1); schema included now so the migration is complete."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _uuid_pk()
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int]
    comment: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
