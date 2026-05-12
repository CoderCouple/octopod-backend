import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.organization_response import OrgMembershipResponse
from app.common.billing.plan_enforcement import PlanEnforcer
from app.common.enum.org import MembershipStatus, OrgRole
from app.db.repository.org_membership_repository import OrgMembershipRepository
from app.db.repository.organization_repository import OrganizationRepository
from app.db.repository.user_repository import UserRepository
from app.model.org_membership_model import OrgMembership
from app.service.billing_service import BillingService

logger = logging.getLogger(__name__)


class OrgMembershipService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.membership_repo = OrgMembershipRepository(db)
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.enforcer = PlanEnforcer(db)
        self.billing_service = BillingService(db)

    async def _get_active_member_count(self, org_id: str) -> int:
        members, total = await self.membership_repo.list_by_org(org_id, 0, 10000)
        return sum(1 for m in members if m.status in ("active", "invited"))

    async def invite_member(
        self, org_id: str, email: str, role: str, invited_by: str
    ) -> OrgMembershipResponse:
        # Plan limit check
        org = await self.org_repo.get_by_id(org_id)
        plan = org.plan if org else "free"
        await self.enforcer.check_org_members(plan, org_id)

        # Check if already invited
        existing = await self.membership_repo.get_by_org_and_email(org_id, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{email}' already invited",
            )

        # Check if user exists and is already a member
        user = await self.user_repo.get_by_email(email)
        if user:
            existing_membership = await self.membership_repo.get(org_id, user.id)
            if existing_membership:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User is already a member of this organization",
                )

        membership = OrgMembership(
            org_id=org_id,
            user_id=user.id if user else None,
            role=role,
            status=MembershipStatus.INVITED.value if not user else MembershipStatus.ACTIVE.value,
            invited_by=invited_by,
            invited_email=email,
        )
        membership = await self.membership_repo.create(membership)

        # Sync seat count with Stripe
        new_count = await self._get_active_member_count(org_id)
        await self.billing_service.sync_seat_count(org_id, new_count)

        return OrgMembershipResponse.model_validate(membership)

    async def list_members(
        self, org_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[OrgMembershipResponse], int]:
        members, total = await self.membership_repo.list_by_org(org_id, offset, limit)
        return [OrgMembershipResponse.model_validate(m) for m in members], total

    async def change_role(
        self, org_id: str, target_user_id: str, new_role: str, actor_role: str
    ) -> OrgMembershipResponse:
        membership = await self.membership_repo.get(org_id, target_user_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found",
            )

        # Admins cannot change/remove owners
        if membership.role == OrgRole.OWNER.value and actor_role != OrgRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify owner membership",
            )

        membership.role = new_role
        membership.updated_at = datetime.now(timezone.utc)
        membership = await self.membership_repo.update(membership)
        return OrgMembershipResponse.model_validate(membership)

    async def remove_member(
        self, org_id: str, target_user_id: str, actor_role: str
    ) -> None:
        membership = await self.membership_repo.get(org_id, target_user_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found",
            )

        if membership.role == OrgRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove organization owner",
            )

        await self.membership_repo.delete(membership)

        # Sync seat count with Stripe
        new_count = await self._get_active_member_count(org_id)
        await self.billing_service.sync_seat_count(org_id, new_count)
