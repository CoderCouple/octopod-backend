import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enum.org import MembershipStatus, OrgRole
from app.db.repository.org_membership_repository import OrgMembershipRepository
from app.db.repository.organization_repository import OrganizationRepository
from app.db.repository.project_repository import ProjectRepository
from app.db.repository.user_repository import UserRepository
from app.model.org_membership_model import OrgMembership
from app.model.organization_model import Organization
from app.model.project_model import Project
from app.model.user_model import User
from app.service.billing_service import BillingService

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.membership_repo = OrgMembershipRepository(db)
        self.project_repo = ProjectRepository(db)
        self.billing_service = BillingService(db)

    async def get_or_create_user(self, cognito_sub: str, email: str | None = None) -> User:
        """Lookup user by cognito_sub. Auto-provision on first login."""
        user = await self.user_repo.get_by_cognito_sub(cognito_sub)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await self.user_repo.update(user)
            return user

        return await self._auto_provision(cognito_sub, email)

    async def _auto_provision(self, cognito_sub: str, email: str | None) -> User:
        """Create user + personal org + default project + owner membership."""
        logger.info("Auto-provisioning user for sub=%s email=%s", cognito_sub, email)

        # 1. Create user
        user = User(
            cognito_sub=cognito_sub,
            email=email,
            display_name=email.split("@")[0] if email else None,
            last_login_at=datetime.now(timezone.utc),
        )
        user = await self.user_repo.create(user)

        # 2. Create personal org
        org_name = "Personal"
        org_slug = _slugify(f"personal-{user.id[-8:]}")
        org = Organization(
            name=org_name,
            slug=org_slug,
            plan="free",
            created_by=user.id,
            updated_by=user.id,
        )
        org = await self.org_repo.create(org)

        # 3. Create owner membership
        membership = OrgMembership(
            org_id=org.id,
            user_id=user.id,
            role=OrgRole.OWNER.value,
            status=MembershipStatus.ACTIVE.value,
        )
        await self.membership_repo.create(membership)

        # 4. Create default project
        project = Project(
            org_id=org.id,
            name="Default",
            slug="default",
            created_by=user.id,
            updated_by=user.id,
        )
        project = await self.project_repo.create(project)

        # 5. Create Stripe customer for the org
        try:
            await self.billing_service.ensure_stripe_customer(org.id, org.name, email)
        except Exception:
            logger.warning("Stripe customer creation skipped for org=%s", org.id)

        # 6. Set defaults
        user.default_org_id = org.id
        user.default_project_id = project.id
        await self.user_repo.update(user)

        logger.info(
            "Auto-provisioned user=%s org=%s project=%s", user.id, org.id, project.id
        )
        return user

    async def get_user(self, user_id: str) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    async def update_profile(
        self, user_id: str, display_name: str | None = None, avatar_url: str | None = None
    ) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            from app.common.exceptions import EntityNotFoundError

            raise EntityNotFoundError("User", user_id)

        if display_name is not None:
            user.display_name = display_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        user.updated_at = datetime.now(timezone.utc)
        return await self.user_repo.update(user)

    async def switch_context(
        self, user_id: str, org_id: str | None = None, project_id: str | None = None
    ) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            from app.common.exceptions import EntityNotFoundError

            raise EntityNotFoundError("User", user_id)

        if org_id is not None:
            user.default_org_id = org_id
        if project_id is not None:
            user.default_project_id = project_id
        user.updated_at = datetime.now(timezone.utc)
        return await self.user_repo.update(user)
