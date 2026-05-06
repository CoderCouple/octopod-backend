"""Service layer for the email send queue processor.

Picks up scheduled messages, checks mailbox capacity and unsubscribe list,
injects tracking pixel + link rewrites, sends via the appropriate provider,
and advances recipients to the next step.
"""

import base64
import logging
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enum.email import (
    EmailEventType,
    MailboxProvider,
    MailboxStatus,
    MessageStatus,
    SendProvider,
)
from app.db.repository.campaign_recipient_repository import CampaignRecipientRepository
from app.db.repository.email_event_repository import EmailEventRepository
from app.db.repository.email_message_repository import EmailMessageRepository
from app.db.repository.email_unsubscribe_repository import EmailUnsubscribeRepository
from app.db.repository.mailbox_repository import MailboxRepository
from app.model.email_event_model import EmailEvent
from app.model.email_message_model import EmailMessage
from app.model.mailbox_model import Mailbox
from app.outreach.link_rewriter import rewrite_links
from app.outreach.tracking_pixel import inject_tracking_pixel
from app.service.mailbox_service import MailboxService
from app.settings import settings

logger = logging.getLogger(__name__)


class EmailSendingService:
    """Processes the email send queue."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = EmailMessageRepository(db)
        self.mailbox_repo = MailboxRepository(db)
        self.unsub_repo = EmailUnsubscribeRepository(db)
        self.event_repo = EmailEventRepository(db)
        self.recipient_repo = CampaignRecipientRepository(db)
        self.mailbox_service = MailboxService(db)

    async def process_send_queue(self, batch_size: int = 50) -> int:
        """Process a batch of scheduled messages. Returns count of messages sent."""
        messages = await self.message_repo.get_scheduled_messages(batch_size)
        if not messages:
            return 0

        sent_count = 0
        # Group by mailbox for capacity checking
        mailbox_cache: dict[str, Mailbox] = {}

        for message in messages:
            try:
                # Load mailbox
                mailbox = mailbox_cache.get(message.mailbox_id)
                if not mailbox:
                    mailbox = await self.mailbox_repo.get_by_id(message.mailbox_id)
                    if mailbox:
                        mailbox_cache[message.mailbox_id] = mailbox

                if not mailbox or mailbox.status != MailboxStatus.CONNECTED.value:
                    message.status = MessageStatus.FAILED.value
                    message.error_message = "Mailbox not connected"
                    message.failed_at = datetime.now(timezone.utc)
                    await self.message_repo.update(message)
                    continue

                # Check capacity
                remaining = await self.mailbox_service.check_capacity(mailbox.id)
                if remaining <= 0:
                    continue  # Skip, will retry next cycle

                # Check unsubscribe list
                if await self.unsub_repo.is_unsubscribed(message.to_email):
                    message.status = MessageStatus.CANCELLED.value
                    message.error_message = "Recipient unsubscribed"
                    await self.message_repo.update(message)
                    continue

                # Mark as sending
                message.status = MessageStatus.SENDING.value
                await self.message_repo.update(message)

                # Inject tracking
                body = message.body_html
                base_url = settings.tracking_base_url
                body = inject_tracking_pixel(body, message.tracking_id, base_url)
                body, link_map = rewrite_links(body, message.tracking_id, base_url)
                message.link_map = link_map

                # Send
                success = await self._send(mailbox, message, body)

                if success:
                    message.status = MessageStatus.SENT.value
                    message.sent_at = datetime.now(timezone.utc)
                    message.provider = _provider_for_mailbox(mailbox)
                    await self.message_repo.update(message)
                    await self.mailbox_service.increment_send_count(mailbox.id)

                    # Record sent event
                    event = EmailEvent(
                        message_id=message.id,
                        event_type=EmailEventType.SENT.value,
                    )
                    await self.event_repo.create(event)

                    # Advance recipient to next step
                    recipient = await self.recipient_repo.get_by_id(message.recipient_id)
                    if recipient:
                        from app.service.campaign_service import CampaignService

                        campaign_svc = CampaignService(self.db)
                        await campaign_svc.advance_recipient(recipient)

                    sent_count += 1
                else:
                    await self._handle_failure(message)

            except Exception as e:
                logger.exception(f"Error sending message {message.id}: {e}")
                message.status = MessageStatus.FAILED.value
                message.error_message = str(e)[:500]
                message.failed_at = datetime.now(timezone.utc)
                await self.message_repo.update(message)

        return sent_count

    async def _send(self, mailbox: Mailbox, message: EmailMessage, body_html: str) -> bool:
        """Send via the appropriate provider."""
        if mailbox.provider == MailboxProvider.GMAIL.value:
            return await self._send_gmail(mailbox, message, body_html)
        elif mailbox.provider == MailboxProvider.OUTLOOK.value:
            return await self._send_outlook(mailbox, message, body_html)
        elif mailbox.provider == MailboxProvider.SMTP.value:
            return await self._send_smtp(mailbox, message, body_html)
        elif mailbox.provider == MailboxProvider.SES.value:
            return await self._send_ses(mailbox, message, body_html)
        return False

    async def _send_gmail(
        self, mailbox: Mailbox, message: EmailMessage, body_html: str
    ) -> bool:
        """Send via Gmail REST API."""
        token = mailbox.access_token
        if not token:
            token = await self.mailbox_service.refresh_token(mailbox)
        if not token:
            return False

        mime = MIMEMultipart("alternative")
        mime["From"] = f"{message.from_name or ''} <{message.from_email}>".strip()
        mime["To"] = message.to_email
        mime["Subject"] = message.subject
        if message.body_text:
            mime.attach(MIMEText(message.body_text, "plain"))
        mime.attach(MIMEText(body_html, "html"))

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                message.provider_message_id = data.get("id")
                message.thread_id = data.get("threadId")
                return True
            else:
                message.error_message = f"Gmail API {resp.status_code}: {resp.text[:200]}"
                return False

    async def _send_outlook(
        self, mailbox: Mailbox, message: EmailMessage, body_html: str
    ) -> bool:
        """Send via Microsoft Graph API."""
        token = mailbox.access_token
        if not token:
            token = await self.mailbox_service.refresh_token(mailbox)
        if not token:
            return False

        payload = {
            "message": {
                "subject": message.subject,
                "body": {"contentType": "HTML", "content": body_html},
                "from": {
                    "emailAddress": {
                        "address": message.from_email,
                        "name": message.from_name or "",
                    }
                },
                "toRecipients": [
                    {"emailAddress": {"address": message.to_email}}
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/me/sendMail",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0,
            )
            if resp.status_code == 202:
                return True
            else:
                message.error_message = f"Graph API {resp.status_code}: {resp.text[:200]}"
                return False

    async def _send_smtp(
        self, mailbox: Mailbox, message: EmailMessage, body_html: str
    ) -> bool:
        """Send via SMTP."""
        try:
            import aiosmtplib

            mime = MIMEMultipart("alternative")
            mime["From"] = f"{message.from_name or ''} <{message.from_email}>".strip()
            mime["To"] = message.to_email
            mime["Subject"] = message.subject
            if message.body_text:
                mime.attach(MIMEText(message.body_text, "plain"))
            mime.attach(MIMEText(body_html, "html"))

            await aiosmtplib.send(
                mime,
                hostname=mailbox.smtp_host,
                port=mailbox.smtp_port,
                username=mailbox.smtp_username,
                password=mailbox.smtp_password,
                use_tls=mailbox.smtp_use_tls,
                timeout=30,
            )
            return True
        except Exception as e:
            message.error_message = f"SMTP error: {str(e)[:200]}"
            return False

    async def _send_ses(
        self, mailbox: Mailbox, message: EmailMessage, body_html: str
    ) -> bool:
        """Send via AWS SES through the SQS queue."""
        from app.service.sqs_publisher import SqsPublisher

        publisher = SqsPublisher()
        payload = {
            "messageId": message.id,
            "to": message.to_email,
            "subject": message.subject,
            "bodyHtml": body_html,
            "bodyText": message.body_text or "",
            "senderEmail": message.from_email,
            "senderName": message.from_name or "",
            "trackingId": message.tracking_id,
        }
        msg_id = await publisher.publish(payload)
        if msg_id:
            message.provider_message_id = msg_id
            return True
        return False

    async def _handle_failure(self, message: EmailMessage) -> None:
        """Handle a send failure with retry logic."""
        message.retry_count += 1
        if message.retry_count >= message.max_retries:
            message.status = MessageStatus.FAILED.value
            message.failed_at = datetime.now(timezone.utc)

            event = EmailEvent(
                message_id=message.id,
                event_type=EmailEventType.FAILED.value,
            )
            await self.event_repo.create(event)
        else:
            # Exponential backoff: 5min * 2^retry
            backoff = timedelta(minutes=5 * (2**message.retry_count))
            message.status = MessageStatus.SCHEDULED.value
            message.next_retry_at = datetime.now(timezone.utc) + backoff
            message.scheduled_at = datetime.now(timezone.utc) + backoff

        await self.message_repo.update(message)


def _provider_for_mailbox(mailbox: Mailbox) -> str:
    """Map mailbox provider to send provider enum value."""
    mapping = {
        MailboxProvider.GMAIL.value: SendProvider.GMAIL_API.value,
        MailboxProvider.OUTLOOK.value: SendProvider.OUTLOOK_GRAPH.value,
        MailboxProvider.SMTP.value: SendProvider.SMTP.value,
        MailboxProvider.SES.value: SendProvider.AWS_SES.value,
    }
    return mapping.get(mailbox.provider, SendProvider.SMTP.value)
