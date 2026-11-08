"""Application settings, loaded once from environment variables.

Why one place: the AGENTS.md playbook forbids scattering `os.environ` calls
through the codebase. Every setting the app needs lives here, typed, with a
sane default only where the default is safe for local development.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed environment configuration.

    Field names are lowercase versions of the env vars in `.env.example`.
    Pydantic-settings matches env vars case-insensitively by default.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    secret_key: str = "change-me-long-random"
    database_url: str = "postgresql+psycopg://app:app@db:5432/askonboarding"

    # --- LLM (OpenRouter, OpenAI-compatible) ---
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"
    llm_fallback_model: str = "openai/gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_max_output_tokens: int = 800
    llm_price_input_per_mtok: float = 0.15
    llm_price_output_per_mtok: float = 0.60

    # --- Embeddings (OpenAI direct, never via a gateway) ---
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Chunking / retrieval ---
    chunk_target_tokens: int = 500
    chunk_overlap_tokens: int = 80
    retrieval_top_k: int = 5
    retrieval_candidates: int = 20
    hybrid_enabled: bool = True
    min_similarity: float = 0.30
    max_upload_mb: int = 10
    # Where uploaded files live, stored by UUID (never by user filename —
    # AGENTS.md §3.2). The compose volume mounts this path in both
    # containers so the API and the worker see the same files.
    upload_dir: str = "uploads"

    # --- Rate limiting and audit ---
    rate_limit_chat_per_minute: int = 10
    rate_limit_upload_per_minute: int = 20
    audit_retention_days: int = 90
    seed_on_start: bool = True

    # --- Efficiency: cache and budgets ---
    cache_enabled: bool = True
    cache_ttl_hours: int = 72
    semantic_cache_enabled: bool = False
    semantic_cache_threshold: float = 0.97
    extractive_shortcut_enabled: bool = False
    max_context_tokens: int = 3000
    max_question_chars: int = 1000
    max_pdf_pages: int = 300
    daily_token_cap_per_user: int = 100_000
    daily_cost_cap_usd: float = 10.0
    circuit_breaker_failures: int = 5
    circuit_breaker_cooldown_seconds: int = 30

    # --- Prompt versioning (cache keys include this; §5.10 rule 4) ---
    prompt_version: str = "v1.1"

    # Repo root that holds README/ARCHITECTURE/docs for the admin Docs tab.
    # Empty → auto-detect by walking up for AGENTS.md. In Docker set to
    # /app/repo and mount the monorepo there (read-only).
    project_docs_root: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance.

    Cached so env parsing happens once; tests can bypass this by
    constructing `Settings(...)` directly with overrides.
    """
    return Settings()
