"""Covers §3.2/§5.1 upload validation: wrong file type, a spoofed extension,
an oversize file, and a path-traversal filename are all rejected
server-side — the frontend's checks are only a convenience, never trusted.
"""

import io

from app.models import User
from tests.integration.sse_helpers import CSRF_HEADERS


def test_wrong_extension_is_rejected(make_client, manager_user: User) -> None:
    client = make_client(manager_user)

    response = client.post(
        "/api/documents",
        files={"file": ("virus.exe", io.BytesIO(b"not a document"), "application/octet-stream")},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 400


def test_spoofed_pdf_extension_is_rejected(make_client, manager_user: User) -> None:
    client = make_client(manager_user)

    response = client.post(
        "/api/documents",
        files={"file": ("report.pdf", io.BytesIO(b"this is not a real pdf"), "application/pdf")},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


def test_oversize_file_is_rejected(make_client, manager_user: User) -> None:
    client = make_client(manager_user)
    oversize_bytes = b"x" * (11 * 1024 * 1024)  # over the 10 MB default limit

    response = client.post(
        "/api/documents",
        files={"file": ("huge.txt", io.BytesIO(oversize_bytes), "text/plain")},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 400


def test_empty_file_is_rejected(make_client, manager_user: User) -> None:
    client = make_client(manager_user)

    response = client.post(
        "/api/documents",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 400


def test_path_traversal_filename_is_sanitised(make_client, manager_user: User) -> None:
    client = make_client(manager_user)

    response = client.post(
        "/api/documents",
        files={"file": ("../../etc/passwd.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 201
    # Directories are stripped; the file is never written to that path.
    assert response.json()["filename"] == "passwd.txt"


def test_employee_cannot_mark_document_managers_only(make_client, demo_user: User) -> None:
    client = make_client(demo_user)

    response = client.post(
        "/api/documents",
        files={"file": ("salary.md", io.BytesIO(b"# Salary bands"), "text/markdown")},
        data={"access_level": "managers"},
        headers=CSRF_HEADERS,
    )

    assert response.status_code == 403


def test_upload_without_csrf_header_is_rejected(make_client, demo_user: User) -> None:
    client = make_client(demo_user)

    response = client.post(
        "/api/documents",
        files={"file": ("notes.md", io.BytesIO(b"# Notes"), "text/markdown")},
    )

    assert response.status_code == 403


def test_employee_cannot_upload_documents(make_client, demo_user: User) -> None:
    client = make_client(demo_user)
    response = client.post(
        "/api/documents",
        files={"file": ("ok.md", b"# hello\n", "text/markdown")},
        data={"access_level": "all"},
        headers={"X-Requested-With": "ask-onboarding"},
    )
    assert response.status_code == 403
