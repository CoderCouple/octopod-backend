from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from typing import AsyncGenerator, Generator

from app.settings import settings

# Create base class for models
Base = declarative_base()

# Async engine and session
async_engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine and session (for migrations)
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.close()