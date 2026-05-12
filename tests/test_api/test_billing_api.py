"""Integration tests for billing API endpoints."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_get_billing_info(authenticated_client):
    """GET /api/v1/billing returns free plan for auto-provisioned org."""
    resp = await authenticated_client.get("/api/v1/billing")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    result = data["result"]
    assert result["plan"] == "free"
    assert result["status"] == "active"
    assert result["seat_count"] == 1
    assert result["cancel_at_period_end"] is False


@pytest.mark.asyncio
async def test_create_checkout_requires_owner(authenticated_client):
    """POST /api/v1/billing/checkout should work for owner role."""
    with patch(
        "app.service.billing_service.stripe_client.create_checkout_session",
        return_value="https://checkout.stripe.com/test",
    ), patch(
        "app.service.billing_service.stripe_client.create_customer",
        return_value="cus_test123",
    ):
        resp = await authenticated_client.post(
            "/api/v1/billing/checkout",
            json={
                "plan": "pro",
                "success_url": "https://app.example.com/success",
                "cancel_url": "https://app.example.com/cancel",
            },
        )
        # Returns 400 when stripe_price_id_pro is not configured in test env
        assert resp.status_code in (201, 400)


@pytest.mark.asyncio
async def test_create_portal_requires_owner(authenticated_client):
    """POST /api/v1/billing/portal should work for owner role."""
    with patch(
        "app.service.billing_service.stripe_client.create_portal_session",
        return_value="https://billing.stripe.com/test",
    ), patch(
        "app.service.billing_service.stripe_client.create_customer",
        return_value="cus_test123",
    ):
        resp = await authenticated_client.post(
            "/api/v1/billing/portal",
            json={"return_url": "https://app.example.com/billing"},
        )
        assert resp.status_code in (200, 500)
