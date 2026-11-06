"""Ingestion worker entrypoint: claims and processes queued documents (§5.1).

A separate container from the API so uploads return instantly and ingestion
survives a restart (AGENTS.md §1: "upload returns instantly; survives
restarts; scales by adding workers; no Redis needed").
"""

import time
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.embeddings.base import Embedder
from app.embeddings.factory import build_embedder
from app.ingestion.pipeline import process_document
from app.models import Document, DocumentStatus

logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 5
# How long a document may sit in `processing` before we assume the worker
# that claimed it crashed and requeue it (§5.1 point 3, §5.12 #18).
STUCK_PROCESSING_MINUTES = 30


def reclaim_stuck_documents(session: Session) -> None:
    """Rows stuck in `processing` (the worker that claimed them crashed)
    are requeued once at startup so they get another attempt."""
    cutoff = datetime.now(UTC) - timedelta(minutes=STUCK_PROCESSING_MINUTES)
    stuck = (
        session.query(Document)
        .filter(Document.status == DocumentStatus.PROCESSING, Document.updated_at < cutoff)
        .all()
    )
    for document in stuck:
        document.status = DocumentStatus.QUEUED
        logger.warning("worker.reclaimed_stuck_document", document_id=str(document.id))
    if stuck:
        session.commit()


def claim_next_document(session: Session) -> uuid.UUID | None:
    """Atomically claim one queued document so multiple worker replicas
    never process the same document twice (`FOR UPDATE SKIP LOCKED`)."""
    row = session.execute(
        text(
            "SELECT id FROM documents WHERE status = 'queued' "
            "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
    ).first()
    if row is None:
        return None
    document_id = row[0]
    session.execute(
        text("UPDATE documents SET status = 'processing' WHERE id = :id"),
        {"id": document_id},
    )
    session.commit()
    return uuid.UUID(str(document_id))


def run_once(embedder: Embedder) -> bool:
    """Claim and process at most one document. Returns True if one was
    found, so the caller knows whether to poll again immediately or wait."""
    with SessionLocal() as claim_session:
        document_id = claim_next_document(claim_session)
    if document_id is None:
        return False
    with SessionLocal() as process_session:
        process_document(process_session, document_id, embedder)
    return True


def run_forever() -> None:
    embedder = build_embedder()
    with SessionLocal() as startup_session:
        reclaim_stuck_documents(startup_session)
    logger.info("worker.started")

    while True:
        try:
            found_work = run_once(embedder)
        except Exception as exc:  # noqa: BLE001 - keep the poll loop alive across any failure
            logger.error("worker.loop_error", error=str(exc))
            found_work = False
        if not found_work:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
