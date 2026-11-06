"""Picks the real or fake embedder based on config (shared by the worker
and the retrieval router so there is one place that decides this).
"""

import structlog

from app.config import get_settings
from app.embeddings.base import Embedder
from app.embeddings.fake_embedder import FakeEmbedder
from app.embeddings.openai_embedder import OpenAiEmbedder

logger = structlog.get_logger(__name__)


def build_embedder() -> Embedder:
    """Real embeddings need a key; an empty key means local/test use, where
    the fake, deterministic embedder keeps the app runnable offline."""
    settings = get_settings()
    if not settings.embedding_api_key:
        logger.warning("embeddings.using_fake_embedder", reason="EMBEDDING_API_KEY is empty")
        return FakeEmbedder()
    return OpenAiEmbedder(settings)
