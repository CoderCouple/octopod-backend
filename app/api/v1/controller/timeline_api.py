"""Timeline API controller.

Exposes read-only endpoints for retrieving chronological event streams
associated with employees.  This includes the general activity timeline
and the reporting-relationship change history.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, success_response
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.timeline_service import TimelineService

router = APIRouter(tags=[Tags.Timeline])


def get_timeline_service(db: AsyncSession = Depends(get_db)) -> TimelineService:
    """Construct a ``TimelineService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        TimelineService: A new service instance bound to the given session.
    """
    return TimelineService(db)


@router.get(
    "/timeline/employee/{employee_id}",
    response_model=BaseResponse[PaginatedResponse[dict]],
)
async def get_employee_timeline(
    employee_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: TimelineService = Depends(get_timeline_service),
):
    """Retrieve the activity timeline for an employee.

    Returns a chronological list of events related to the specified
    employee, such as employment changes, claim submissions, and
    relationship updates.

    HTTP Method:
        GET /api/v1/timeline/employee/{employee_id}

    Args:
        employee_id: Unique identifier of the employee whose timeline
            is requested.
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        service: Injected ``TimelineService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[dict]]: A paginated list of
        timeline event dictionaries including ``items``, ``total``,
        ``offset``, and ``limit`` fields.

    Status Codes:
        200 OK: Timeline fetched successfully.
        404 Not Found: No employee exists with the given ID.
    """
    events, total = await service.get_employee_timeline(employee_id, offset, limit)
    page = PaginatedResponse(items=events, total=total, offset=offset, limit=limit)
    return success_response(page, "Employee timeline fetched")


@router.get(
    "/timeline/employee/{employee_id}/reporting-history",
    response_model=BaseResponse[PaginatedResponse[dict]],
)
async def get_employee_reporting_history(
    employee_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: TimelineService = Depends(get_timeline_service),
):
    """Retrieve the reporting-relationship change history for an employee.

    Returns a chronological list of events specifically related to changes
    in the employee's reporting relationships (e.g. manager changes,
    new direct reports).

    HTTP Method:
        GET /api/v1/timeline/employee/{employee_id}/reporting-history

    Args:
        employee_id: Unique identifier of the employee whose reporting
            history is requested.
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        service: Injected ``TimelineService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[dict]]: A paginated list of
        reporting-history event dictionaries including ``items``,
        ``total``, ``offset``, and ``limit`` fields.

    Status Codes:
        200 OK: Reporting history fetched successfully.
        404 Not Found: No employee exists with the given ID.
    """
    history, total = await service.get_employee_reporting_history(
        employee_id, offset, limit
    )
    page = PaginatedResponse(items=history, total=total, offset=offset, limit=limit)
    return success_response(page, "Reporting history fetched")
