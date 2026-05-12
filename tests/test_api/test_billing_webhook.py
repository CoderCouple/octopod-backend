"""Integration tests for Stripe webhook endpoint."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_webhook_invalid_signature(async_client):
    """POST /webhooks/stripe with invalid signature returns 400."""
    with patch(
        "app.common.billing.stripe_client.construct_webhook_event",
        side_effect=Exception("Invalid signature"),
    ):
        resp = await async_client.post(
            "/webhooks/stripe",
            content=b'{"type": "test"}',
            headers={"Stripe-Signature": "invalid_sig"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid signature"


@pytest.mark.asyncio
async def test_webhook_valid_event(async_client):
    """POST /webhooks/stripe with valid signature returns 200."""
    mock_event = MagicMock()
    mock_event.id = "evt_test_123"
    mock_event.type = "checkout.session.completed"
    mock_event.data = {
        "object": {
            "metadata": {"org_id": "org_test"},
            "subscription": "sub_test",
        }
    }

    with patch(
        "app.common.billing.stripe_client.construct_webhook_event",
        return_value=mock_event,
    ):
        resp = await async_client.post(
            "/webhooks/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={"Stripe-Signature": "valid_sig"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
