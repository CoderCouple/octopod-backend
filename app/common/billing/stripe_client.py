"""Thin wrapper around the Stripe SDK.

All Stripe SDK calls are synchronous — FastAPI runs them via threadpool
automatically when called from async service methods.
"""

import logging

import stripe

from app.settings import settings

logger = logging.getLogger(__name__)


def _configure() -> None:
    stripe.api_key = settings.stripe_secret_key


def create_customer(name: str, email: str | None = None, metadata: dict | None = None) -> str:
    """Create a Stripe customer and return the customer ID."""
    _configure()
    customer = stripe.Customer.create(
        name=name,
        email=email,
        metadata=metadata or {},
    )
    return customer.id


def create_checkout_session(
    customer_id: str,
    price_id: str,
    quantity: int,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    _configure()
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": quantity}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return session.url


def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    _configure()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def update_subscription_quantity(subscription_id: str, quantity: int) -> None:
    """Update the seat count on a subscription (triggers proration)."""
    _configure()
    sub = stripe.Subscription.retrieve(subscription_id)
    stripe.Subscription.modify(
        subscription_id,
        items=[{"id": sub["items"]["data"][0]["id"], "quantity": quantity}],
        proration_behavior="create_prorations",
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and construct a Stripe webhook event from raw payload."""
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )


def list_invoices(customer_id: str, limit: int = 20) -> list[dict]:
    """List recent invoices for a customer. Returns simplified dicts."""
    _configure()
    resp = stripe.Invoice.list(customer=customer_id, limit=limit)
    out = []
    for inv in resp.data:
        out.append(
            {
                "id": inv["id"],
                "number": inv.get("number"),
                "status": inv["status"],
                "amount_paid": inv["amount_paid"],
                "amount_due": inv["amount_due"],
                "currency": inv["currency"],
                "created": inv["created"],
                "period_start": inv.get("period_start"),
                "period_end": inv.get("period_end"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
                "invoice_pdf": inv.get("invoice_pdf"),
            }
        )
    return out
