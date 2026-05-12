"""Plan limit enforcement — checks resource counts against plan limits."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.billing.plan_limits import get_plan_limits
from app.common.exceptions import PlanLimitExceededError
from app.model.developer_profile_model import DeveloperProfile
from app.model.email_campaign_model import EmailCampaign
from app.model.mailbox_model import Mailbox
from app.model.org_membership_model import OrgMembership
from app.model.project_model import Project
from app.settings import settings


class PlanEnforcer:
    """Check resource counts against plan limits for an organization.

    Enforcement is only active when Stripe is configured (stripe_secret_key is set).
    Without Stripe configuration (dev/test), all limits are bypassed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._enabled = bool(settings.stripe_secret_key)

    async def _count(self, model, project_id: str | None = None, org_id: str | None = None):
        """Count non-deleted rows for a resource scoped to project or org."""
        conditions = []
        if project_id and hasattr(model, "project_id"):
            conditions.append(model.project_id == project_id)
        if org_id and hasattr(model, "org_id"):
            conditions.append(model.org_id == org_id)
        if hasattr(model, "is_deleted"):
            conditions.append(model.is_deleted == False)  # noqa: E712
        result = await self.db.execute(select(func.count(model.id)).where(*conditions))
        return result.scalar() or 0

    async def check_mailboxes(self, plan: str, project_id: str) -> None:
        if not self._enabled:
            return
        limits = get_plan_limits(plan)
        count = await self._count(Mailbox, project_id=project_id)
        if count >= limits.mailboxes:
            raise PlanLimitExceededError("mailboxes", count, limits.mailboxes, plan)

    async def check_campaigns(self, plan: str, project_id: str) -> None:
        if not self._enabled:
            return
        limits = get_plan_limits(plan)
        count = await self._count(EmailCampaign, project_id=project_id)
        if count >= limits.campaigns:
            raise PlanLimitExceededError("campaigns", count, limits.campaigns, plan)

    async def check_developer_profiles(self, plan: str, project_id: str) -> None:
        if not self._enabled:
            return
        limits = get_plan_limits(plan)
        count = await self._count(DeveloperProfile, project_id=project_id)
        if count >= limits.developer_profiles:
            raise PlanLimitExceededError(
                "developer_profiles", count, limits.developer_profiles, plan
            )

    async def check_projects(self, plan: str, org_id: str) -> None:
        if not self._enabled:
            return
        limits = get_plan_limits(plan)
        count = await self._count(Project, org_id=org_id)
        if count >= limits.projects:
            raise PlanLimitExceededError("projects", count, limits.projects, plan)

    async def check_org_members(self, plan: str, org_id: str) -> None:
        if not self._enabled:
            return
        limits = get_plan_limits(plan)
        result = await self.db.execute(
            select(func.count(OrgMembership.id)).where(
                OrgMembership.org_id == org_id,
                OrgMembership.status.in_(["active", "invited"]),
            )
        )
        count = result.scalar() or 0
        if count >= limits.org_members:
            raise PlanLimitExceededError("org_members", count, limits.org_members, plan)
