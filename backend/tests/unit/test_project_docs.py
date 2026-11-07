"""Unit tests for the admin project-docs catalogue (path safety + allowlist)."""

from pathlib import Path

import pytest

from app.services.project_docs_service import (
    ProjectDocsError,
    list_project_docs,
    read_project_doc,
    resolve_docs_root,
)


def _write(root: Path, relative: str, text: str = "# hello\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_list_includes_architecture_and_rules(tmp_path: Path) -> None:
    _write(tmp_path, "AGENTS.md")
    _write(tmp_path, "ARCHITECTURE.md", "# Architecture\n")
    _write(tmp_path, "docs/adr/001-pgvector.md", "# ADR\n")
    _write(tmp_path, ".cursor/rules/security.mdc", "# Rule\n")
    _write(tmp_path, "sample-data/README.md", "# Samples\n")
    _write(tmp_path, "sample-data/docs/secret.md", "CANARY\n")
    _write(tmp_path, "backend/eval/report.md", "# Report\n")
    _write(tmp_path, "backend/eval/notes.md", "# Skip\n")

    paths = {entry.path for entry in list_project_docs(tmp_path)}
    assert "ARCHITECTURE.md" in paths
    assert "docs/adr/001-pgvector.md" in paths
    assert ".cursor/rules/security.mdc" in paths
    assert "sample-data/README.md" in paths
    assert "backend/eval/report.md" in paths
    assert "sample-data/docs/secret.md" not in paths
    assert "backend/eval/notes.md" not in paths


def test_read_returns_content(tmp_path: Path) -> None:
    _write(tmp_path, "ARCHITECTURE.md", "# Architecture\n\nPostgres + pgvector.\n")
    entry, text = read_project_doc(tmp_path, "ARCHITECTURE.md")
    assert entry.path == "ARCHITECTURE.md"
    assert "pgvector" in text


@pytest.mark.parametrize(
    "bad_path",
    [
        "../ARCHITECTURE.md",
        "/etc/passwd",
        "docs/../../etc/passwd",
        ".env",
        "backend/app/config.py",
    ],
)
def test_read_rejects_escape_and_non_allowlisted(tmp_path: Path, bad_path: str) -> None:
    _write(tmp_path, "ARCHITECTURE.md")
    _write(tmp_path, ".env", "SECRET=1\n")
    _write(tmp_path, "backend/app/config.py", "x = 1\n")
    with pytest.raises(ProjectDocsError):
        read_project_doc(tmp_path, bad_path)


def test_resolve_docs_root_uses_agents_marker(tmp_path: Path) -> None:
    _write(tmp_path, "AGENTS.md")
    nested = tmp_path / "backend" / "app" / "services"
    nested.mkdir(parents=True)
    # Walking from a fake nested path still finds AGENTS via configured root.
    assert resolve_docs_root(str(tmp_path)) == tmp_path.resolve()
