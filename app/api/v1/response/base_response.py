from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Generic envelope schema for all API responses.

    Wraps the actual response payload in a standardized structure that
    includes a status code, human-readable message, and success flag.

    Attributes:
        result: The response payload of type ``T``, or ``None``.
        status_code: The HTTP status code of the response.
        message: An optional human-readable message.
        success: Whether the operation succeeded.
    """

    result: Optional[T] = None
    status_code: int
    message: Optional[str] = None
    success: Optional[bool] = None


def success_response(
    result: T | None = None, message: str = "Success", status_code: int = 200
) -> BaseResponse[T]:
    """Build a standardized success response envelope.

    Args:
        result: The response payload to include (may be ``None``).
        message: A human-readable success message.  Defaults to
            ``"Success"``.
        status_code: The HTTP status code.  Defaults to ``200``.

    Returns:
        A ``BaseResponse`` instance with ``success=True``.
    """
    return BaseResponse(
        result=result,
        status_code=status_code,
        message=message or "Success",
        success=True,
    )


def error_response(
    message: str = "Something went wrong", status_code: int = 500
) -> BaseResponse[None]:
    """Build a standardized error response envelope.

    Args:
        message: A human-readable error message.  Defaults to
            ``"Something went wrong"``.
        status_code: The HTTP status code.  Defaults to ``500``.

    Returns:
        A ``BaseResponse`` instance with ``success=False`` and
        ``result=None``.
    """
    return BaseResponse(
        result=None,
        status_code=status_code,
        message=message or "Something went wrong",
        success=False,
    )
