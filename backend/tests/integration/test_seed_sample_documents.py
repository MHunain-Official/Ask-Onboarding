"""Integration test for seeding `sample-data/docs` (AGENTS.md §8.1, §1):
every file is queued for the worker, the manager-only file is marked
correctly, and running the seed twice never creates duplicates.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import AccessLevel, Document, DocumentStatus, User
from app.seed import MANAGER_ONLY_FILENAME, seed_sample_documents

SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[3] / "sample-data" / "docs"


def test_seed_queues_every_sample_file_with_the_right_access_level(
    db: Session, admin_user: User, tmp_path: Path
) -> None:
    expected_filenames = {p.name for p in SAMPLE_DOCS_DIR.iterdir() if p.is_file()}

    seed_sample_documents(db, str(tmp_path))

    documents = db.query(Document).all()
    assert {d.filename for d in documents} == expected_filenames
    assert all(d.status == DocumentStatus.QUEUED for d in documents)
    assert all(d.uploaded_by == admin_user.id for d in documents)

    manager_only = next(d for d in documents if d.filename == MANAGER_ONLY_FILENAME)
    assert manager_only.access_level == AccessLevel.MANAGERS

    everyone_else = [d for d in documents if d.filename != MANAGER_ONLY_FILENAME]
    assert all(d.access_level == AccessLevel.ALL for d in everyone_else)

    # The bytes were really copied, not just referenced, and the content
    # hash matches the file on disk (§5.1 step 1).
    one_doc = documents[0]
    copied_bytes = Path(one_doc.storage_path).read_bytes()
    original_bytes = (SAMPLE_DOCS_DIR / one_doc.filename).read_bytes()
    assert copied_bytes == original_bytes


def test_seeding_twice_does_not_duplicate_documents(
    db: Session, admin_user: User, tmp_path: Path
) -> None:
    seed_sample_documents(db, str(tmp_path))
    first_count = db.query(Document).count()

    seed_sample_documents(db, str(tmp_path))
    second_count = db.query(Document).count()

    assert first_count == second_count


def test_seeding_without_an_admin_user_queues_nothing(db: Session, tmp_path: Path) -> None:
    seed_sample_documents(db, str(tmp_path))
    assert db.query(Document).count() == 0
