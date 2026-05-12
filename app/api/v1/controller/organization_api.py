"""Organization API controller."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.organization_request import (
    CreateOrganizationRequest,
    UpdateOrganizationRequest,
)
from app.api.v1.request.user_request import InviteMemberRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.organization_response import (
    OrganizationResponse,
    OrgMembershipResponse,
)
from app.common.auth.auth import UserContext, get_user_context, require_role
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.org_membership_service import OrgMembershipService
from app.service.organization_service import OrganizationService

router = APIRouter(tags=[Tags.Organization])


def get_org_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)


def get_membership_service(db: AsyncSession = Depends(get_db)) -> OrgMembershipService:
    return OrgMembershipService(db)


@router.post("/organization", response_model=BaseResponse[OrganizationResponse], status_code=201)
async def create_organization(
    body: CreateOrganizationRequest,
    ctx: UserContext = Depends(get_user_context),
    service: OrganizationService = Depends(get_org_service),
):
    """Create a new organization. The creator becomes the owner."""
    result = await service.create_org(body.name, ctx.user_id, body.slug)
    return success_response(result, "Organization created", 201)


@router.get(
    "/organization",
    response_model=BaseResponse[PaginatedResponse[OrganizationResponse]],
)
async def list_organizations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: UserContext = Depends(get_user_context),
    service: OrganizationService = Depends(get_org_service),
):
    """List organizations the current user belongs to."""
    orgs, total = await service.list_user_orgs(ctx.user_id, offset, limit)
    page = PaginatedResponse(items=orgs, total=total, offset=offset, limit=limit)
    return success_response(page, "Organizations fetched")


@router.get("/organization/{org_id}", response_model=BaseResponse[OrganizationResponse])
async def get_organization(
    org_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: OrganizationService = Depends(get_org_service),
):
    """Get organization details. Requires membership."""
    result = await service.get_org(org_id)
    return success_response(result, "Organization fetched")


@router.patch("/organization/{org_id}", response_model=BaseResponse[OrganizationResponse])
async def update_organization(
    org_id: str,
    body: UpdateOrganizationRequest,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: OrganizationService = Depends(get_org_service),
):
    """Update organization settings. Requires admin or owner role."""
    result = await service.update_org(
        org_id, name=body.name, logo_url=body.logo_url, actor_id=ctx.user_id
    )
    return success_response(result, "Organization updated")


@router.delete("/organization/{org_id}", response_model=BaseResponse)
async def delete_organization(
    org_id: str,
    ctx: UserContext = Depends(require_role("owner")),
    service: OrganizationService = Depends(get_org_service),
):
    """Soft-delete an organization. Requires owner role."""
    await service.delete_org(org_id, ctx.user_id)
    return success_response(None, "Organization deleted")


# ── Members ───────────────────────────────────────────────────────


@router.post(
    "/organization/{org_id}/members/invite",
    response_model=BaseResponse[OrgMembershipResponse],
    status_code=201,
)
async def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: OrgMembershipService = Depends(get_membership_service),
):
    """Invite a user to the organization by email."""
    result = await service.invite_member(org_id, body.email, body.role, ctx.user_id)
    return success_response(result, "Member invited", 201)


@router.get(
    "/organization/{org_id}/members",
    response_model=BaseResponse[PaginatedResponse[OrgMembershipResponse]],
)
async def list_members(
    org_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _ctx: UserContext = Depends(get_user_context),
    service: OrgMembershipService = Depends(get_membership_service),
):
    """List members of an organization."""
    members, total = await service.list_members(org_id, offset, limit)
    page = PaginatedResponse(items=members, total=total, offset=offset, limit=limit)
    return success_response(page, "Members fetched")


@router.patch(
    "/organization/{org_id}/members/{user_id}",
    response_model=BaseResponse[OrgMembershipResponse],
)
async def change_member_role(
    org_id: str,
    user_id: str,
    body: InviteMemberRequest,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: OrgMembershipService = Depends(get_membership_service),
):
    """Change a member's role. Admins cannot modify owners."""
    result = await service.change_role(org_id, user_id, body.role, ctx.role)
    return success_response(result, "Member role updated")


@router.delete("/organization/{org_id}/members/{user_id}", response_model=BaseResponse)
async def remove_member(
    org_id: str,
    user_id: str,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: OrgMembershipService = Depends(get_membership_service),
):
    """Remove a member from the organization. Cannot remove the owner."""
    await service.remove_member(org_id, user_id, ctx.role)
    return success_response(None, "Member removed")
