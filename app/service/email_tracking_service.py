"""Service layer for email tracking events.

Records opens, clicks, replies, bounces, and unsubscribes.
Handles auto-stopping sequences on reply/bounce.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enum.email import EmailEventType, MessageStatus, RecipientStatus
from app.db.repository.campaign_recipient_repository import CampaignRecipientRepository
from app.db.repository.email_campaign_repository import EmailCampaignRepository
from app.db.repository.email_event_repository import EmailEventRepository
from app.db.repository.email_message_repository import EmailMessageRepository
from app.db.repository.email_unsubscribe_repository import EmailUnsubscribeRepository
from app.model.email_event_model import EmailEvent
from app.model.email_unsubscribe_model import EmailUnsubscribe

logger = logging.getLogger(__name__)


class EmailTrackingService:
    """Handles email tracking event recording and sequence control."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = EmailMessageRepository(db)
        self.event_repo = EmailEventRepository(db)
        self.recipient_repo = CampaignRecipientRepository(db)
        self.campaign_repo = EmailCampaignRepository(db)
        self.unsub_repo = EmailUnsubscribeRepository(db)

    async def record_open(
        self,
        tracking_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Record an email open event. Returns True if message was found."""
        message = await self.message_repo.get_by_tracking_id(tracking_id)
        if not message:
            return False

        # Record event
        event = EmailEvent(
            message_id=message.id,
            event_type=EmailEventType.OPENED.value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.event_repo.create(event)

        # Update message stats
        message.open_count += 1
        if not message.opened_at:
            message.opened_at = datetime.now(timezone.utc)
            # Increment campaign counter on first open
            await self.campaign_repo.increment_stat(message.campaign_id, "total_opened")
        await self.message_repo.update(message)

        return True

    async def record_click(
        self,
        tracking_id: str,
        link_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str | None:
        """Record a click event and return the original URL for redirect."""
        message = await self.message_repo.get_by_tracking_id(tracking_id)
        if not message:
            return None

        # Resolve original URL from link map
        link_map = message.link_map or {}
        original_url = link_map.get(link_id)
        if not original_url:
            return None

        # Record event
        event = EmailEvent(
            message_id=message.id,
            event_type=EmailEventType.CLICKED.value,
            ip_address=ip_address,
            user_agent=user_agent,
            link_url=original_url,
        )
        await self.event_repo.create(event)

        # Update message stats
        message.click_count += 1
        if not message.clicked_at:
            message.clicked_at = datetime.now(timezone.utc)
            await self.campaign_repo.increment_stat(message.campaign_id, "total_clicked")
        await self.message_repo.update(message)

        return original_url

    async def record_reply(
        self,
        tracking_id: str | None = None,
        message_id_header: str | None = None,
        in_reply_to: str | None = None,
    ) -> bool:
        """Record a reply event. Stops the sequence if campaign.stop_on_reply is True."""
        message = None
        if tracking_id:
            message = await self.message_repo.get_by_tracking_id(tracking_id)
        elif in_reply_to:
            # Match via In-Reply-To header
            from sqlalchemy import select

            from app.model.email_message_model import EmailMessage

            result = await self.db.execute(
                select(EmailMessage).where(EmailMessage.message_id_header == in_reply_to)
            )
            message = result.scalar_one_or_none()

        if not message:
            return False

        # Record event
        event = EmailEvent(
            message_id=message.id,
            event_type=EmailEventType.REPLIED.value,
        )
        await self.event_repo.create(event)

        # Update message
        message.replied_at = datetime.now(timezone.utc)
        await self.message_repo.update(message)

        # Increment campaign counter
        await self.campaign_repo.increment_stat(message.campaign_id, "total_replied")

        # Stop sequence if configured
        campaign = await self.campaign_repo.get_by_id(message.campaign_id)
        if campaign and campaign.stop_on_reply:
            recipient = await self.recipient_repo.get_by_id(message.recipient_id)
            if recipient:
                recipient.status = RecipientStatus.REPLIED.value
                recipient.next_send_at = None
                await self.recipient_repo.update(recipient)
                await self.message_repo.cancel_scheduled_for_recipient(recipient.id)

        return True

    async def record_bounce(
        self,
        tracking_id: str | None = None,
        message_id: str | None = None,
        bounce_type: str = "hard",
        raw_payload: dict | None = None,
    ) -> bool:
        """Record a bounce event. Stops the sequence if campaign.stop_on_bounce is True."""
        message = None
        if tracking_id:
            message = await self.message_repo.get_by_tracking_id(tracking_id)
        elif message_id:
            message = await self.message_repo.get_by_id(message_id)

        if not message:
            return False

        # Record event
        event = EmailEvent(
            message_id=message.id,
            event_type=EmailEventType.BOUNCED.value,
            raw_payload=raw_payload or {},
        )
        await self.event_repo.create(event)

        # Update message
        message.status = MessageStatus.BOUNCED.value
        message.bounced_at = datetime.now(timezone.utc)
        await self.message_repo.update(message)

        # Increment campaign counter
        await self.campaign_repo.increment_stat(message.campaign_id, "total_bounced")

        # Stop sequence
        campaign = await self.campaign_repo.get_by_id(message.campaign_id)
        if campaign and campaign.stop_on_bounce:
            recipient = await self.recipient_repo.get_by_id(message.recipient_id)
            if recipient:
                recipient.status = RecipientStatus.BOUNCED.value
                recipient.next_send_at = None
                await self.recipient_repo.update(recipient)
                await self.message_repo.cancel_scheduled_for_recipient(recipient.id)

        return True

    async def process_unsubscribe(
        self,
        tracking_id: str,
        reason: str | None = None,
    ) -> bool:
        """Process an unsubscribe request. Adds to global unsub list and stops all campaigns."""
        message = await self.message_repo.get_by_tracking_id(tracking_id)
        if not message:
            return False

        # Record event
        event = EmailEvent(
            message_id=message.id,
            event_type=EmailEventType.UNSUBSCRIBED.value,
        )
        await self.event_repo.create(event)

        # Add to global unsubscribe list
        existing = await self.unsub_repo.get_by_email(message.to_email)
        if not existing:
            unsub = EmailUnsubscribe(
                email=message.to_email,
                reason=reason,
                source="tracking_link",
                message_id=message.id,
            )
            await self.unsub_repo.create(unsub)

        # Increment campaign counter
        await self.campaign_repo.increment_stat(message.campaign_id, "total_unsubscribed")

        # Stop the recipient in this campaign
        recipient = await self.recipient_repo.get_by_id(message.recipient_id)
        if recipient:
            recipient.status = RecipientStatus.UNSUBSCRIBED.value
            recipient.next_send_at = None
            await self.recipient_repo.update(recipient)
            await self.message_repo.cancel_scheduled_for_recipient(recipient.id)

        return True
