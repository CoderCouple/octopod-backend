"""Lambda handler: receives SQS messages and sends emails via AWS SES."""

import json
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses = boto3.client("ses")


def handler(event, context):
    """Process SQS records and send each email through SES."""
    for record in event["Records"]:
        payload = json.loads(record["body"])

        sender = payload.get("senderEmail", "")
        sender_name = payload.get("senderName", "")
        source = f"{sender_name} <{sender}>" if sender_name else sender

        ses.send_email(
            Source=source,
            Destination={"ToAddresses": [payload["to"]]},
            Message={
                "Subject": {"Data": payload["subject"], "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": payload["bodyHtml"], "Charset": "UTF-8"},
                    "Text": {"Data": payload.get("bodyText", ""), "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Sent email %s to %s", payload.get("messageId"), payload["to"])

    return {"statusCode": 200}
