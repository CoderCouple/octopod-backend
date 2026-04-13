"""Employee API controller.

Exposes CRUD endpoints for managing employee records and retrieving the
employments associated with a given employee.  Each mutation is attributed
to an authenticated actor and recorded in the event log.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.employee_request import (
    CreateEmployeeRequest,
    UpdateEmployeeRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.employee_response import EmployeeResponse
from app.api.v1.response.employment_response import EmploymentResponse
from app.common.auth.auth import get_actor_id
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.employee_service import EmployeeService
from app.service.employment_service import EmploymentService

router = APIRouter(tags=[Tags.Employee])


def get_employee_service(db: AsyncSession = Depends(get_db)) -> EmployeeService:
    """Construct an ``EmployeeService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        EmployeeService: A new service instance bound to the given session.
    """
    return EmployeeService(db)


def get_employment_service(db: AsyncSession = Depends(get_db)) -> EmploymentService:
    """Construct an ``EmploymentService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into employee-scoped
    route handlers that need to query employment records.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        EmploymentService: A new service instance bound to the given session.
    """
    return EmploymentService(db)


@router.post("/employee", response_model=BaseResponse[EmployeeResponse], status_code=201)
async def create_employee(
    body: CreateEmployeeRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: EmployeeService = Depends(get_employee_service),
):
    """Create a new employee record.

    HTTP Method:
        POST /api/v1/employee

    Args:
        body: Request payload containing employee details (e.g. name,
            email, external identifiers).
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``EmployeeService`` instance.

    Returns:
        BaseResponse[EmployeeResponse]: The newly created employee wrapped
        in a standard response envelope with a success message.

    Side Effects:
        Logs an employee-created event to the event log.

    Status Codes:
        201 Created: Employee successfully created.
        422 Unprocessable Entity: Validation error in request body.
    """
    emp = await service.create_employee(body, actor_id)
    return success_response(emp, "Employee created", 201)


@router.get("/employee", response_model=BaseResponse[PaginatedResponse[EmployeeResponse]])
async def list_employees(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: EmployeeService = Depends(get_employee_service),
):
    """List employees with pagination.

    HTTP Method:
        GET /api/v1/employee

    Args:
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        service: Injected ``EmployeeService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[EmployeeResponse]]: A paginated list
        of employees including ``items``, ``total``, ``offset``, and
        ``limit`` fields.

    Status Codes:
        200 OK: Employees fetched successfully.
    """
    employees, total = await service.list_employees(offset, limit)
    page = PaginatedResponse(items=employees, total=total, offset=offset, limit=limit)
    return success_response(page, "Employees fetched")


@router.get("/employee/{employee_id}", response_model=BaseResponse[EmployeeResponse])
async def get_employee(
    employee_id: str,
    service: EmployeeService = Depends(get_employee_service),
):
    """Retrieve a single employee by their ID.

    HTTP Method:
        GET /api/v1/employee/{employee_id}

    Args:
        employee_id: Unique identifier of the employee.
        service: Injected ``EmployeeService`` instance.

    Returns:
        BaseResponse[EmployeeResponse]: The requested employee wrapped in a
        standard response envelope.

    Status Codes:
        200 OK: Employee fetched successfully.
        404 Not Found: No employee exists with the given ID.
    """
    emp = await service.get_employee(employee_id)
    return success_response(emp, "Employee fetched")


@router.patch("/employee/{employee_id}", response_model=BaseResponse[EmployeeResponse])
async def update_employee(
    employee_id: str,
    body: UpdateEmployeeRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: EmployeeService = Depends(get_employee_service),
):
    """Partially update an existing employee record.

    HTTP Method:
        PATCH /api/v1/employee/{employee_id}

    Args:
        employee_id: Unique identifier of the employee to update.
        body: Request payload containing the fields to update.  Only
            supplied fields are modified; omitted fields remain unchanged.
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``EmployeeService`` instance.

    Returns:
        BaseResponse[EmployeeResponse]: The updated employee wrapped in a
        standard response envelope.

    Side Effects:
        Logs an employee-updated event to the event log.

    Status Codes:
        200 OK: Employee updated successfully.
        404 Not Found: No employee exists with the given ID.
        422 Unprocessable Entity: Validation error in request body.
    """
    emp = await service.update_employee(employee_id, body, actor_id)
    return success_response(emp, "Employee updated")


@router.get(
    "/employee/{employee_id}/employments",
    response_model=BaseResponse[PaginatedResponse[EmploymentResponse]],
)
async def list_employee_employments(
    employee_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    emp_service: EmployeeService = Depends(get_employee_service),
    empl_service: EmploymentService = Depends(get_employment_service),
):
    """List all employments for a specific employee.

    First validates that the employee exists, then retrieves their
    employment records with pagination.

    HTTP Method:
        GET /api/v1/employee/{employee_id}/employments

    Args:
        employee_id: Unique identifier of the employee whose employments
            are to be listed.
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        emp_service: Injected ``EmployeeService`` used to verify the
            employee exists.
        empl_service: Injected ``EmploymentService`` used to fetch
            employment records.

    Returns:
        BaseResponse[PaginatedResponse[EmploymentResponse]]: A paginated
        list of employments including ``items``, ``total``, ``offset``,
        and ``limit`` fields.

    Status Codes:
        200 OK: Employments fetched successfully.
        404 Not Found: No employee exists with the given ID.
    """
    await emp_service.get_employee(employee_id)
    employments, total = await empl_service.list_employments_for_employee(
        employee_id, offset, limit
    )
    page = PaginatedResponse(items=employments, total=total, offset=offset, limit=limit)
    return success_response(page, "Employments fetched")
