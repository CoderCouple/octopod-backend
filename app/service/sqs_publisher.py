"""SQS publisher for sending email payloads to the SES processing queue."""

import json
import logging

import aioboto3

from app.settings import settings

logger = logging.getLogger(__name__)


class SqsPublisher:
    """Publishes email payloads to an SQS FIFO queue for Lambda → SES delivery."""

    def __init__(self) -> None:
        self._session = aioboto3.Session()

    async def publish(self, payload: dict) -> str | None:
        """Push an email payload to the SQS FIFO queue.

        Returns the SQS message ID on success, or None on failure.
        """
        queue_url = settings.sqs_email_queue_url
        if not queue_url:
            logger.error("sqs_email_queue_url is not configured")
            return None

        try:
            async with self._session.client("sqs", region_name=settings.aws_region) as sqs:
                resp = await sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(payload),
                    MessageGroupId=settings.sqs_email_message_group,
                    MessageDeduplicationId=payload["messageId"],
                )
                msg_id: str | None = resp.get("MessageId")
                logger.info("Published email %s to SQS, MessageId=%s", payload["messageId"], msg_id)
                return msg_id
        except Exception:
            logger.exception("Failed to publish email %s to SQS", payload.get("messageId"))
            return None
