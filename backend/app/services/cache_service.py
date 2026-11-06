"""ACL-scoped exact answer cache (AGENTS.md §5.10 L1, §5.10 cache safety
rules). Every lookup and write is scoped by `scope` — the user's sorted
allowed access levels — so an entry built for an employee can never be
served to, or overwritten by, a different scope.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AccessLevel, AnswerCache, Document, DocumentStatus
from app.services.text_normalize import normalize_question


@dataclass(frozen=True)
class CachedAnswer:
    answer_text: str
    citations: list[dict[str, object]]


def _now_naive_utc() -> datetime:
    """The `DateTime()` columns here are naive but always UTC (no tz info
    stored); strip tzinfo so comparisons against them don't raise."""
    return datetime.now(UTC).replace(tzinfo=None)


def cache_scope(allowed_levels: list[AccessLevel]) -> str:
    """`"all"` for an employee, `"all+managers"` for a manager/admin. The
    sort makes the string independent of the order `allowed_levels` was
    built in."""
    return "+".join(sorted(level.value for level in allowed_levels))


def hash_question(question: str) -> str:
    return hashlib.sha256(normalize_question(question).encode("utf-8")).hexdigest()


def get_cached_answer(
    db: Session,
    *,
    question: str,
    scope: str,
    prompt_version: str,
    model: str,
    allowed_levels: list[AccessLevel],
) -> CachedAnswer | None:
    """Exact-cache lookup. Re-validates every source document on every hit
    (cache safety rule 2): a re-upload, delete, or ACL change makes a stale
    answer impossible to serve, even if the row is still technically there.
    """
    row = (
        db.query(AnswerCache)
        .filter(
            AnswerCache.scope == scope,
            AnswerCache.question_hash == hash_question(question),
            AnswerCache.prompt_version == prompt_version,
            AnswerCache.model == model,
            AnswerCache.invalidated_at.is_(None),
        )
        .first()
    )
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at < _now_naive_utc():
        return None
    if not _source_docs_still_valid(db, row.source_docs, allowed_levels):
        row.invalidated_at = _now_naive_utc()
        db.commit()
        return None

    row.hit_count += 1
    db.commit()
    return CachedAnswer(answer_text=row.answer_text, citations=row.citations or [])


def store_answer(
    db: Session,
    *,
    question: str,
    scope: str,
    prompt_version: str,
    model: str,
    answer_text: str,
    citations: list[dict[str, object]],
    source_docs: list[dict[str, object]],
    question_embedding: list[float],
    ttl_hours: int,
) -> None:
    question_hash = hash_question(question)
    expires_at = _now_naive_utc() + timedelta(hours=ttl_hours)
    existing = (
        db.query(AnswerCache)
        .filter(
            AnswerCache.scope == scope,
            AnswerCache.question_hash == question_hash,
            AnswerCache.prompt_version == prompt_version,
            AnswerCache.model == model,
        )
        .first()
    )
    if existing is not None:
        existing.answer_text = answer_text
        existing.citations = citations
        existing.source_docs = source_docs
        existing.question_embedding = question_embedding
        existing.invalidated_at = None
        existing.expires_at = expires_at
    else:
        db.add(
            AnswerCache(
                scope=scope,
                question_hash=question_hash,
                question_text=question,
                question_embedding=question_embedding,
                answer_text=answer_text,
                citations=citations,
                source_docs=source_docs,
                prompt_version=prompt_version,
                model=model,
                expires_at=expires_at,
            )
        )
    db.commit()


def build_source_doc_refs(db: Session, document_ids: set[str]) -> list[dict[str, object]]:
    """`{"document_id", "version"}` for every document a cached answer
    depended on, so a later re-upload/version bump invalidates it on the
    next lookup (cache safety rule 2)."""
    if not document_ids:
        return []
    ids = [uuid.UUID(document_id) for document_id in document_ids]
    documents = db.query(Document).filter(Document.id.in_(ids)).all()
    return [
        {"document_id": str(document.id), "version": document.version} for document in documents
    ]


def invalidate_cache_for_document(db: Session, document_id: object) -> int:
    """Called on re-upload/delete so a cached answer can never outlive the
    document version it was built from. Returns the number of rows marked
    invalid."""
    document_id_str = str(document_id)
    rows = db.query(AnswerCache).filter(AnswerCache.invalidated_at.is_(None)).all()
    count = 0
    for row in rows:
        if any(ref.get("document_id") == document_id_str for ref in row.source_docs):
            row.invalidated_at = _now_naive_utc()
            count += 1
    if count:
        db.commit()
    return count


def _source_docs_still_valid(
    db: Session, source_docs: list[dict[str, object]], allowed_levels: list[AccessLevel]
) -> bool:
    for ref in source_docs:
        document = db.get(Document, uuid.UUID(str(ref["document_id"])))
        if document is None:
            return False
        if document.version != ref["version"]:
            return False
        if document.status != DocumentStatus.READY:
            return False
        if document.access_level not in allowed_levels:
            return False
    return True
