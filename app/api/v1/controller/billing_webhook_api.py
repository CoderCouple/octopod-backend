"""Stripe webhook endpoint — mounted at root level, no JWT auth."""

import logging

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.billing import stripe_client
from app.db.session import get_db
from app.service.billing_service import BillingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(alias="Stripe-Signature"),
):
    """Process incoming Stripe webhook events.

    Verifies the signature, deduplicates, and dispatches to BillingService.
    """
    payload = await request.body()

    try:
        event = stripe_client.construct_webhook_event(payload, stripe_signature)
    except Exception:
        logger.warning("Invalid Stripe webhook signature")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid signature"},
        )

    service = BillingService(db)
    await service.handle_webhook_event(event)

    return {"status": "ok"}
