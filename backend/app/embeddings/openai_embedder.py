"""OpenAI embeddings, called directly (never through a gateway — AGENTS.md
§1: changing the embedding model forces a full re-embed, so this one call
path stays simple and stable).
"""

import time

import structlog
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from app.config import Settings

logger = structlog.get_logger(__name__)

# OpenAI's embeddings endpoint accepts many inputs per call; batching keeps
# well under its request-size limits while still being efficient.
MAX_BATCH_SIZE = 64
MAX_RETRIES = 3
RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, APIStatusError)


class OpenAiEmbedder:
    """Embedder backed by the real OpenAI API (`EMBEDDING_*` settings)."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_model
        self._client = OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[start : start + MAX_BATCH_SIZE]
            vectors.extend(self._embed_batch_with_retry(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch_with_retry([text])[0]

    def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.embeddings.create(model=self._model, input=batch)
                return [item.embedding for item in response.data]
            except RETRYABLE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "embedding.retry",
                    attempt=attempt,
                    max_retries=MAX_RETRIES,
                    error=str(exc),
                )
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)  # 2s, 4s backoff
        assert last_error is not None  # loop always sets this before exhausting retries
        raise last_error
