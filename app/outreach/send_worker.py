"""Background send worker that polls the email send queue.

Runs as an asyncio task registered in the FastAPI lifespan.
"""

import asyncio
import logging

from app.db.engine import get_async_session_factory
from app.service.email_sending_service import EmailSendingService
from app.settings import settings

logger = logging.getLogger(__name__)


class SendWorker:
    """Async worker that periodically processes the email send queue."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the send worker loop."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("SendWorker started")

    async def stop(self) -> None:
        """Stop the send worker loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SendWorker stopped")

    async def _run(self) -> None:
        """Main loop: poll send queue at configured interval."""
        poll_interval = getattr(settings, "send_worker_poll_interval", 30)
        batch_size = getattr(settings, "send_worker_batch_size", 50)

        while self._running:
            try:
                factory = get_async_session_factory()
                async with factory() as session:
                    try:
                        service = EmailSendingService(session)
                        sent = await service.process_send_queue(batch_size)
                        if sent > 0:
                            logger.info(f"SendWorker: sent {sent} emails")
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception("SendWorker: error processing send queue")
            except Exception:
                logger.exception("SendWorker: error creating session")

            await asyncio.sleep(poll_interval)


# Module-level singleton
send_worker = SendWorker()
