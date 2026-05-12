import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.organization_response import OrganizationResponse
from app.common.enum.org import MembershipStatus, OrgRole
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.org_membership_repository import OrgMembershipRepository
from app.db.repository.organization_repository import OrganizationRepository
from app.db.repository.project_repository import ProjectRepository
from app.model.org_membership_model import OrgMembership
from app.model.organization_model import Organization
from app.model.project_model import Project
from app.service.billing_service import BillingService

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.membership_repo = OrgMembershipRepository(db)
        self.project_repo = ProjectRepository(db)
        self.billing_service = BillingService(db)

    async def create_org(
        self, name: str, user_id: str, slug: str | None = None
    ) -> OrganizationResponse:
        final_slug = slug or _slugify(name)
        existing = await self.org_repo.get_by_slug(final_slug)
        if existing:
            raise DuplicateEntityError("Organization", "slug", final_slug)

        org = Organization(
            name=name,
            slug=final_slug,
            plan="free",
            created_by=user_id,
            updated_by=user_id,
        )
        org = await self.org_repo.create(org)

        # Creator becomes owner
        membership = OrgMembership(
            org_id=org.id,
            user_id=user_id,
            role=OrgRole.OWNER.value,
            status=MembershipStatus.ACTIVE.value,
        )
        await self.membership_repo.create(membership)

        # Create default project
        project = Project(
            org_id=org.id,
            name="Default",
            slug="default",
            created_by=user_id,
            updated_by=user_id,
        )
        await self.project_repo.create(project)

        # Create Stripe customer
        try:
            await self.billing_service.ensure_stripe_customer(org.id, org.name)
        except Exception:
            logger.warning("Stripe customer creation skipped for org=%s", org.id)

        return OrganizationResponse.model_validate(org)

    async def get_org(self, org_id: str) -> OrganizationResponse:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)
        return OrganizationResponse.model_validate(org)

    async def list_user_orgs(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[OrganizationResponse], int]:
        orgs, total = await self.org_repo.list_by_user(user_id, offset, limit)
        return [OrganizationResponse.model_validate(o) for o in orgs], total

    async def update_org(
        self, org_id: str, name: str | None = None, logo_url: str | None = None,
        actor_id: str | None = None,
    ) -> OrganizationResponse:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)

        if name is not None:
            org.name = name
        if logo_url is not None:
            org.logo_url = logo_url
        org.updated_by = actor_id
        org.updated_at = datetime.now(timezone.utc)
        org = await self.org_repo.update(org)
        return OrganizationResponse.model_validate(org)

    async def delete_org(self, org_id: str, actor_id: str | None = None) -> None:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)
        await self.org_repo.soft_delete(org, actor_id)
