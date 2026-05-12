"""Unit tests for BillingService."""

from unittest.mock import patch

import pytest

from app.model.subscription_model import Subscription
from app.service.billing_service import BillingService


@pytest.mark.asyncio
async def test_ensure_stripe_customer_creates_new(async_session):
    """ensure_stripe_customer creates a Stripe customer and local subscription."""
    with patch(
        "app.common.billing.stripe_client.create_customer",
        return_value="cus_new_123",
    ):
        service = BillingService(async_session)
        sub = await service.ensure_stripe_customer("org_test1", "Test Org", "test@example.com")

        assert sub.org_id == "org_test1"
        assert sub.stripe_customer_id == "cus_new_123"
        assert sub.plan == "free"
        assert sub.status == "active"
        assert sub.seat_count == 1


@pytest.mark.asyncio
async def test_ensure_stripe_customer_idempotent(async_session):
    """ensure_stripe_customer returns existing subscription if already created."""
    with patch(
        "app.common.billing.stripe_client.create_customer",
        return_value="cus_existing",
    ):
        service = BillingService(async_session)
        sub1 = await service.ensure_stripe_customer("org_test2", "Test Org")
        sub2 = await service.ensure_stripe_customer("org_test2", "Test Org")

        assert sub1.id == sub2.id
        assert sub1.stripe_customer_id == "cus_existing"


@pytest.mark.asyncio
async def test_get_billing_info_no_subscription(async_session):
    """get_billing_info returns free defaults when no subscription exists."""
    service = BillingService(async_session)
    info = await service.get_billing_info("org_nonexistent")

    assert info["plan"] == "free"
    assert info["status"] == "active"
    assert info["seat_count"] == 1
    assert info["stripe_customer_id"] is None


@pytest.mark.asyncio
async def test_get_billing_info_with_subscription(async_session):
    """get_billing_info returns subscription data when it exists."""
    sub = Subscription(
        org_id="org_info_test",
        stripe_customer_id="cus_info",
        plan="pro",
        status="active",
        seat_count=5,
    )
    async_session.add(sub)
    await async_session.flush()

    service = BillingService(async_session)
    info = await service.get_billing_info("org_info_test")

    assert info["plan"] == "pro"
    assert info["seat_count"] == 5
    assert info["stripe_customer_id"] == "cus_info"


@pytest.mark.asyncio
async def test_sync_seat_count(async_session):
    """sync_seat_count updates local seat count."""
    sub = Subscription(
        org_id="org_seat_test",
        stripe_customer_id="cus_seat",
        plan="free",
        status="active",
        seat_count=1,
    )
    async_session.add(sub)
    await async_session.flush()

    service = BillingService(async_session)
    await service.sync_seat_count("org_seat_test", 3)

    info = await service.get_billing_info("org_seat_test")
    assert info["seat_count"] == 3
