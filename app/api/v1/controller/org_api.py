"""Organization API controller.

Exposes CRUD endpoints for managing organizations within the Octopod
platform.  Each mutation is attributed to an authenticated actor and
recorded in the event log.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.org_request import CreateOrgRequest, UpdateOrgRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.org_response import OrgResponse
from app.common.auth.auth import get_actor_id
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.org_service import OrgService

router = APIRouter(tags=[Tags.Organization])


def get_org_service(db: AsyncSession = Depends(get_db)) -> OrgService:
    """Construct an ``OrgService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        OrgService: A new service instance bound to the given session.
    """
    return OrgService(db)


@router.post("/org", response_model=BaseResponse[OrgResponse], status_code=201)
async def create_org(
    body: CreateOrgRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: OrgService = Depends(get_org_service),
):
    """Create a new organization.

    HTTP Method:
        POST /api/v1/org

    Args:
        body: Request payload containing the organization details
            (e.g. name, display name, metadata).
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``OrgService`` instance.

    Returns:
        BaseResponse[OrgResponse]: The newly created organization wrapped
        in a standard response envelope with a success message.

    Side Effects:
        Logs an organization-created event to the event log.

    Status Codes:
        201 Created: Organization successfully created.
        422 Unprocessable Entity: Validation error in request body.
    """
    org = await service.create_org(body, actor_id)
    return success_response(org, "Organization created", 201)


@router.get("/org", response_model=BaseResponse[PaginatedResponse[OrgResponse]])
async def list_orgs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: OrgService = Depends(get_org_service),
):
    """List organizations with pagination.

    HTTP Method:
        GET /api/v1/org

    Args:
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        service: Injected ``OrgService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[OrgResponse]]: A paginated list of
        organizations including ``items``, ``total``, ``offset``, and
        ``limit`` fields.

    Status Codes:
        200 OK: Organizations fetched successfully.
    """
    orgs, total = await service.list_orgs(offset, limit)
    page = PaginatedResponse(items=orgs, total=total, offset=offset, limit=limit)
    return success_response(page, "Organizations fetched")


@router.get("/org/{org_id}", response_model=BaseResponse[OrgResponse])
async def get_org(
    org_id: str,
    service: OrgService = Depends(get_org_service),
):
    """Retrieve a single organization by its ID.

    HTTP Method:
        GET /api/v1/org/{org_id}

    Args:
        org_id: Unique identifier of the organization.
        service: Injected ``OrgService`` instance.

    Returns:
        BaseResponse[OrgResponse]: The requested organization wrapped in a
        standard response envelope.

    Status Codes:
        200 OK: Organization fetched successfully.
        404 Not Found: No organization exists with the given ID.
    """
    org = await service.get_org(org_id)
    return success_response(org, "Organization fetched")


@router.patch("/org/{org_id}", response_model=BaseResponse[OrgResponse])
async def update_org(
    org_id: str,
    body: UpdateOrgRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: OrgService = Depends(get_org_service),
):
    """Partially update an existing organization.

    HTTP Method:
        PATCH /api/v1/org/{org_id}

    Args:
        org_id: Unique identifier of the organization to update.
        body: Request payload containing the fields to update.  Only
            supplied fields are modified; omitted fields remain unchanged.
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``OrgService`` instance.

    Returns:
        BaseResponse[OrgResponse]: The updated organization wrapped in a
        standard response envelope.

    Side Effects:
        Logs an organization-updated event to the event log.

    Status Codes:
        200 OK: Organization updated successfully.
        404 Not Found: No organization exists with the given ID.
        422 Unprocessable Entity: Validation error in request body.
    """
    org = await service.update_org(org_id, body, actor_id)
    return success_response(org, "Organization updated")


@router.delete("/org/{org_id}", response_model=BaseResponse)
async def delete_org(
    org_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: OrgService = Depends(get_org_service),
):
    """Delete an organization.

    HTTP Method:
        DELETE /api/v1/org/{org_id}

    Args:
        org_id: Unique identifier of the organization to delete.
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``OrgService`` instance.

    Returns:
        BaseResponse: A standard response envelope with a success message
        and ``None`` data payload.

    Side Effects:
        Logs an organization-deleted event to the event log.

    Status Codes:
        200 OK: Organization deleted successfully.
        404 Not Found: No organization exists with the given ID.
    """
    await service.delete_org(org_id, actor_id)
    return success_response(None, "Organization deleted")
