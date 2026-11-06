"""Settings must load with sane defaults and pick up env var overrides."""

import pytest

from app.config import Settings, get_settings


def test_settings_load_with_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_env == "development"
    assert settings.embedding_dimensions == 1536
    assert settings.retrieval_top_k == 5
    assert settings.hybrid_enabled is True


def test_settings_read_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIN_SIMILARITY", "0.42")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "7")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.min_similarity == pytest.approx(0.42)
    assert settings.retrieval_top_k == 7


def test_get_settings_is_cached() -> None:
    # lru_cache means both calls return the exact same object, not just an
    # equal one — important because other modules import this singleton.
    assert get_settings() is get_settings()
