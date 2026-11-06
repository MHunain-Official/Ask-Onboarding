"""Covers §5.1's re-upload rules and the required test matrix (§9): a new
upload gets chunked, a changed re-upload atomically replaces the old chunks,
a failed re-upload keeps the previous version serving, and an identical
re-upload is a no-op.
"""

import hashlib
import io
from pathlib import Path

from sqlalchemy.orm import Session

from app.embeddings.fake_embedder import FakeEmbedder
from app.ingestion.pipeline import process_document
from app.models import AccessLevel, Document, DocumentChunk, DocumentStatus, User
from tests.integration.sse_helpers import CSRF_HEADERS

V1_TEXT = "# Welcome\n\nThe VPN password is rotated every 90 days.\n"
V2_TEXT = "# Welcome\n\nThe VPN password is rotated every 30 days now.\n"


def _make_document(db: Session, user: User, tmp_path: Path, content: str) -> Document:
    file_path = tmp_path / "doc.md"
    file_path.write_text(content)
    document = Document(
        filename="vpn-guide.md",
        content_type="text/markdown",
        storage_path=str(file_path),
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        access_level=AccessLevel.ALL,
        version=1,
        status=DocumentStatus.QUEUED,
        chunk_count=0,
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _chunks_of(db: Session, document_id: object) -> list[DocumentChunk]:
    return db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()


def test_process_document_creates_chunks(db: Session, demo_user: User, tmp_path: Path) -> None:
    document = _make_document(db, demo_user, tmp_path, V1_TEXT)

    process_document(db, document.id, FakeEmbedder())

    db.refresh(document)
    assert document.status == DocumentStatus.READY
    assert document.chunk_count > 0
    chunks = _chunks_of(db, document.id)
    assert len(chunks) == document.chunk_count
    assert all(chunk.document_version == 1 for chunk in chunks)
    assert any("90 days" in chunk.text for chunk in chunks)
    assert all(len(chunk.embedding) == 1536 for chunk in chunks)


def test_reupload_changed_content_replaces_old_chunks(
    db: Session, demo_user: User, tmp_path: Path
) -> None:
    document = _make_document(db, demo_user, tmp_path, V1_TEXT)
    process_document(db, document.id, FakeEmbedder())

    # Simulate what the upload endpoint does for a changed re-upload.
    new_path = tmp_path / "doc_v2.md"
    new_path.write_text(V2_TEXT)
    document.storage_path = str(new_path)
    document.content_hash = hashlib.sha256(V2_TEXT.encode()).hexdigest()
    document.version = 2
    document.status = DocumentStatus.QUEUED
    db.commit()

    process_document(db, document.id, FakeEmbedder())

    db.refresh(document)
    assert document.status == DocumentStatus.READY
    chunks = _chunks_of(db, document.id)
    assert all(chunk.document_version == 2 for chunk in chunks)
    all_text = " ".join(chunk.text for chunk in chunks)
    assert "30 days" in all_text
    assert "90 days" not in all_text


def test_failed_reupload_keeps_old_chunks_active(
    db: Session, demo_user: User, tmp_path: Path
) -> None:
    document = _make_document(db, demo_user, tmp_path, V1_TEXT)
    process_document(db, document.id, FakeEmbedder())
    original_chunk_ids = {chunk.id for chunk in _chunks_of(db, document.id)}

    # Point at a file that no longer exists -> processing must fail cleanly,
    # leaving the previous (good) chunks exactly as they were.
    document.storage_path = str(tmp_path / "missing.md")
    document.content_hash = "deadbeef"
    document.version = 2
    document.status = DocumentStatus.QUEUED
    db.commit()

    process_document(db, document.id, FakeEmbedder())

    db.refresh(document)
    assert document.status == DocumentStatus.FAILED
    assert document.error_message
    remaining_chunk_ids = {chunk.id for chunk in _chunks_of(db, document.id)}
    assert remaining_chunk_ids == original_chunk_ids


def test_identical_content_reupload_is_a_noop(make_client, demo_user: User) -> None:
    client = make_client(demo_user)

    first = client.post(
        "/api/documents",
        files={"file": ("notes.md", io.BytesIO(V1_TEXT.encode()), "text/markdown")},
        headers=CSRF_HEADERS,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/documents",
        files={"file": ("notes.md", io.BytesIO(V1_TEXT.encode()), "text/markdown")},
        headers=CSRF_HEADERS,
    )

    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["version"] == first.json()["version"] == 1
