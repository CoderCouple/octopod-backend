"""One-time backfill: create Stripe customers for existing organizations.

Usage:
    poetry run python scripts/backfill_stripe_customers.py [--dry-run]

Creates a Stripe customer and local Subscription record for every
Organization that doesn't already have one.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill(dry_run: bool = False) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.model.organization_model import Organization
    from app.model.subscription_model import Subscription
    from app.service.billing_service import BillingService
    from app.settings import settings

    engine = create_async_engine(settings.async_database_url)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        # Find orgs without a subscription
        result = await session.execute(
            select(Organization).where(
                Organization.is_deleted == False,  # noqa: E712
                ~Organization.id.in_(select(Subscription.org_id)),
            )
        )
        orgs = list(result.scalars().all())
        logger.info("Found %d organizations without Stripe customers", len(orgs))

        if dry_run:
            for org in orgs:
                logger.info("[DRY RUN] Would create customer for org=%s name=%s", org.id, org.name)
            return

        service = BillingService(session)
        created = 0
        for org in orgs:
            try:
                await service.ensure_stripe_customer(org.id, org.name)
                created += 1
                logger.info("Created Stripe customer for org=%s name=%s", org.id, org.name)
            except Exception:
                logger.exception("Failed to create Stripe customer for org=%s", org.id)

        await session.commit()
        logger.info("Backfill complete: %d/%d customers created", created, len(orgs))

    await engine.dispose()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        logger.info("Running in DRY RUN mode — no Stripe calls will be made")
    asyncio.run(backfill(dry_run=dry_run))
