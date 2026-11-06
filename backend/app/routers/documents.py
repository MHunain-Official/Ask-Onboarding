"""Document upload, listing, deletion, and content/chunk retrieval (§5.1, §6).

Access control is enforced in the same query that reads the row — never
after the fact — the one rule AGENTS.md repeats most (§5.7, §3.2).
"""

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.ingestion.file_validation import (
    FileValidationError,
    sanitize_display_filename,
    validate_extension,
    validate_magic_bytes,
    validate_size,
)
from app.ingestion.parsers import parse_by_filename
from app.ingestion.storage import CONTENT_TYPES, store_file
from app.models import AccessLevel, Document, DocumentChunk, DocumentStatus, User, UserRole
from app.schemas import ChunkPublic, DocumentContentResponse, DocumentListResponse, DocumentPublic
from app.security import allowed_access_levels, require_csrf_header, require_user
from app.security_hardening import require_upload_rate_limit
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api", tags=["documents"])


@router.post(
    "/documents",
    response_model=DocumentPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header), Depends(require_upload_rate_limit)],
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    access_level: AccessLevel = Form(default=AccessLevel.ALL),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> Document:
    """Upload or re-upload a document. Identity is the filename, compared
    case-insensitively: identical content is a no-op, changed content bumps
    the version and requeues it — the old chunks keep answering questions
    until the worker's atomic swap replaces them (§5.1)."""
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")
    if access_level == AccessLevel.MANAGERS and user.role == UserRole.EMPLOYEE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only managers or admins may mark a document manager-only"
        )

    raw_bytes = await file.read()
    settings = get_settings()
    try:
        extension = validate_extension(file.filename)
        validate_size(raw_bytes, max_megabytes=settings.max_upload_mb)
        validate_magic_bytes(extension, raw_bytes)
        display_filename = sanitize_display_filename(file.filename)
    except FileValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    existing = (
        db.query(Document).filter(func.lower(Document.filename) == display_filename.lower()).first()
    )
    # Symmetric with the check above: an employee may not create a
    # manager-only document, so an employee must not be able to overwrite
    # or downgrade one either by re-uploading over the same filename —
    # otherwise the `access_level == MANAGERS` guard above would be
    # trivially bypassed (AGENTS.md §5.7: this check is in the only place
    # that writes `documents.access_level`, never re-derived elsewhere).
    existing_is_managers_only = (
        existing is not None and existing.access_level == AccessLevel.MANAGERS
    )
    if existing_is_managers_only and user.role == UserRole.EMPLOYEE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only managers or admins may replace a manager-only document",
        )
    if existing is not None and existing.content_hash == content_hash:
        return existing  # identical re-upload: no-op (§5.1)

    storage_path = store_file(raw_bytes, extension, settings.upload_dir)
    is_reupload = existing is not None
    document = _upsert_document(
        existing, display_filename, extension, storage_path, content_hash, access_level, user
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    record_audit_event(
        db,
        event_type="reupload" if is_reupload else "upload",
        request_id=getattr(request.state, "request_id", None),
        user_id=user.id,
        details={
            "document_id": str(document.id),
            "filename": document.filename,
            "version": document.version,
            "access_level": document.access_level.value,
        },
    )
    return document


def _upsert_document(
    existing: Document | None,
    filename: str,
    extension: str,
    storage_path: str,
    content_hash: str,
    access_level: AccessLevel,
    user: User,
) -> Document:
    if existing is None:
        return Document(
            filename=filename,
            content_type=CONTENT_TYPES[extension],
            storage_path=storage_path,
            content_hash=content_hash,
            access_level=access_level,
            version=1,
            status=DocumentStatus.QUEUED,
            chunk_count=0,
            uploaded_by=user.id,
        )

    existing.filename = filename
    existing.storage_path = storage_path
    existing.content_hash = content_hash
    existing.access_level = access_level
    existing.version += 1
    existing.status = DocumentStatus.QUEUED
    existing.error_message = None
    existing.uploaded_by = user.id
    return existing


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    user: User = Depends(require_user), db: Session = Depends(get_db)
) -> DocumentListResponse:
    """Employees never even see `managers`-only documents in this list."""
    levels = allowed_access_levels(user)
    documents = (
        db.query(Document)
        .filter(Document.access_level.in_(levels))
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentListResponse(items=[DocumentPublic.model_validate(d) for d in documents])


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    document = _get_visible_document(db, document_id, user)
    filename = document.filename
    Path(document.storage_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
    record_audit_event(
        db,
        event_type="delete",
        request_id=getattr(request.state, "request_id", None),
        user_id=user.id,
        details={"document_id": str(document_id), "filename": filename},
    )


@router.get("/documents/{document_id}/content", response_model=DocumentContentResponse)
def get_document_content(
    document_id: uuid.UUID,
    highlight_chunk: uuid.UUID | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> DocumentContentResponse:
    document = _get_visible_document(db, document_id, user)
    settings = get_settings()
    raw_bytes = Path(document.storage_path).read_bytes()
    parsed = parse_by_filename(document.filename, raw_bytes, max_pages=settings.max_pdf_pages)

    char_start = char_end = page = None
    if highlight_chunk is not None:
        chunk = db.get(DocumentChunk, highlight_chunk)
        if chunk is None or chunk.document_id != document.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
        char_start, char_end, page = chunk.char_start, chunk.char_end, chunk.page_number

    return DocumentContentResponse(
        filename=document.filename,
        content_type=document.content_type,
        text=parsed.text,
        highlight_char_start=char_start,
        highlight_char_end=char_end,
        highlight_page=page,
    )


@router.get("/chunks/{chunk_id}", response_model=ChunkPublic)
def get_chunk(
    chunk_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> ChunkPublic:
    """A guessed `chunk_id` the user may not read must 404, not 403, so a
    probe cannot even learn the chunk exists (AGENTS.md §5.7)."""
    chunk = db.get(DocumentChunk, chunk_id)
    if chunk is None or chunk.access_level not in allowed_access_levels(user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    document = db.get(Document, chunk.document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    return ChunkPublic(
        id=chunk.id,
        document_id=chunk.document_id,
        filename=document.filename,
        heading=chunk.heading,
        page_number=chunk.page_number,
        text=chunk.text,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
    )


def _get_visible_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.access_level not in allowed_access_levels(user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document
