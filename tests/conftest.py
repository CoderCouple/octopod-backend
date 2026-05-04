import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.model.aggregated_individual_profile_model import AggregatedIndividualProfile  # noqa: F401
from app.model.campaign_recipient_model import CampaignRecipient  # noqa: F401
from app.model.campaign_step_model import CampaignStep  # noqa: F401
from app.model.cohesive_individual_profile_model import CohesiveIndividualProfile  # noqa: F401

# Import all models so Base.metadata knows about them
# Developer profile models
from app.model.developer_profile_model import DeveloperProfile  # noqa: F401
from app.model.email_campaign_model import EmailCampaign  # noqa: F401
from app.model.email_event_model import EmailEvent  # noqa: F401
from app.model.email_message_model import EmailMessage  # noqa: F401
from app.model.email_template_model import EmailTemplate  # noqa: F401
from app.model.email_unsubscribe_model import EmailUnsubscribe  # noqa: F401

# Email outreach models
from app.model.mailbox_model import Mailbox  # noqa: F401
from app.model.merge_audit_log_model import MergeAuditLog  # noqa: F401
from app.model.profile_ranking_model import ProfileRanking  # noqa: F401
from app.model.social_profile_model import SocialProfile  # noqa: F401

ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client(async_engine) -> AsyncGenerator[AsyncClient, None]:
    from app.db.session import get_db
    from app.main import app

    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


FAKE_COGNITO_CLAIMS = {
    "sub": "test-user-00000000-0000-0000-0000-000000000001",
    "email": "test@example.com",
    "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_FAKE",
    "aud": "fake-client-id",
    "token_use": "id",
}


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(async_engine) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with Cognito JWT validation mocked — requests appear authenticated."""
    from app.common.auth.cognito import get_current_user, get_current_user_optional
    from app.db.session import get_db
    from app.main import app

    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user():
        return FAKE_COGNITO_CLAIMS

    async def override_get_current_user_optional():
        return FAKE_COGNITO_CLAIMS

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_user_optional] = override_get_current_user_optional

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
