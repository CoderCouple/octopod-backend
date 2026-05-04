from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from app.common.auth.cognito import get_current_user, get_current_user_optional


class UserContext(BaseModel):
    actor_id: str
    email: str | None = None
    organization_id: str | None = None
    role: str | None = None


async def get_actor_id(
    claims: dict[str, Any] | None = Depends(get_current_user_optional),
) -> str | None:
    """Return the Cognito ``sub`` from a valid JWT, or ``None`` if no token.

    Drop-in replacement for the old X-Actor-Id header approach.
    Same signature (``str | None``) so existing controllers need zero changes.
    """
    if claims is None:
        return None
    return claims.get("sub")


async def get_actor_id_required(
    claims: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Like ``get_actor_id`` but raises 401 if no valid token is present."""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )
    return sub


async def get_user_context(
    claims: dict[str, Any] = Depends(get_current_user),
) -> UserContext:
    """Return a full ``UserContext`` from the JWT claims."""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )
    return UserContext(
        actor_id=sub,
        email=claims.get("email"),
    )
