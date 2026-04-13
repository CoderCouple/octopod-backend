from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings


@lru_cache(maxsize=1)
def get_async_engine():
    """Create and cache a singleton async SQLAlchemy engine.

    The engine connects to the PostgreSQL database specified by
    ``settings.async_database_url`` using the asyncpg driver.
    SQL echo is enabled when ``settings.debug`` is ``True``.

    Returns:
        An ``AsyncEngine`` instance (cached; only one is created per
        process).
    """
    return create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        future=True,
    )


@lru_cache(maxsize=1)
def get_async_session_factory():
    """Create and cache a singleton async session factory.

    The factory is bound to the async engine and configured with:

    * ``expire_on_commit=False`` -- prevent lazy-load errors after
      commit.
    * ``autocommit=False`` / ``autoflush=False`` -- explicit
      transaction control.

    Returns:
        An ``async_sessionmaker`` instance (cached; only one is created
        per process).
    """
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def get_sync_engine():
    """Lazily create a synchronous SQLAlchemy engine for Alembic migrations.

    This engine uses the synchronous database URL and is only imported
    when needed (to avoid importing synchronous SQLAlchemy drivers at
    application startup).

    Returns:
        A synchronous ``Engine`` instance.
    """
    from sqlalchemy import create_engine

    return create_engine(settings.sync_database_url, echo=settings.debug)
