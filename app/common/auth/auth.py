import logging
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth.cognito import get_current_user, get_current_user_optional
from app.db.session import get_db

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    actor_id: str  # Cognito sub (backward compat)
    user_id: str  # Internal usr_ id
    email: str | None = None
    organization_id: str  # Active org
    project_id: str  # Active project
    role: str  # Role in active org


async def get_actor_id(
    claims: dict[str, Any] | None = Depends(get_current_user_optional),
) -> str | None:
    """Return the Cognito ``sub`` from a valid JWT, or ``None`` if no token."""
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
    db: AsyncSession = Depends(get_db),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
    x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
) -> UserContext:
    """Return a full ``UserContext`` from JWT claims + DB lookup.

    Auto-provisions user, org, project, and membership on first login.
    Resolves active org/project from headers or user defaults.
    """
    from app.db.repository.org_membership_repository import OrgMembershipRepository
    from app.db.repository.project_repository import ProjectRepository
    from app.service.user_service import UserService

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )
    email = claims.get("email")

    user_service = UserService(db)
    user = await user_service.get_or_create_user(sub, email)

    # Resolve org
    org_id = x_org_id or user.default_org_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization context. Set X-Org-Id header or default org.",
        )

    # Verify membership
    membership_repo = OrgMembershipRepository(db)
    membership = await membership_repo.get(org_id, user.id)
    if not membership or membership.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    # Resolve project
    project_id = x_project_id or user.default_project_id
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No project context. Set X-Project-Id header or default project.",
        )

    # Verify project belongs to org
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project or project.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project does not belong to this organization",
        )

    return UserContext(
        actor_id=sub,
        user_id=user.id,
        email=email,
        organization_id=org_id,
        project_id=project_id,
        role=membership.role,
    )


def require_role(*roles: str):
    """Dependency factory that checks the user has one of the specified roles."""

    async def _check(ctx: UserContext = Depends(get_user_context)) -> UserContext:
        if ctx.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return ctx

    return _check
