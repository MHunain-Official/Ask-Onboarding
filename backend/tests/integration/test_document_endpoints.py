"""Covers the remaining document/chunk endpoints from §6: listing is
ACL-filtered, delete removes the row and its file, content returns the
exact parsed text with highlight offsets, and a chunk a user may not read
404s instead of 403ing (§5.7)."""

import io
import uuid

from app.embeddings.fake_embedder import FakeEmbedder
from app.ingestion.pipeline import process_document
from app.models import DocumentChunk, User, UserRole
from tests.integration.sse_helpers import CSRF_HEADERS

MARKDOWN = "# Welcome\n\nThe wifi password is `hunter2`.\n"


def test_employee_does_not_see_managers_only_document_in_list(
    make_client, db, demo_user: User
) -> None:
    manager = User(email="mgr@demo.local", name="Mgr", role=UserRole.MANAGER)
    db.add(manager)
    db.commit()
    db.refresh(manager)

    manager_client = make_client(manager)
    manager_client.post(
        "/api/documents",
        files={"file": ("salary.md", io.BytesIO(b"# Salary bands"), "text/markdown")},
        data={"access_level": "managers"},
        headers=CSRF_HEADERS,
    )

    employee_client = make_client(demo_user)
    response = employee_client.get("/api/documents")

    assert response.status_code == 200
    filenames = [item["filename"] for item in response.json()["items"]]
    assert "salary.md" not in filenames


def test_manager_sees_managers_only_document_in_list(make_client, demo_user: User) -> None:
    demo_user.role = UserRole.MANAGER
    client = make_client(demo_user)
    client.post(
        "/api/documents",
        files={"file": ("salary.md", io.BytesIO(b"# Salary bands"), "text/markdown")},
        data={"access_level": "managers"},
        headers=CSRF_HEADERS,
    )

    response = client.get("/api/documents")

    filenames = [item["filename"] for item in response.json()["items"]]
    assert "salary.md" in filenames


def test_delete_document_removes_it_from_the_list(make_client, manager_user: User) -> None:
    client = make_client(manager_user)
    upload = client.post(
        "/api/documents",
        files={"file": ("notes.md", io.BytesIO(b"# Notes"), "text/markdown")},
        headers=CSRF_HEADERS,
    )
    document_id = upload.json()["id"]

    delete_response = client.delete(f"/api/documents/{document_id}", headers=CSRF_HEADERS)

    assert delete_response.status_code == 204
    listing = client.get("/api/documents").json()
    assert all(item["id"] != document_id for item in listing["items"])


def test_get_document_content_returns_highlighted_passage(make_client, db, manager_user: User) -> None:
    client = make_client(manager_user)
    upload = client.post(
        "/api/documents",
        files={"file": ("wifi.md", io.BytesIO(MARKDOWN.encode()), "text/markdown")},
        headers=CSRF_HEADERS,
    )
    document_id = upload.json()["id"]
    process_document(db, document_id, FakeEmbedder())
    chunk = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).first()

    response = client.get(f"/api/documents/{document_id}/content?highlight_chunk={chunk.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == MARKDOWN
    highlighted = body["text"][body["highlight_char_start"] : body["highlight_char_end"]]
    if chunk.heading:
        expected_body_text = chunk.text.removeprefix(f"{chunk.heading}\n\n")
    else:
        expected_body_text = chunk.text
    assert highlighted == expected_body_text


def test_get_chunk_for_other_users_scope_returns_404_not_403(
    make_client, db, demo_user: User
) -> None:
    manager = User(email="mgr2@demo.local", name="Mgr2", role=UserRole.MANAGER)
    db.add(manager)
    db.commit()
    db.refresh(manager)

    manager_client = make_client(manager)
    content = b"# Salary bands\n\nEngineering L4 is 120k to 150k per year.\n"
    upload = manager_client.post(
        "/api/documents",
        files={"file": ("salary2.md", io.BytesIO(content), "text/markdown")},
        data={"access_level": "managers"},
        headers=CSRF_HEADERS,
    )
    process_document(db, upload.json()["id"], FakeEmbedder())
    chunk = db.query(DocumentChunk).filter(DocumentChunk.document_id == upload.json()["id"]).first()
    assert chunk is not None

    employee_client = make_client(demo_user)
    response = employee_client.get(f"/api/chunks/{chunk.id}")

    assert response.status_code == 404


def test_get_unknown_chunk_is_404(make_client, demo_user: User) -> None:
    client = make_client(demo_user)

    response = client.get(f"/api/chunks/{uuid.uuid4()}")

    assert response.status_code == 404
