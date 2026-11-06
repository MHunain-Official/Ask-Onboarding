"""Idempotent demo seed, run on container start when SEED_ON_START=true:
demo users, plus the `sample-data/docs` documents queued for the worker.

Idempotent: running this twice never creates duplicate users (looked up by
email) or duplicate documents (looked up by filename) before inserting.
"""

import hashlib
import uuid
from pathlib import Path

import structlog
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.ingestion.file_validation import extension_of
from app.ingestion.storage import CONTENT_TYPES, store_file
from app.models import AccessLevel, Document, DocumentStatus, User, UserRole

logger = structlog.get_logger(__name__)

DEMO_USERS = [
    {"email": "employee@demo.local", "name": "Demo Employee", "role": UserRole.EMPLOYEE},
    {"email": "manager@demo.local", "name": "Demo Manager", "role": UserRole.MANAGER},
    {"email": "admin@demo.local", "name": "Demo Admin", "role": UserRole.ADMIN},
]

# The one file in sample-data/docs that must be manager-only (see
# sample-data/README.md "seed rule"); every other file seeds as `all`.
MANAGER_ONLY_FILENAME = "salary-bands-managers.md"


def seed_demo_users() -> None:
    db = SessionLocal()
    try:
        for user_data in DEMO_USERS:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing is not None:
                continue
            db.add(User(**user_data))
            logger.info("seed.user_created", email=user_data["email"])
        db.commit()
    finally:
        db.close()


def seed_sample_documents(db: Session, upload_dir: str) -> None:
    """Copy every file in `sample-data/docs` into a `queued` `Document` row
    so the worker ingests them through the exact same pipeline as a real
    upload (AGENTS.md §1: no shortcuts, no pre-filled chunks). Skips a file
    whose filename is already seeded, so re-running this is a no-op.

    Takes an open `Session` (rather than opening its own, like
    `seed_demo_users` does) so tests can pass the test database's session
    directly — the same pattern `app/ingestion/worker.py` uses for
    `claim_next_document`/`reclaim_stuck_documents`."""
    docs_dir = _find_sample_docs_dir()
    if docs_dir is None:
        logger.warning("seed.sample_docs_dir_not_found")
        return

    uploader = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if uploader is None:
        logger.warning("seed.no_admin_user_for_sample_documents")
        return
    # Captured once as a plain value: re-reading `uploader.id` after each
    # `db.commit()` below would re-select the row every time (SQLAlchemy
    # expires attributes on commit by default).
    uploader_id = uploader.id
    for file_path in sorted(p for p in docs_dir.iterdir() if p.is_file()):
        try:
            _seed_one_document(db, file_path, upload_dir, uploader_id)
        except SQLAlchemyError as exc:
            # One bad file (or a vanished `uploader_id` row) must not abort
            # every file after it — roll back just this insert and move on.
            db.rollback()
            logger.warning("seed.document_failed", filename=file_path.name, error=str(exc))


def _find_sample_docs_dir() -> Path | None:
    """Two layouts to support: a local checkout (this file lives at
    `backend/app/seed.py`, so `sample-data/docs` is three levels up) and
    the Docker image (`sample-data` mounted read-only at `/app/sample-data`,
    see `docker-compose.yml`)."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "sample-data" / "docs",
        Path("/app/sample-data/docs"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _seed_one_document(
    db: Session, file_path: Path, upload_dir: str, uploaded_by: uuid.UUID
) -> None:
    filename = file_path.name
    already_seeded = (
        db.query(Document).filter(func.lower(Document.filename) == filename.lower()).first()
    )
    if already_seeded is not None:
        return

    extension = extension_of(filename)
    if extension not in CONTENT_TYPES:
        return  # not a supported type; defensive, should not happen in sample-data

    raw_bytes = file_path.read_bytes()
    storage_path = store_file(raw_bytes, extension, upload_dir)
    access_level = AccessLevel.MANAGERS if filename == MANAGER_ONLY_FILENAME else AccessLevel.ALL
    db.add(
        Document(
            filename=filename,
            content_type=CONTENT_TYPES[extension],
            storage_path=storage_path,
            content_hash=hashlib.sha256(raw_bytes).hexdigest(),
            access_level=access_level,
            version=1,
            status=DocumentStatus.QUEUED,
            chunk_count=0,
            uploaded_by=uploaded_by,
        )
    )
    db.commit()
    logger.info("seed.document_queued", filename=filename, access_level=access_level.value)


if __name__ == "__main__":
    # Unconditional: whoever runs this module (make seed, or the backend
    # container's start command) has already decided seeding should happen.
    # The SEED_ON_START flag is checked by the caller, not here.
    seed_demo_users()
    _db = SessionLocal()
    try:
        seed_sample_documents(_db, get_settings().upload_dir)
    finally:
        _db.close()
    logger.info("seed.done")
