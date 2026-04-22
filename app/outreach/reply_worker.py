"""Background reply detection worker.

Polls for replies via IMAP as a fallback for Gmail Push / Outlook Push.
Matches In-Reply-To headers against sent message_id_header values.
"""

import asyncio
import logging

from app.db.engine import get_async_session_factory
from app.service.email_tracking_service import EmailTrackingService
from app.settings import settings

logger = logging.getLogger(__name__)


class ReplyWorker:
    """Async worker that periodically checks for email replies."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the reply detection loop."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("ReplyWorker started")

    async def stop(self) -> None:
        """Stop the reply detection loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ReplyWorker stopped")

    async def _run(self) -> None:
        """Main loop: check for replies at configured interval."""
        check_interval = getattr(settings, "reply_check_interval", 300)

        while self._running:
            try:
                factory = get_async_session_factory()
                async with factory() as session:
                    try:
                        tracking_svc = EmailTrackingService(session)
                        # In a full implementation, this would:
                        # 1. Connect to IMAP for each mailbox
                        # 2. Fetch recent messages
                        # 3. Match In-Reply-To headers
                        # 4. Call tracking_svc.record_reply()
                        #
                        # For now, replies are detected via:
                        # - Gmail Push notifications (webhook)
                        # - SendGrid webhook events
                        # - Manual IMAP polling (to be implemented)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception("ReplyWorker: error checking replies")
            except Exception:
                logger.exception("ReplyWorker: error creating session")

            await asyncio.sleep(check_interval)


# Module-level singleton
reply_worker = ReplyWorker()
