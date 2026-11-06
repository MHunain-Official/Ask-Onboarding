"""Fixtures for integration tests that need a real Postgres with pgvector
(AGENTS.md §9: ingestion/re-upload behaviour is tested against a real
database, with `FakeEmbedder` standing in for the network call).

If no test database is reachable, every integration test module is skipped
instead of failing noisily — these tests are opt-in via `TEST_DATABASE_URL`.
"""

import os
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db
from app.llm.base import LlmClient
from app.llm.factory import get_circuit_breaker, get_llm_client
from app.main import app
from app.models import User, UserRole
from app.security import require_user
from app.security_hardening import get_rate_limiter

# Host port 55432 matches docker-compose.yml (and the local ask-pg container).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://app:app@localhost:55432/askonboarding",
)


def _try_connect() -> Engine | None:
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


_engine = _try_connect()
if _engine is None:
    pytest.skip(
        f"No reachable test database at {TEST_DATABASE_URL}. Start one and run migrations "
        "(see AGENTS.md: `docker run ... pgvector/pgvector:pg16` then `alembic upgrade head`), "
        "or point TEST_DATABASE_URL at an already-migrated database.",
        allow_module_level=True,
    )

_SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """A session against the real test database, reset before each test so
    tests never depend on each other's leftover rows."""
    session = _SessionLocal()
    session.execute(
        text(
            "TRUNCATE document_chunks, documents, users, answer_cache, "
            "query_embedding_cache, conversations, messages, tickets, "
            "llm_calls, audit_events, usage_daily, feedback "
            "RESTART IDENTITY CASCADE"
        )
    )
    session.commit()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _reset_circuit_breaker() -> Generator[None, None, None]:
    """The breaker is a process-wide singleton (AGENTS.md §5.9); one test
    opening it must never leak into the next test's assertions."""
    get_circuit_breaker.cache_clear()
    yield
    get_circuit_breaker.cache_clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Generator[None, None, None]:
    """The in-memory rate limiter (§3.2/§7) is also a process-wide
    singleton; one test tripping it must never throttle the next test."""
    get_rate_limiter().reset()
    yield
    get_rate_limiter().reset()


@pytest.fixture
def demo_user(db: Session) -> User:
    user = User(email="uploader@demo.local", name="Uploader", role=UserRole.EMPLOYEE)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def manager_user(db: Session) -> User:
    user = User(email="manager@demo.local", name="Manager", role=UserRole.MANAGER)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db: Session) -> User:
    user = User(email="admin@demo.local", name="Admin", role=UserRole.ADMIN)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def make_client(
    db: Session,
) -> Generator[Callable[..., TestClient], None, None]:
    """Factory for a `TestClient` whose `get_db`/`require_user` dependencies
    are swapped for the test session and a chosen user — no real cookie or
    database connection needed. Pass `llm_client=` to also swap in a
    scripted `FakeLlm` for chat-endpoint tests."""

    def _make(user: User, llm_client: LlmClient | None = None) -> TestClient:
        def _db_override() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[require_user] = lambda: user
        if llm_client is not None:
            app.dependency_overrides[get_llm_client] = lambda: llm_client
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
