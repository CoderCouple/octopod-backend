"""Reporting-relationship API controller.

Exposes read-only endpoints for querying reporting relationships between
employees.  Relationships are created and managed as side effects of
employment and claim operations; this controller only provides retrieval
and filtering capabilities.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.relationship_response import ReportingRelationshipResponse
from app.common.exceptions import EntityNotFoundError
from app.common.pagination import PaginatedResponse
from app.db.repository.reporting_relationship_repository import (
    ReportingRelationshipRepository,
)
from app.db.session import get_db

router = APIRouter(tags=[Tags.Relationship])


def get_relationship_repo(
    db: AsyncSession = Depends(get_db),
) -> ReportingRelationshipRepository:
    """Construct a ``ReportingRelationshipRepository`` with a database session.

    Used as a FastAPI dependency to inject the repository into route
    handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        ReportingRelationshipRepository: A new repository instance bound to
        the given session.
    """
    return ReportingRelationshipRepository(db)


@router.get(
    "/relationship",
    response_model=BaseResponse[PaginatedResponse[ReportingRelationshipResponse]],
)
async def list_relationships(
    org_id: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    manager_employee_id: str | None = Query(default=None),
    is_current: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    repo: ReportingRelationshipRepository = Depends(get_relationship_repo),
):
    """List reporting relationships with optional filters and pagination.

    Supports filtering by organization, employee, manager, and active
    status.  All filter parameters are optional; when omitted the full
    (paginated) set of relationships is returned.

    HTTP Method:
        GET /api/v1/relationship

    Args:
        org_id: Filter by organization ID (optional).
        employee_id: Filter by the subordinate employee ID (optional).
        manager_employee_id: Filter by the manager employee ID (optional).
        is_current: If ``True``, return only active relationships; if
            ``False``, return only ended relationships (optional).
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        repo: Injected ``ReportingRelationshipRepository`` instance.

    Returns:
        BaseResponse[PaginatedResponse[ReportingRelationshipResponse]]:
        A paginated list of reporting relationships including ``items``,
        ``total``, ``offset``, and ``limit`` fields.

    Status Codes:
        200 OK: Relationships fetched successfully.
    """
    relationships, total = await repo.list_filtered(
        org_id=org_id,
        employee_id=employee_id,
        manager_employee_id=manager_employee_id,
        is_current=is_current,
        offset=offset,
        limit=limit,
    )
    items = [ReportingRelationshipResponse.model_validate(r) for r in relationships]
    page = PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
    return success_response(page, "Relationships fetched")


@router.get(
    "/relationship/{relationship_id}",
    response_model=BaseResponse[ReportingRelationshipResponse],
)
async def get_relationship(
    relationship_id: str,
    repo: ReportingRelationshipRepository = Depends(get_relationship_repo),
):
    """Retrieve a single reporting relationship by its ID.

    HTTP Method:
        GET /api/v1/relationship/{relationship_id}

    Args:
        relationship_id: Unique identifier of the reporting relationship.
        repo: Injected ``ReportingRelationshipRepository`` instance.

    Returns:
        BaseResponse[ReportingRelationshipResponse]: The requested
        reporting relationship wrapped in a standard response envelope.

    Raises:
        EntityNotFoundError: If no relationship exists with the given ID.

    Status Codes:
        200 OK: Relationship fetched successfully.
        404 Not Found: No reporting relationship exists with the given ID.
    """
    rr = await repo.get_by_id(relationship_id)
    if not rr:
        raise EntityNotFoundError("ReportingRelationship", relationship_id)
    return success_response(
        ReportingRelationshipResponse.model_validate(rr), "Relationship fetched"
    )
