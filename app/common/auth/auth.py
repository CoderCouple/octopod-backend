from typing import Optional

from fastapi import Header
from pydantic import BaseModel


class UserContext(BaseModel):
    """Pydantic schema representing the authenticated user's context.

    Attributes:
        actor_id: The unique identifier of the authenticated actor.
        organization_id: The organization the actor is operating within,
            if applicable.
        role: The actor's role (e.g. ``"admin"``, ``"member"``), if
            applicable.
    """

    actor_id: str
    organization_id: Optional[str] = None
    role: Optional[str] = None


async def get_actor_id(x_actor_id: str | None = Header(default=None)) -> str | None:
    """FastAPI dependency that extracts the actor id from the request.

    Reads the ``X-Actor-Id`` header value.  This is a lightweight
    stand-in for full authentication; in production this would be
    replaced by a JWT or OAuth dependency.

    Args:
        x_actor_id: The value of the ``X-Actor-Id`` HTTP header, or
            ``None`` if the header is absent.

    Returns:
        The actor id string, or ``None`` if no header was provided.
    """
    return x_actor_id
