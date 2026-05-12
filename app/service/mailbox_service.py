"""Service layer for mailbox management.

Handles connecting Gmail/Outlook/SMTP mailboxes, OAuth token management,
capacity checks, and daily send count resets.
"""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.mailbox_request import (
    ConnectGmailRequest,
    ConnectOutlookRequest,
    ConnectSesRequest,
    ConnectSmtpRequest,
    UpdateMailboxRequest,
)
from app.api.v1.response.mailbox_response import MailboxResponse
from app.common.billing.plan_enforcement import PlanEnforcer
from app.common.enum.email import MailboxProvider, MailboxStatus
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.mailbox_repository import MailboxRepository
from app.db.repository.organization_repository import OrganizationRepository
from app.model.mailbox_model import Mailbox
from app.settings import settings

logger = logging.getLogger(__name__)


class MailboxService:
    """Service for managing connected email mailboxes."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MailboxRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.enforcer = PlanEnforcer(db)

    async def _check_mailbox_limit(self, org_id: str | None, project_id: str | None) -> None:
        if org_id and project_id:
            org = await self.org_repo.get_by_id(org_id)
            plan = org.plan if org else "free"
            await self.enforcer.check_mailboxes(plan, project_id)

    async def connect_gmail(
        self, data: ConnectGmailRequest, owner_id: str, actor_id: str | None = None,
        project_id: str | None = None, org_id: str | None = None,
    ) -> MailboxResponse:
        """Exchange a Gmail OAuth authorization code for tokens and create a mailbox."""
        await self._check_mailbox_limit(org_id, project_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": data.auth_code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            tokens = resp.json()

            # Get the user's email address
            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        email_address = profile.get("email", "")
        existing = await self.repo.get_by_email(email_address)
        if existing:
            raise DuplicateEntityError("Mailbox", "email_address", email_address)

        expires_at = None
        if "expires_in" in tokens:
            expires_at = datetime.now(timezone.utc)

        mailbox = Mailbox(
            owner_id=owner_id,
            project_id=project_id,
            provider=MailboxProvider.GMAIL.value,
            email_address=email_address,
            display_name=data.display_name or profile.get("name", ""),
            status=MailboxStatus.CONNECTED.value,
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            token_expires_at=expires_at,
            created_by=actor_id,
            updated_by=actor_id,
        )
        mailbox = await self.repo.create(mailbox)
        return MailboxResponse.model_validate(mailbox)

    async def connect_outlook(
        self, data: ConnectOutlookRequest, owner_id: str, actor_id: str | None = None,
        project_id: str | None = None, org_id: str | None = None,
    ) -> MailboxResponse:
        """Exchange an Outlook OAuth authorization code for tokens and create a mailbox."""
        await self._check_mailbox_limit(org_id, project_id)
        tenant = settings.ms_tenant_id or "common"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "code": data.auth_code,
                    "client_id": settings.ms_client_id,
                    "client_secret": settings.ms_client_secret,
                    "redirect_uri": settings.ms_redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "https://graph.microsoft.com/Mail.Send offline_access",
                },
            )
            resp.raise_for_status()
            tokens = resp.json()

            profile_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()

        email_address = profile.get("mail") or profile.get("userPrincipalName", "")
        existing = await self.repo.get_by_email(email_address)
        if existing:
            raise DuplicateEntityError("Mailbox", "email_address", email_address)

        mailbox = Mailbox(
            owner_id=owner_id,
            project_id=project_id,
            provider=MailboxProvider.OUTLOOK.value,
            email_address=email_address,
            display_name=data.display_name or profile.get("displayName", ""),
            status=MailboxStatus.CONNECTED.value,
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            created_by=actor_id,
            updated_by=actor_id,
        )
        mailbox = await self.repo.create(mailbox)
        return MailboxResponse.model_validate(mailbox)

    async def connect_smtp(
        self, data: ConnectSmtpRequest, owner_id: str, actor_id: str | None = None,
        project_id: str | None = None, org_id: str | None = None,
    ) -> MailboxResponse:
        """Create a mailbox with SMTP credentials."""
        await self._check_mailbox_limit(org_id, project_id)
        existing = await self.repo.get_by_email(data.email_address)
        if existing:
            raise DuplicateEntityError("Mailbox", "email_address", data.email_address)

        mailbox = Mailbox(
            owner_id=owner_id,
            project_id=project_id,
            provider=MailboxProvider.SMTP.value,
            email_address=data.email_address,
            display_name=data.display_name,
            status=MailboxStatus.CONNECTED.value,
            smtp_host=data.smtp_host,
            smtp_port=data.smtp_port,
            smtp_username=data.smtp_username,
            smtp_password=data.smtp_password,
            smtp_use_tls=data.smtp_use_tls,
            created_by=actor_id,
            updated_by=actor_id,
        )
        mailbox = await self.repo.create(mailbox)
        return MailboxResponse.model_validate(mailbox)

    async def connect_ses(
        self, data: ConnectSesRequest, owner_id: str, actor_id: str | None = None,
        project_id: str | None = None, org_id: str | None = None,
    ) -> MailboxResponse:
        """Create a mailbox backed by AWS SES."""
        await self._check_mailbox_limit(org_id, project_id)
        existing = await self.repo.get_by_email(data.email_address)
        if existing:
            raise DuplicateEntityError("Mailbox", "email_address", data.email_address)

        mailbox = Mailbox(
            owner_id=owner_id,
            project_id=project_id,
            provider=MailboxProvider.SES.value,
            email_address=data.email_address,
            display_name=data.display_name,
            status=MailboxStatus.CONNECTED.value,
            created_by=actor_id,
            updated_by=actor_id,
        )
        mailbox = await self.repo.create(mailbox)
        return MailboxResponse.model_validate(mailbox)

    async def get_mailbox(self, mailbox_id: str) -> MailboxResponse:
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", mailbox_id)
        return MailboxResponse.model_validate(mailbox)

    async def list_mailboxes(
        self, owner_id: str, offset: int = 0, limit: int = 20,
        project_id: str | None = None,
    ) -> tuple[list[MailboxResponse], int]:
        if project_id:
            mailboxes, total = await self.repo.list_by_project(project_id, offset, limit)
        else:
            mailboxes, total = await self.repo.list_by_owner(owner_id, offset, limit)
        return [MailboxResponse.model_validate(m) for m in mailboxes], total

    async def update_mailbox(
        self, mailbox_id: str, data: UpdateMailboxRequest, actor_id: str | None = None
    ) -> MailboxResponse:
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", mailbox_id)

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(mailbox, key, value)
        mailbox.updated_by = actor_id
        mailbox.updated_at = datetime.now(timezone.utc)

        mailbox = await self.repo.update(mailbox)
        return MailboxResponse.model_validate(mailbox)

    async def disconnect(self, mailbox_id: str, actor_id: str | None = None) -> None:
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", mailbox_id)
        await self.repo.soft_delete(mailbox, actor_id)

    async def check_capacity(self, mailbox_id: str) -> int:
        """Return remaining send capacity for today."""
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", mailbox_id)

        # Reset daily counter if needed
        now = datetime.now(timezone.utc)
        if mailbox.sends_today_reset_at and mailbox.sends_today_reset_at.date() < now.date():
            mailbox.sends_today = 0
            mailbox.sends_today_reset_at = now
            await self.repo.update(mailbox)

        effective_limit = mailbox.daily_send_limit
        if mailbox.warmup_enabled and mailbox.warmup_current_limit:
            effective_limit = min(effective_limit, mailbox.warmup_current_limit)

        return max(0, effective_limit - mailbox.sends_today)

    async def increment_send_count(self, mailbox_id: str) -> None:
        """Increment the daily send counter for a mailbox."""
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            return
        mailbox.sends_today += 1
        await self.repo.update(mailbox)

    async def refresh_token(self, mailbox: Mailbox) -> str | None:
        """Refresh OAuth token for Gmail or Outlook mailbox. Returns new access token."""
        if mailbox.provider == MailboxProvider.GMAIL.value and mailbox.refresh_token:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "refresh_token": mailbox.refresh_token,
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "grant_type": "refresh_token",
                    },
                )
                if resp.status_code == 200:
                    tokens = resp.json()
                    mailbox.access_token = tokens["access_token"]
                    await self.repo.update(mailbox)
                    return tokens["access_token"]

        elif mailbox.provider == MailboxProvider.OUTLOOK.value and mailbox.refresh_token:
            tenant = settings.ms_tenant_id or "common"
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                    data={
                        "refresh_token": mailbox.refresh_token,
                        "client_id": settings.ms_client_id,
                        "client_secret": settings.ms_client_secret,
                        "grant_type": "refresh_token",
                        "scope": "https://graph.microsoft.com/Mail.Send offline_access",
                    },
                )
                if resp.status_code == 200:
                    tokens = resp.json()
                    mailbox.access_token = tokens["access_token"]
                    mailbox.refresh_token = tokens.get("refresh_token", mailbox.refresh_token)
                    await self.repo.update(mailbox)
                    return tokens["access_token"]

        return None

    async def test_connection(self, mailbox_id: str) -> dict:
        """Test if the mailbox can send emails."""
        mailbox = await self.repo.get_by_id(mailbox_id)
        if not mailbox:
            raise EntityNotFoundError("Mailbox", mailbox_id)

        if mailbox.provider == MailboxProvider.SMTP.value:
            try:
                import aiosmtplib

                smtp = aiosmtplib.SMTP(
                    hostname=mailbox.smtp_host,
                    port=mailbox.smtp_port,
                    use_tls=mailbox.smtp_use_tls,
                )
                await smtp.connect()
                await smtp.login(mailbox.smtp_username, mailbox.smtp_password)
                await smtp.quit()
                return {"success": True, "message": "SMTP connection successful"}
            except Exception as e:
                return {"success": False, "message": str(e)}

        elif mailbox.provider == MailboxProvider.GMAIL.value:
            token = await self.refresh_token(mailbox)
            if token:
                return {"success": True, "message": "Gmail OAuth token valid"}
            return {"success": False, "message": "Failed to refresh Gmail token"}

        elif mailbox.provider == MailboxProvider.OUTLOOK.value:
            token = await self.refresh_token(mailbox)
            if token:
                return {"success": True, "message": "Outlook OAuth token valid"}
            return {"success": False, "message": "Failed to refresh Outlook token"}

        elif mailbox.provider == MailboxProvider.SES.value:
            try:
                import aioboto3

                session = aioboto3.Session()
                async with session.client("ses", region_name=settings.cognito_region) as ses:
                    resp = await ses.get_identity_verification_attributes(
                        Identities=[mailbox.email_address]
                    )
                    attrs = resp.get("VerificationAttributes", {})
                    identity = attrs.get(mailbox.email_address, {})
                    status = identity.get("VerificationStatus", "NotStarted")
                    if status == "Success":
                        return {"success": True, "message": "SES identity verified"}
                    return {
                        "success": False,
                        "message": f"SES identity status: {status}",
                    }
            except Exception as e:
                return {"success": False, "message": str(e)}

        return {"success": False, "message": "Unknown provider"}
