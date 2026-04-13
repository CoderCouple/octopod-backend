from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    """Register global HTTP exception handlers on the FastAPI application.

    Wraps all ``HTTPException`` responses in a standardized JSON envelope
    containing ``result``, ``status_code``, ``message``, and ``success``
    fields.

    Args:
        app: The FastAPI application instance to attach handlers to.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "result": None,
                "status_code": exc.status_code,
                "message": exc.detail,
                "success": False,
            },
        )


class EntityNotFoundError(HTTPException):
    """Raised when a requested entity does not exist or has been soft-deleted.

    Returns HTTP 404 Not Found.

    Args:
        entity_type: A human-readable name for the entity kind (e.g.
            ``"Organization"``).
        entity_id: The identifier of the entity that was not found.
    """

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_type} with id '{entity_id}' not found",
        )


class InvalidStateTransitionError(HTTPException):
    """Raised when a state-machine transition is not allowed.

    Returns HTTP 409 Conflict.

    Args:
        current_state: The current state of the entity.
        action: The action that was attempted.
    """

    def __init__(self, current_state: str, action: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot perform '{action}' from state '{current_state}'",
        )


class DuplicateEntityError(HTTPException):
    """Raised when a unique-constraint violation is detected.

    Returns HTTP 409 Conflict.

    Args:
        entity_type: A human-readable name for the entity kind.
        field: The field that has a conflicting value.
        value: The duplicated value.
    """

    def __init__(self, entity_type: str, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{entity_type} with {field} '{value}' already exists",
        )


class CycleDetectedError(HTTPException):
    """Raised when adding a reporting relationship would create a cycle.

    Returns HTTP 422 Unprocessable Entity.

    Args:
        message: A descriptive error message.  Defaults to a generic
            cycle-detection message.
    """

    def __init__(self, message: str = "Adding this relationship would create a cycle"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )


class InsufficientVisibilityError(HTTPException):
    """Raised when the actor lacks the required visibility level.

    Returns HTTP 403 Forbidden.
    """

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient visibility level to access this resource",
        )
