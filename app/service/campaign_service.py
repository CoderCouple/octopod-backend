"""Service layer for email campaign management.

Handles campaign CRUD, step management, recipient enrollment,
message scheduling, and analytics aggregation.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.email_campaign_request import (
    AddRecipientRequest,
    CreateCampaignRequest,
    CreateStepRequest,
    UpdateCampaignRequest,
    UpdateStepRequest,
)
from app.api.v1.response.email_campaign_response import (
    CampaignAnalyticsResponse,
    CampaignRecipientResponse,
    CampaignStepResponse,
    EmailCampaignResponse,
    EmailMessageResponse,
)
from app.common.enum.email import CampaignStatus, MessageStatus, RecipientStatus
from app.common.exceptions import EntityNotFoundError, InvalidStateTransitionError
from app.db.repository.campaign_recipient_repository import CampaignRecipientRepository
from app.db.repository.campaign_step_repository import CampaignStepRepository
from app.db.repository.email_campaign_repository import EmailCampaignRepository
from app.db.repository.email_message_repository import EmailMessageRepository
from app.db.repository.email_template_repository import EmailTemplateRepository
from app.db.repository.mailbox_repository import MailboxRepository
from app.model.campaign_recipient_model import CampaignRecipient
from app.model.campaign_step_model import CampaignStep
from app.model.email_campaign_model import EmailCampaign
from app.model.email_message_model import EmailMessage

logger = logging.getLogger(__name__)

# Allowed state transitions
_TRANSITIONS = {
    CampaignStatus.DRAFT.value: {CampaignStatus.ACTIVE.value, CampaignStatus.CANCELLED.value},
    CampaignStatus.ACTIVE.value: {
        CampaignStatus.PAUSED.value,
        CampaignStatus.COMPLETED.value,
        CampaignStatus.CANCELLED.value,
    },
    CampaignStatus.PAUSED.value: {
        CampaignStatus.ACTIVE.value,
        CampaignStatus.CANCELLED.value,
    },
    CampaignStatus.COMPLETED.value: set(),
    CampaignStatus.CANCELLED.value: set(),
}


class CampaignService:
    """Service for managing email campaigns, steps, and recipients."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.campaign_repo = EmailCampaignRepository(db)
        self.step_repo = CampaignStepRepository(db)
        self.recipient_repo = CampaignRecipientRepository(db)
        self.message_repo = EmailMessageRepository(db)
        self.template_repo = EmailTemplateRepository(db)
        self.mailbox_repo = MailboxRepository(db)

    # ── Campaign CRUD ──────────────────────────────────────────

    async def create_campaign(
        self, data: CreateCampaignRequest, owner_id: str, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        mailbox = await self.mailbox_repo.get_by_id(data.mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", data.mailbox_id)

        send_start = _parse_time(data.send_window_start)
        send_end = _parse_time(data.send_window_end)

        campaign = EmailCampaign(
            owner_id=owner_id,
            mailbox_id=data.mailbox_id,
            name=data.name,
            description=data.description,
            status=CampaignStatus.DRAFT.value,
            send_window_start=send_start,
            send_window_end=send_end,
            send_timezone=data.send_timezone,
            send_days=data.send_days or [1, 2, 3, 4, 5],
            stop_on_reply=data.stop_on_reply,
            stop_on_bounce=data.stop_on_bounce,
            track_opens=data.track_opens,
            track_clicks=data.track_clicks,
            metadata_=data.metadata or {},
            created_by=actor_id,
            updated_by=actor_id,
        )
        campaign = await self.campaign_repo.create(campaign)
        return EmailCampaignResponse.model_validate(campaign)

    async def get_campaign(self, campaign_id: str) -> EmailCampaignResponse:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)
        return EmailCampaignResponse.model_validate(campaign)

    async def list_campaigns(
        self, owner_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailCampaignResponse], int]:
        campaigns, total = await self.campaign_repo.list_by_owner(owner_id, offset, limit)
        return [EmailCampaignResponse.model_validate(c) for c in campaigns], total

    async def update_campaign(
        self, campaign_id: str, data: UpdateCampaignRequest, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)

        update_data = data.model_dump(exclude_unset=True)
        if "send_window_start" in update_data:
            update_data["send_window_start"] = _parse_time(update_data["send_window_start"])
        if "send_window_end" in update_data:
            update_data["send_window_end"] = _parse_time(update_data["send_window_end"])
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")

        for key, value in update_data.items():
            setattr(campaign, key, value)
        campaign.updated_by = actor_id
        campaign.updated_at = datetime.now(timezone.utc)

        campaign = await self.campaign_repo.update(campaign)
        return EmailCampaignResponse.model_validate(campaign)

    async def delete_campaign(self, campaign_id: str, actor_id: str | None = None) -> None:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)
        await self.campaign_repo.soft_delete(campaign, actor_id)

    # ── State machine ──────────────────────────────────────────

    async def start_campaign(
        self, campaign_id: str, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        campaign = await self._transition(campaign_id, CampaignStatus.ACTIVE.value, actor_id)
        campaign.started_at = datetime.now(timezone.utc)
        await self.campaign_repo.update(campaign)

        # Schedule first step for all active recipients
        first_step = await self.step_repo.get_first_step(campaign_id)
        if first_step:
            recipients, _ = await self.recipient_repo.list_by_campaign(campaign_id, 0, 10000)
            for r in recipients:
                if r.status == RecipientStatus.ACTIVE.value:
                    await self._schedule_message(campaign, first_step, r)

        return EmailCampaignResponse.model_validate(campaign)

    async def pause_campaign(
        self, campaign_id: str, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        campaign = await self._transition(campaign_id, CampaignStatus.PAUSED.value, actor_id)
        return EmailCampaignResponse.model_validate(campaign)

    async def resume_campaign(
        self, campaign_id: str, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        campaign = await self._transition(campaign_id, CampaignStatus.ACTIVE.value, actor_id)
        return EmailCampaignResponse.model_validate(campaign)

    async def cancel_campaign(
        self, campaign_id: str, actor_id: str | None = None
    ) -> EmailCampaignResponse:
        campaign = await self._transition(campaign_id, CampaignStatus.CANCELLED.value, actor_id)
        return EmailCampaignResponse.model_validate(campaign)

    async def _transition(
        self, campaign_id: str, target: str, actor_id: str | None
    ) -> EmailCampaign:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)

        allowed = _TRANSITIONS.get(campaign.status, set())
        if target not in allowed:
            raise InvalidStateTransitionError(campaign.status, target)

        campaign.status = target
        campaign.updated_by = actor_id
        campaign.updated_at = datetime.now(timezone.utc)
        await self.campaign_repo.update(campaign)
        return campaign

    # ── Steps CRUD ─────────────────────────────────────────────

    async def add_step(
        self, campaign_id: str, data: CreateStepRequest, actor_id: str | None = None
    ) -> CampaignStepResponse:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)

        max_order = await self.step_repo.get_max_order(campaign_id)
        step = CampaignStep(
            campaign_id=campaign_id,
            template_id=data.template_id,
            step_order=max_order + 1,
            step_type=data.step_type,
            delay_days=data.delay_days,
            delay_hours=data.delay_hours,
            subject_override=data.subject_override,
            body_override=data.body_override,
            condition_field=data.condition_field,
            condition_op=data.condition_op,
            condition_value=data.condition_value,
            created_by=actor_id,
            updated_by=actor_id,
        )
        step = await self.step_repo.create(step)
        return CampaignStepResponse.model_validate(step)

    async def list_steps(self, campaign_id: str) -> list[CampaignStepResponse]:
        steps = await self.step_repo.list_by_campaign(campaign_id)
        return [CampaignStepResponse.model_validate(s) for s in steps]

    async def update_step(
        self, step_id: str, data: UpdateStepRequest, actor_id: str | None = None
    ) -> CampaignStepResponse:
        step = await self.step_repo.get_by_id(step_id)
        if not step:
            raise EntityNotFoundError("CampaignStep", step_id)

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(step, key, value)
        step.updated_by = actor_id
        step.updated_at = datetime.now(timezone.utc)

        step = await self.step_repo.update(step)
        return CampaignStepResponse.model_validate(step)

    async def delete_step(self, step_id: str, actor_id: str | None = None) -> None:
        step = await self.step_repo.get_by_id(step_id)
        if not step:
            raise EntityNotFoundError("CampaignStep", step_id)
        await self.step_repo.soft_delete(step, actor_id)

    # ── Recipients ─────────────────────────────────────────────

    async def add_recipient(
        self, campaign_id: str, data: AddRecipientRequest, actor_id: str | None = None
    ) -> CampaignRecipientResponse:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)

        existing = await self.recipient_repo.get_by_email_and_campaign(data.email, campaign_id)
        if existing:
            raise DuplicateEntityError("Recipient", "email", data.email)

        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            company=data.company,
            title=data.title,
            status=RecipientStatus.ACTIVE.value,
            merge_variables=data.merge_variables or {},
            created_by=actor_id,
            updated_by=actor_id,
        )
        recipient = await self.recipient_repo.create(recipient)

        await self.campaign_repo.increment_stat(campaign_id, "total_recipients")
        return CampaignRecipientResponse.model_validate(recipient)

    async def list_recipients(
        self, campaign_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[CampaignRecipientResponse], int]:
        recipients, total = await self.recipient_repo.list_by_campaign(
            campaign_id, offset, limit
        )
        return [CampaignRecipientResponse.model_validate(r) for r in recipients], total

    async def remove_recipient(
        self, recipient_id: str, actor_id: str | None = None
    ) -> None:
        recipient = await self.recipient_repo.get_by_id(recipient_id)
        if not recipient:
            raise EntityNotFoundError("Recipient", recipient_id)
        await self.message_repo.cancel_scheduled_for_recipient(recipient_id)
        await self.recipient_repo.soft_delete(recipient, actor_id)

    # ── Messages ───────────────────────────────────────────────

    async def list_messages(
        self, campaign_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailMessageResponse], int]:
        messages, total = await self.message_repo.list_by_campaign(campaign_id, offset, limit)
        return [EmailMessageResponse.model_validate(m) for m in messages], total

    # ── Analytics ──────────────────────────────────────────────

    async def get_analytics(self, campaign_id: str) -> CampaignAnalyticsResponse:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise EntityNotFoundError("Campaign", campaign_id)

        sent = campaign.total_sent or 1  # avoid division by zero
        return CampaignAnalyticsResponse(
            campaign_id=campaign.id,
            total_recipients=campaign.total_recipients,
            total_sent=campaign.total_sent,
            total_delivered=campaign.total_delivered,
            total_opened=campaign.total_opened,
            total_clicked=campaign.total_clicked,
            total_replied=campaign.total_replied,
            total_bounced=campaign.total_bounced,
            total_unsubscribed=campaign.total_unsubscribed,
            open_rate=round(campaign.total_opened / sent, 4),
            click_rate=round(campaign.total_clicked / sent, 4),
            reply_rate=round(campaign.total_replied / sent, 4),
            bounce_rate=round(campaign.total_bounced / sent, 4),
        )

    # ── Scheduling helpers ─────────────────────────────────────

    async def _schedule_message(
        self,
        campaign: EmailCampaign,
        step: CampaignStep,
        recipient: CampaignRecipient,
    ) -> EmailMessage | None:
        """Render and schedule a single email message for a recipient."""
        if step.step_type != "email":
            return None

        # Resolve template
        subject = step.subject_override or ""
        body_html = step.body_override or ""
        if step.template_id:
            template = await self.template_repo.get_by_id(step.template_id)
            if template:
                subject = step.subject_override or template.subject
                body_html = step.body_override or template.body_html

        # Render Jinja2 variables
        merge_vars = {
            "first_name": recipient.first_name or "",
            "last_name": recipient.last_name or "",
            "email": recipient.email,
            "company": recipient.company or "",
            "title": recipient.title or "",
            **(recipient.merge_variables or {}),
        }
        try:
            subject = Template(subject).render(**merge_vars)
            body_html = Template(body_html).render(**merge_vars)
        except Exception:
            logger.warning(f"Template render failed for recipient {recipient.id}")

        # Compute send time
        send_at = self._compute_send_time(campaign, step)

        mailbox = await self.mailbox_repo.get_by_id(campaign.mailbox_id)
        if not mailbox:
            return None

        tracking_id = str(uuid.uuid4())
        message = EmailMessage(
            campaign_id=campaign.id,
            step_id=step.id,
            recipient_id=recipient.id,
            mailbox_id=mailbox.id,
            tracking_id=tracking_id,
            from_email=mailbox.email_address,
            from_name=mailbox.display_name,
            to_email=recipient.email,
            subject=subject,
            body_html=body_html,
            status=MessageStatus.SCHEDULED.value,
            scheduled_at=send_at,
        )
        message = await self.message_repo.create(message)

        # Update recipient's next_send_at
        recipient.next_send_at = send_at
        recipient.current_step_order = step.step_order
        await self.recipient_repo.update(recipient)

        return message

    def _compute_send_time(self, campaign: EmailCampaign, step: CampaignStep) -> datetime:
        """Calculate when to send based on delay + send window."""
        now = datetime.now(timezone.utc)
        delay = timedelta(days=step.delay_days, hours=step.delay_hours)
        send_at = now + delay

        # Clamp to send window if configured (stored as "HH:MM" strings)
        if campaign.send_window_start and campaign.send_window_end:
            window_start = _parse_time_to_parts(campaign.send_window_start)
            window_end = _parse_time_to_parts(campaign.send_window_end)
            if window_start and window_end:
                current_minutes = send_at.hour * 60 + send_at.minute
                start_minutes = window_start[0] * 60 + window_start[1]
                end_minutes = window_end[0] * 60 + window_end[1]

                if current_minutes < start_minutes:
                    send_at = send_at.replace(
                        hour=window_start[0], minute=window_start[1], second=0, microsecond=0
                    )
                elif current_minutes > end_minutes:
                    send_at = send_at + timedelta(days=1)
                    send_at = send_at.replace(
                        hour=window_start[0], minute=window_start[1], second=0, microsecond=0
                    )

        return send_at

    async def advance_recipient(self, recipient: CampaignRecipient) -> None:
        """Advance a recipient to the next step after a message is sent."""
        campaign = await self.campaign_repo.get_by_id(recipient.campaign_id)
        if not campaign or campaign.status != CampaignStatus.ACTIVE.value:
            return

        next_step = await self.step_repo.get_next_step(
            recipient.campaign_id, recipient.current_step_order
        )
        if next_step:
            await self._schedule_message(campaign, next_step, recipient)
        else:
            # No more steps — mark as completed
            recipient.status = RecipientStatus.COMPLETED.value
            recipient.next_send_at = None
            await self.recipient_repo.update(recipient)


def _parse_time(value: str | None) -> str | None:
    """Validate and normalize HH:MM string."""
    if not value:
        return None
    parts = value.split(":")
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def _parse_time_to_parts(value: str) -> tuple[int, int] | None:
    """Parse HH:MM string to (hour, minute) tuple."""
    try:
        parts = value.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


# Need this import at module level for add_recipient
from app.common.exceptions import DuplicateEntityError  # noqa: E402
