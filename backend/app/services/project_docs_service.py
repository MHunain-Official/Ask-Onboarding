"""Serve allowlisted project markdown for the admin Docs tab.

Reviewers can read ARCHITECTURE, ADRs, walkthrough notes, and agent rules
inside the app instead of opening GitHub. Paths are allowlisted and
resolved under `PROJECT_DOCS_ROOT` so `../` cannot escape the tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Extensions the browser may open. Never .env, .py, keys, etc.
_ALLOWED_SUFFIXES = {".md", ".mdc"}

# Hard cap so a huge accidental file cannot blow up the response.
_MAX_BYTES = 1_500_000

# Curated groups: fixed root files first, then directory scans.
# Sample company docs under sample-data/docs are the RAG corpus, not
# project documentation — they stay out of this catalogue on purpose.
_ROOT_FILES: tuple[tuple[str, str], ...] = (
    ("Overview", "README.md"),
    ("Overview", "ARCHITECTURE.md"),
    ("Overview", "AI_LOG.md"),
    ("Overview", "SECURITY.md"),
    ("Build & process", "AGENTS.md"),
    ("Build & process", "Build_PlayBook.md"),
    ("Build & process", "CONTRIBUTING.md"),
    ("Build & process", "CHANGELOG.md"),
    ("Build & process", "LICENSE"),
)

_SCAN_DIRS: tuple[tuple[str, str], ...] = (
    ("Deep dive", "docs"),
    ("Agent rules", ".cursor/rules"),
    ("Eval", "backend/eval"),
    ("Sample data", "sample-data"),
)


@dataclass(frozen=True)
class ProjectDocEntry:
    path: str
    title: str
    group: str


class ProjectDocsError(Exception):
    """Raised when a path is missing or not allowlisted."""


def resolve_docs_root(configured: str | None) -> Path:
    """Prefer env; otherwise walk up until AGENTS.md (the repo root)."""
    if configured:
        return Path(configured).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    # Fallback: backend/ is parents[2] from this file (services → app → backend).
    return here.parents[2].parent


def list_project_docs(root: Path) -> list[ProjectDocEntry]:
    """Return the catalogue of files that exist on disk under `root`."""
    entries: list[ProjectDocEntry] = []
    seen: set[str] = set()

    for group, relative in _ROOT_FILES:
        path = root / relative
        if not path.is_file():
            continue
        key = relative.replace("\\", "/")
        if key in seen:
            continue
        seen.add(key)
        entries.append(ProjectDocEntry(path=key, title=_title_for(key), group=group))

    for group, directory in _SCAN_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            # sample-data: only the catalogue README, not every company doc.
            if directory == "sample-data" and path.name != "README.md":
                continue
            # backend/eval: only the human report, not questions.json adjacent noise.
            if directory == "backend/eval" and path.name != "report.md":
                continue
            try:
                key = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if key in seen:
                continue
            seen.add(key)
            entries.append(ProjectDocEntry(path=key, title=_title_for(key), group=group))

    return entries


def read_project_doc(root: Path, relative_path: str) -> tuple[ProjectDocEntry, str]:
    """Load one allowlisted file. Raises ProjectDocsError on bad paths."""
    normalised = _normalise_relative(relative_path)
    allowed = {entry.path: entry for entry in list_project_docs(root)}
    entry = allowed.get(normalised)
    if entry is None:
        raise ProjectDocsError("Document not found")

    full = (root / normalised).resolve()
    if not _is_under(full, root.resolve()):
        raise ProjectDocsError("Document not found")
    if not full.is_file():
        raise ProjectDocsError("Document not found")
    if full.stat().st_size > _MAX_BYTES:
        raise ProjectDocsError("Document is too large to preview")

    text = full.read_text(encoding="utf-8", errors="replace")
    return entry, text


def _title_for(relative_path: str) -> str:
    name = Path(relative_path).name
    if name.lower() == "readme.md":
        parent = Path(relative_path).parent.as_posix()
        return "README" if parent in {"", "."} else f"{parent}/README"
    stem = Path(name).stem
    return stem.replace("-", " ").replace("_", " ")


def _normalise_relative(relative_path: str) -> str:
    cleaned = relative_path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned.startswith("/") or ".." in cleaned.split("/"):
        raise ProjectDocsError("Document not found")
    if cleaned == "":
        raise ProjectDocsError("Document not found")
    return cleaned


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
