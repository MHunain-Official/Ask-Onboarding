"""Parse -> chunk -> embed -> atomically swap chunks for one document (§5.1).

This is the single function both the worker's poll loop and tests call
directly. It always leaves the document in a safe state: `ready` with new
chunks, or `failed` with the *old* chunks still in place and still serving
answers (AGENTS.md §5.1: a half-indexed document must never exist).
"""

import hashlib
import uuid
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings.base import Embedder
from app.ingestion.chunker import Chunk, split_text_into_chunks
from app.ingestion.parsers import PageMarker, ParsedDocument, ParseError, parse_by_filename
from app.models import Document, DocumentChunk, DocumentStatus
from app.security_hardening import matches_injection_pattern
from app.services.audit_service import record_audit_event

logger = structlog.get_logger(__name__)


def process_document(session: Session, document_id: uuid.UUID, embedder: Embedder) -> None:
    """Process one document end to end. Safe to call directly (tests do) or
    from the worker's claim loop."""
    document = session.get(Document, document_id)
    if document is None:
        logger.warning("ingestion.document_missing", document_id=str(document_id))
        return

    document.status = DocumentStatus.PROCESSING
    session.commit()

    settings = get_settings()
    try:
        raw_bytes = _read_file(document.storage_path)
        parsed = parse_by_filename(document.filename, raw_bytes, max_pages=settings.max_pdf_pages)
        _flag_injection_patterns_in_document(session, document, parsed.text)
        chunks = split_text_into_chunks(
            parsed.text,
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
            is_markdown=document.filename.lower().endswith(".md"),
        )
        if not chunks:
            raise ParseError("Document produced no chunks after splitting")

        hashes, embeddings = _reuse_or_embed(session, document.id, chunks, embedder)
        _swap_chunks(session, document, chunks, hashes, embeddings, parsed)
        logger.info("ingestion.ready", document_id=str(document.id), chunk_count=len(chunks))
    except Exception as exc:  # noqa: BLE001 - any failure must mark the doc failed, not crash the worker
        session.rollback()
        _mark_failed(session, document.id, str(exc))
        logger.error("ingestion.failed", document_id=str(document.id), error=str(exc))


def _read_file(storage_path: str) -> bytes:
    return Path(storage_path).read_bytes()


def _flag_injection_patterns_in_document(session: Session, document: Document, text: str) -> None:
    """Log-only prompt-injection flagger for uploaded documents (§5.8),
    the sibling of the one `answer_service.py` runs on questions. Ingestion
    never fails or rewrites content because of this — it only gives the
    admin audit page a signal that this document is worth a human look."""
    if not matches_injection_pattern(text):
        return
    record_audit_event(
        session,
        event_type="injection_pattern_flagged",
        details={
            "source": "document",
            "document_id": str(document.id),
            "filename": document.filename,
        },
    )


def _reuse_or_embed(
    session: Session, document_id: uuid.UUID, chunks: list[Chunk], embedder: Embedder
) -> tuple[list[str], list[list[float]]]:
    """Hash each chunk's embedded text; reuse the old vector for any hash
    that already exists among this document's current chunks (re-upload with
    partially unchanged content), and embed only what's new."""
    hashes = [hashlib.sha256(chunk.text.encode("utf-8")).hexdigest() for chunk in chunks]

    existing = (
        session.query(DocumentChunk.text_hash, DocumentChunk.embedding)
        .filter(DocumentChunk.document_id == document_id, DocumentChunk.text_hash.in_(set(hashes)))
        .all()
    )
    reusable = {row.text_hash: list(row.embedding) for row in existing}

    embeddings: list[list[float] | None] = [reusable.get(h) for h in hashes]
    missing_indices = [i for i, vector in enumerate(embeddings) if vector is None]
    if missing_indices:
        missing_texts = [chunks[i].text for i in missing_indices]
        new_vectors = embedder.embed_texts(missing_texts)
        for index, vector in zip(missing_indices, new_vectors, strict=True):
            embeddings[index] = vector

    assert all(vector is not None for vector in embeddings)  # every slot was filled above
    return hashes, embeddings  # type: ignore[return-value]


def _swap_chunks(
    session: Session,
    document: Document,
    chunks: list[Chunk],
    hashes: list[str],
    embeddings: list[list[float]],
    parsed: ParsedDocument,
) -> None:
    """Delete the old chunks and insert the new ones in one transaction, so
    a reader never sees a document with zero or half-swapped chunks."""
    session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

    rows = zip(chunks, hashes, embeddings, strict=True)
    for index, (chunk, text_hash, embedding) in enumerate(rows):
        session.add(
            DocumentChunk(
                document_id=document.id,
                document_version=document.version,
                chunk_index=index,
                text=chunk.text,
                text_hash=text_hash,
                page_number=_page_for_offset(parsed.pages, chunk.char_start),
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                heading=chunk.heading,
                token_count=chunk.token_count,
                embedding=embedding,
                access_level=document.access_level,
            )
        )

    document.status = DocumentStatus.READY
    document.error_message = None
    document.chunk_count = len(chunks)
    session.commit()


def _page_for_offset(pages: list[PageMarker], offset: int) -> int | None:
    for page in pages:
        if page.char_start <= offset < page.char_end:
            return page.page_number
    return pages[-1].page_number if pages else None


def _mark_failed(session: Session, document_id: uuid.UUID, error_message: str) -> None:
    """Reload the document after a rollback and record the failure. Old
    chunks were never touched, so they keep serving answers (§5.1)."""
    document = session.get(Document, document_id)
    if document is None:
        return
    document.status = DocumentStatus.FAILED
    document.error_message = error_message[:1000]
    session.commit()
