from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints.

    Attributes:
        offset: The number of records to skip.  Must be >= 0.
            Defaults to ``0``.
        limit: The maximum number of records to return.  Must be
            between 1 and 100 inclusive.  Defaults to ``20``.
    """

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated API responses.

    Attributes:
        items: The list of result items for the current page.
        total: The total number of records matching the query across
            all pages.
        offset: The offset that was used for the current page.
        limit: The limit that was used for the current page.
    """

    items: Sequence[T]
    total: int
    offset: int
    limit: int
