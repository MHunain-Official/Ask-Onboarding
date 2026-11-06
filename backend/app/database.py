"""Database engine and session setup.

Sync SQLAlchemy, on purpose: the owner must be able to read and modify this
without learning async session machinery. FastAPI runs sync dependencies in
a thread pool, so this does not block the event loop under normal load.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in `app.models`."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields one request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
