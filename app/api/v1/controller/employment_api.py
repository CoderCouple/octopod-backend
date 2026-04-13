"""Employment API controller.

Exposes endpoints for creating, retrieving, updating, and terminating
employment records.  An employment represents the relationship between an
employee and an organization for a given time period.  Each mutation is
attributed to an authenticated actor and recorded in the event log.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.employment_request import (
    CreateEmploymentRequest,
    UpdateEmploymentRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.employment_response import EmploymentResponse
from app.common.auth.auth import get_actor_id
from app.db.session import get_db
from app.service.employment_service import EmploymentService

router = APIRouter(tags=[Tags.Employment])


def get_employment_service(db: AsyncSession = Depends(get_db)) -> EmploymentService:
    """Construct an ``EmploymentService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        EmploymentService: A new service instance bound to the given session.
    """
    return EmploymentService(db)


@router.post("/employment", response_model=BaseResponse[EmploymentResponse], status_code=201)
async def create_employment(
    body: CreateEmploymentRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: EmploymentService = Depends(get_employment_service),
):
    """Create a new employment record.

    Links an employee to an organization with a start date and optional
    metadata such as title and department.

    HTTP Method:
        POST /api/v1/employment

    Args:
        body: Request payload containing employment details (e.g.
            employee_id, org_id, start_date, title).
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``EmploymentService`` instance.

    Returns:
        BaseResponse[EmploymentResponse]: The newly created employment
        record wrapped in a standard response envelope.

    Side Effects:
        Logs an employment-created event to the event log.

    Status Codes:
        201 Created: Employment successfully created.
        422 Unprocessable Entity: Validation error in request body.
    """
    emp = await service.create_employment(body, actor_id)
    return success_response(emp, "Employment created", 201)


@router.get("/employment/{employment_id}", response_model=BaseResponse[EmploymentResponse])
async def get_employment(
    employment_id: str,
    service: EmploymentService = Depends(get_employment_service),
):
    """Retrieve a single employment record by its ID.

    HTTP Method:
        GET /api/v1/employment/{employment_id}

    Args:
        employment_id: Unique identifier of the employment record.
        service: Injected ``EmploymentService`` instance.

    Returns:
        BaseResponse[EmploymentResponse]: The requested employment record
        wrapped in a standard response envelope.

    Status Codes:
        200 OK: Employment fetched successfully.
        404 Not Found: No employment record exists with the given ID.
    """
    emp = await service.get_employment(employment_id)
    return success_response(emp, "Employment fetched")


@router.patch("/employment/{employment_id}", response_model=BaseResponse[EmploymentResponse])
async def update_employment(
    employment_id: str,
    body: UpdateEmploymentRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: EmploymentService = Depends(get_employment_service),
):
    """Partially update an existing employment record.

    HTTP Method:
        PATCH /api/v1/employment/{employment_id}

    Args:
        employment_id: Unique identifier of the employment record to
            update.
        body: Request payload containing the fields to update.  Only
            supplied fields are modified; omitted fields remain unchanged.
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``EmploymentService`` instance.

    Returns:
        BaseResponse[EmploymentResponse]: The updated employment record
        wrapped in a standard response envelope.

    Side Effects:
        Logs an employment-updated event to the event log.

    Status Codes:
        200 OK: Employment updated successfully.
        404 Not Found: No employment record exists with the given ID.
        422 Unprocessable Entity: Validation error in request body.
    """
    emp = await service.update_employment(employment_id, body, actor_id)
    return success_response(emp, "Employment updated")


@router.post(
    "/employment/{employment_id}/end",
    response_model=BaseResponse[EmploymentResponse],
)
async def end_employment(
    employment_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: EmploymentService = Depends(get_employment_service),
):
    """Terminate an active employment.

    Sets the end date on the employment record, effectively marking it as
    no longer active.

    HTTP Method:
        POST /api/v1/employment/{employment_id}/end

    Args:
        employment_id: Unique identifier of the employment record to
            terminate.
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``EmploymentService`` instance.

    Returns:
        BaseResponse[EmploymentResponse]: The terminated employment record
        wrapped in a standard response envelope.

    Side Effects:
        Logs an employment-ended event to the event log.

    Status Codes:
        200 OK: Employment ended successfully.
        404 Not Found: No employment record exists with the given ID.
    """
    emp = await service.end_employment(employment_id, actor_id)
    return success_response(emp, "Employment ended")
