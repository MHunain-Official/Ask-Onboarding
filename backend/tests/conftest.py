"""Shared pytest fixtures.

Phase 0-1 tests need no database and no API keys: they exercise plain
Python objects (Settings, ORM instances) directly. Fixtures that need a
real Postgres (FakeEmbedder/FakeLlm-backed integration tests) are added in
later phases alongside the code they test.
"""

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    """A Settings instance built from defaults, ignoring any local .env file."""
    return Settings(_env_file=None)  # type: ignore[call-arg]
