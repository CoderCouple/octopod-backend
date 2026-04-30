"""Email Tracking API controller.

Short-URL tracking endpoints for opens, clicks, and unsubscribes.
These are NOT behind /api/v1 — they need short, clean URLs.
Also includes webhook endpoints for SendGrid and Gmail push notifications.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, success_response
from app.db.session import get_db
from app.outreach.tracking_pixel import TRACKING_GIF
from app.service.email_tracking_service import EmailTrackingService

logger = logging.getLogger(__name__)

# These routes are mounted directly on the app (not under /api/v1)
router = APIRouter(tags=[Tags.Tracking])


def get_tracking_service(db: AsyncSession = Depends(get_db)) -> EmailTrackingService:
    return EmailTrackingService(db)


@router.get("/t/{tracking_id}.png")
async def track_open(
    tracking_id: str,
    request: Request,
    service: EmailTrackingService = Depends(get_tracking_service),
):
    """Track email open via 1x1 pixel image."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await service.record_open(tracking_id, ip, user_agent)
    return Response(
        content=TRACKING_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/c/{tracking_id}/{link_id}")
async def track_click(
    tracking_id: str,
    link_id: str,
    request: Request,
    service: EmailTrackingService = Depends(get_tracking_service),
):
    """Track link click and redirect to original URL."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    original_url = await service.record_click(tracking_id, link_id, ip, user_agent)
    if original_url:
        return RedirectResponse(url=original_url, status_code=302)
    return Response(status_code=404, content="Link not found")


@router.get("/unsub/{tracking_id}")
async def unsubscribe_page(
    tracking_id: str,
    service: EmailTrackingService = Depends(get_tracking_service),
):
    """Process unsubscribe request."""
    success = await service.process_unsubscribe(tracking_id, reason="one-click")
    if success:
        return Response(
            content="<html><body><h2>You have been unsubscribed.</h2></body></html>",
            media_type="text/html",
        )
    return Response(status_code=404, content="Tracking ID not found")


@router.post("/webhooks/sendgrid", response_model=BaseResponse)
async def sendgrid_webhook(
    request: Request,
    service: EmailTrackingService = Depends(get_tracking_service),
):
    """Process SendGrid event webhooks (bounce, delivered, etc.)."""
    events = await request.json()
    for event_data in events:
        event_type = event_data.get("event", "")
        sg_message_id = event_data.get("sg_message_id", "")

        if event_type == "bounce":
            await service.record_bounce(
                message_id=sg_message_id,
                bounce_type=event_data.get("type", "hard"),
                raw_payload=event_data,
            )
        elif event_type == "delivered":
            # Could record delivery event
            pass

    return success_response(None, "Webhook processed")


@router.post("/webhooks/gmail", response_model=BaseResponse)
async def gmail_push_notification(
    request: Request,
    service: EmailTrackingService = Depends(get_tracking_service),
):
    """Process Gmail Pub/Sub push notifications for reply detection."""
    payload = await request.json()
    # Gmail push notification contains encoded message data
    # In full implementation: decode, fetch message, match In-Reply-To header
    logger.info(f"Gmail push notification received: {payload.get('subscription', '')}")
    return success_response(None, "Notification processed")
