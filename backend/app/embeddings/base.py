"""Embedder interface (AGENTS.md §1: embeddings live behind one interface).

Everything downstream (the ingestion pipeline, retrieval, the answer cache)
depends on this `Embedder` protocol, never on a concrete provider. Swapping
`OpenAiEmbedder` for `FakeEmbedder` in tests needs no mocking library.
"""

from typing import Protocol


class Embedder(Protocol):
    """Turns text into vectors. Implementations must be deterministic for
    the same input text within a single embedding model/version."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed many documents/chunks at once (batched for efficiency)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query."""
        ...
