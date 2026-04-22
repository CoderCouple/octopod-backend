from enum import Enum


class MailboxProvider(str, Enum):
    """Supported email provider types.

    Values:
        GMAIL: Google Gmail via OAuth + API.
        OUTLOOK: Microsoft Outlook via OAuth + Graph API.
        SMTP: Generic SMTP server.
    """

    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP = "smtp"


class MailboxStatus(str, Enum):
    """Connection state of a mailbox.

    Values:
        CONNECTED: Mailbox is operational.
        DISCONNECTED: OAuth revoked or credentials removed.
        ERROR: Persistent error (e.g. token refresh failure).
        RATE_LIMITED: Daily send limit reached.
    """

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class CampaignStatus(str, Enum):
    """Lifecycle status of an email campaign.

    Values:
        DRAFT: Campaign is being configured.
        ACTIVE: Campaign is running and sending.
        PAUSED: Campaign is temporarily stopped.
        COMPLETED: All sequences finished.
        CANCELLED: Campaign permanently stopped.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Type of a campaign sequence step.

    Values:
        EMAIL: Send an email.
        WAIT: Wait for a specified duration.
        CONDITION: Branch based on a condition.
    """

    EMAIL = "email"
    WAIT = "wait"
    CONDITION = "condition"


class RecipientStatus(str, Enum):
    """Status of a recipient within a campaign.

    Values:
        ACTIVE: Recipient is progressing through the sequence.
        PAUSED: Recipient is temporarily paused.
        COMPLETED: Recipient finished all steps.
        REPLIED: Recipient replied; sequence stopped.
        BOUNCED: Email bounced; sequence stopped.
        UNSUBSCRIBED: Recipient unsubscribed.
        ERROR: Persistent delivery error.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    ERROR = "error"


class MessageStatus(str, Enum):
    """Delivery status of an individual email message.

    Values:
        SCHEDULED: Queued for future delivery.
        QUEUED: Picked up by send worker.
        SENDING: Currently being transmitted.
        SENT: Successfully handed to provider.
        DELIVERED: Provider confirmed delivery.
        FAILED: Permanent delivery failure.
        CANCELLED: Cancelled before sending.
        BOUNCED: Hard or soft bounce.
    """

    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BOUNCED = "bounced"


class EmailEventType(str, Enum):
    """Granular email tracking event types.

    Values:
        SENT: Email was sent.
        DELIVERED: Email was delivered.
        OPENED: Recipient opened the email.
        CLICKED: Recipient clicked a link.
        REPLIED: Recipient replied.
        BOUNCED: Email bounced.
        UNSUBSCRIBED: Recipient unsubscribed.
        COMPLAINED: Recipient marked as spam.
        FAILED: Delivery failure.
    """

    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    COMPLAINED = "complained"
    FAILED = "failed"


class EmailSource(str, Enum):
    """How a recipient's email address was discovered.

    Values:
        MANUAL: Entered manually.
        GITHUB_PUBLIC: GitHub profile public email.
        GITHUB_COMMIT: Extracted from commit author.
        HUGGINGFACE: Linked via HuggingFace profile.
        HUNTER: Found via Hunter.io API.
        APOLLO: Found via Apollo.io API.
        OTHER: Other source.
    """

    MANUAL = "manual"
    GITHUB_PUBLIC = "github_public"
    GITHUB_COMMIT = "github_commit"
    HUGGINGFACE = "huggingface"
    HUNTER = "hunter"
    APOLLO = "apollo"
    OTHER = "other"


class SendProvider(str, Enum):
    """Provider used to transmit an email.

    Values:
        GMAIL_API: Google Gmail REST API.
        OUTLOOK_GRAPH: Microsoft Graph API.
        SMTP: Generic SMTP relay.
        SENDGRID: SendGrid API.
    """

    GMAIL_API = "gmail_api"
    OUTLOOK_GRAPH = "outlook_graph"
    SMTP = "smtp"
    SENDGRID = "sendgrid"
