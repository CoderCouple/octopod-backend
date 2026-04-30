from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a request-scoped async database session.

    Creates an ``AsyncSession`` from the cached session factory, yields
    it for use by route handlers and services, and handles transaction
    lifecycle:

    * On success the session is **committed**.
    * On exception the session is **rolled back** and the exception is
      re-raised.

    Yields:
        An ``AsyncSession`` instance that is automatically committed
        or rolled back when the request completes.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
