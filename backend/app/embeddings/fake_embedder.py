"""Deterministic fake embedder for tests (AGENTS.md §3.3: AI is faked behind
interfaces so tests need no API keys and never change between runs).

Each word is hashed into one of 1536 buckets and the bucket is incremented,
then the vector is L2-normalised. Two texts that share more words end up
with a higher cosine similarity than two texts that share none — close
enough to a real embedding's behaviour for retrieval tests, without ever
calling a network.
"""

import hashlib
import math
import re

from app.config import Settings

DIMENSIONS = 1536
_WORD_PATTERN = re.compile(r"[a-z0-9]+")


class FakeEmbedder:
    """In-memory, deterministic stand-in for `OpenAiEmbedder`."""

    def __init__(self, settings: Settings | None = None) -> None:
        # Settings is accepted (not used) so call sites can construct either
        # embedder the same way, e.g. `EmbedderClass(settings)`.
        del settings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return _embed_one(text)


def _embed_one(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    words = _WORD_PATTERN.findall(text.lower())
    if not words:
        words = ["empty"]
    for word in words:
        bucket = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % DIMENSIONS
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]
