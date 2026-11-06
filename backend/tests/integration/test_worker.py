"""Worker claim/reclaim logic (§5.1 point 3, §5.12 #18): a queued document
can be claimed exactly once, and a document stuck in `processing` for too
long is requeued at startup instead of being lost forever.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.worker import claim_next_document, reclaim_stuck_documents
from app.models import AccessLevel, Document, DocumentStatus, User


def _make_document(db: Session, user: User, status: DocumentStatus) -> Document:
    document = Document(
        filename="doc.md",
        content_type="text/markdown",
        storage_path="/tmp/doc.md",
        content_hash="hash",
        access_level=AccessLevel.ALL,
        version=1,
        status=status,
        chunk_count=0,
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_claim_next_document_sets_processing_and_returns_id(db: Session, demo_user: User) -> None:
    document = _make_document(db, demo_user, DocumentStatus.QUEUED)

    claimed_id = claim_next_document(db)

    assert claimed_id == document.id
    db.refresh(document)
    assert document.status == DocumentStatus.PROCESSING


def test_claim_next_document_returns_none_when_nothing_queued(db: Session, demo_user: User) -> None:
    _make_document(db, demo_user, DocumentStatus.READY)

    assert claim_next_document(db) is None


def test_reclaim_stuck_documents_requeues_old_processing_rows(db: Session, demo_user: User) -> None:
    document = _make_document(db, demo_user, DocumentStatus.PROCESSING)
    stale_time = datetime.now(UTC) - timedelta(hours=1)
    db.execute(
        text("UPDATE documents SET updated_at = :stale WHERE id = :id"),
        {"stale": stale_time, "id": document.id},
    )
    db.commit()

    reclaim_stuck_documents(db)

    db.refresh(document)
    assert document.status == DocumentStatus.QUEUED


def test_reclaim_stuck_documents_leaves_recent_processing_rows_alone(
    db: Session, demo_user: User
) -> None:
    document = _make_document(db, demo_user, DocumentStatus.PROCESSING)

    reclaim_stuck_documents(db)

    db.refresh(document)
    assert document.status == DocumentStatus.PROCESSING
