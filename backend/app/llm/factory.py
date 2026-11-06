"""Picks the real or fake LLM client based on config, and holds the
process-wide circuit breaker (AGENTS.md §5.9: one breaker per process, so
"N consecutive failures" counts across every request, not per-request).

`get_llm_client` is also a FastAPI dependency (`Depends(get_llm_client)` in
`app/routers/chat.py`) so tests can override it with a scripted `FakeLlm`
the same way `tests/integration/conftest.py` overrides `get_db`.
"""

from functools import lru_cache

import structlog

from app.config import get_settings
from app.llm.base import LlmClient
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.fake_llm import FakeLlm
from app.llm.openai_compatible_client import OpenAiCompatibleClient

logger = structlog.get_logger(__name__)


def get_llm_client() -> LlmClient:
    """Real generation needs a key; an empty key means local/test use,
    where the fake, deterministic client keeps the app runnable offline."""
    settings = get_settings()
    if not settings.llm_api_key:
        logger.warning("llm.using_fake_client", reason="LLM_API_KEY is empty")
        return FakeLlm()
    return OpenAiCompatibleClient(settings)


@lru_cache
def get_circuit_breaker() -> CircuitBreaker:
    settings = get_settings()
    return CircuitBreaker(
        failure_threshold=settings.circuit_breaker_failures,
        cooldown_seconds=settings.circuit_breaker_cooldown_seconds,
    )
