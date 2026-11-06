"""Where uploaded file bytes live on disk (§5.1, §3.2: never store or serve
a file under the user's own filename — only by a generated UUID)."""

import uuid
from pathlib import Path

CONTENT_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


def store_file(raw_bytes: bytes, extension: str, upload_dir: str) -> str:
    """Write the file under a random UUID name and return its storage path."""
    directory = Path(upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    storage_path = directory / f"{uuid.uuid4()}{extension}"
    storage_path.write_bytes(raw_bytes)
    return str(storage_path)
