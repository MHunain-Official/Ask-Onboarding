"""Upload validation: extension, magic bytes, filename sanitisation (§3.2,
§5.1 step 1). The server re-checks everything the client already checked —
client-side checks are only a convenience, never trusted.
"""

from pathlib import Path

ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}
MAX_FILENAME_LENGTH = 255

_PDF_MAGIC = b"%PDF-"


class FileValidationError(Exception):
    """A file failed type, size, or filename validation. The message is
    safe to show to the user."""


def extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_extension(filename: str) -> str:
    """Return the lowercase extension, or raise if it is not an allowed type."""
    extension = extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(f"Unsupported file type '{extension}'. Allowed: {allowed}")
    return extension


def validate_magic_bytes(extension: str, raw_bytes: bytes) -> None:
    """Check the file's actual content matches its extension, not just the
    name — a spoofed `.pdf` containing an executable must be rejected
    (AGENTS.md §3.2, §5.12 #15)."""
    if extension == ".pdf":
        if not raw_bytes.startswith(_PDF_MAGIC):
            raise FileValidationError("File has a .pdf extension but is not a valid PDF")
        return

    # .md / .txt: must look like text, not arbitrary binary data wearing a
    # text extension. A null byte in the first KB is the simplest, cheapest
    # binary-content signal; genuine text files never contain one.
    if b"\x00" in raw_bytes[:1024]:
        raise FileValidationError(f"File has a {extension} extension but contains binary data")


def validate_size(raw_bytes: bytes, *, max_megabytes: int) -> None:
    max_bytes = max_megabytes * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise FileValidationError(f"File exceeds the {max_megabytes} MB upload limit")
    if len(raw_bytes) == 0:
        raise FileValidationError("File is empty")


def sanitize_display_filename(filename: str) -> str:
    """Strip any directory components so a crafted name like
    `../../etc/passwd` or `..\\..\\config` cannot escape the uploads
    directory. The returned name is only ever used for display and for the
    case-insensitive re-upload identity check — the file itself is always
    stored on disk under a UUID, never under this name."""
    normalized = filename.replace("\\", "/")
    name = Path(normalized).name.strip()
    if not name or name in {".", ".."}:
        raise FileValidationError("Invalid filename")
    if len(name) > MAX_FILENAME_LENGTH:
        raise FileValidationError(f"Filename exceeds {MAX_FILENAME_LENGTH} characters")
    return name
