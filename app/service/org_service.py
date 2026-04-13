"""Service layer for organization CRUD operations.

Provides business logic for creating, reading, updating, and deleting
organizations. All mutating operations are recorded in the event log
for audit purposes.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.org_request import CreateOrgRequest, UpdateOrgRequest
from app.api.v1.response.org_response import OrgResponse
from app.common.enum.system import EntityType
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.org_repository import OrgRepository
from app.model.organization_model import Organization
from app.service.event_log_service import EventLogService


class OrgService:
    """Service for managing organization entities.

    Handles the full lifecycle of organizations including creation with
    domain uniqueness validation, retrieval, listing with pagination,
    updates, and soft-deletion. All state changes are persisted to the
    append-only event log.
    """

    def __init__(self, db: AsyncSession):
        """Initialize OrgService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = OrgRepository(db)
        self.event_log = EventLogService(db)

    async def create_org(
        self, data: CreateOrgRequest, actor_id: str | None = None
    ) -> OrgResponse:
        """Create a new organization.

        Validates that the domain (if provided) is not already in use by
        another organization, then persists the new record and logs a
        creation event.

        Args:
            data: The request payload containing organization fields such as
                name, domain, industry, logo_url, and metadata.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An OrgResponse representing the newly created organization.

        Raises:
            DuplicateEntityError: If an organization with the same domain
                already exists.
        """
        if data.domain:
            existing = await self.repo.get_by_domain(data.domain)
            if existing:
                raise DuplicateEntityError("Organization", "domain", data.domain)

        org = Organization(
            name=data.name,
            domain=data.domain,
            industry=data.industry,
            logo_url=data.logo_url,
            metadata_=data.metadata or {},
            created_by=actor_id,
            updated_by=actor_id,
        )
        org = await self.repo.create(org)

        await self.event_log.append_event(
            entity_type=EntityType.ORG,
            entity_id=org.id,
            action="create",
            actor_id=actor_id,
            after_state={"name": org.name, "domain": org.domain},
        )
        return OrgResponse.model_validate(org)

    async def get_org(self, org_id: str) -> OrgResponse:
        """Retrieve a single organization by its unique identifier.

        Args:
            org_id: The UUID string of the organization to retrieve.

        Returns:
            An OrgResponse representing the found organization.

        Raises:
            EntityNotFoundError: If no organization exists with the given ID.
        """
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)
        return OrgResponse.model_validate(org)

    async def list_orgs(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[OrgResponse], int]:
        """List organizations with pagination.

        Args:
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of OrgResponse objects, total count of
            organizations).
        """
        orgs, total = await self.repo.list_all(offset, limit)
        return [OrgResponse.model_validate(o) for o in orgs], total

    async def update_org(
        self, org_id: str, data: UpdateOrgRequest, actor_id: str | None = None
    ) -> OrgResponse:
        """Update an existing organization.

        Applies partial updates from the request payload. If the domain is
        being changed, validates that the new domain is not already in use.
        Logs both the before and after states to the event log.

        Args:
            org_id: The UUID string of the organization to update.
            data: The request payload containing the fields to update. Only
                fields explicitly set in the request will be modified.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An OrgResponse representing the updated organization.

        Raises:
            EntityNotFoundError: If no organization exists with the given ID.
            DuplicateEntityError: If the new domain conflicts with an existing
                organization.
        """
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)

        before = {"name": org.name, "domain": org.domain}

        if data.domain is not None and data.domain != org.domain:
            existing = await self.repo.get_by_domain(data.domain, exclude_id=org_id)
            if existing:
                raise DuplicateEntityError("Organization", "domain", data.domain)

        update_data = data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")
        for key, value in update_data.items():
            setattr(org, key, value)
        org.updated_by = actor_id
        org.updated_at = datetime.now(timezone.utc)

        org = await self.repo.update(org)

        await self.event_log.append_event(
            entity_type=EntityType.ORG,
            entity_id=org.id,
            action="update",
            actor_id=actor_id,
            before_state=before,
            after_state={"name": org.name, "domain": org.domain},
        )
        return OrgResponse.model_validate(org)

    async def delete_org(
        self, org_id: str, actor_id: str | None = None
    ) -> None:
        """Soft-delete an organization.

        Marks the organization as deleted without physically removing the
        record from the database. Logs a delete event to the event log
        before performing the soft-deletion.

        Args:
            org_id: The UUID string of the organization to delete.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            None.

        Raises:
            EntityNotFoundError: If no organization exists with the given ID.
        """
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise EntityNotFoundError("Organization", org_id)

        await self.event_log.append_event(
            entity_type=EntityType.ORG,
            entity_id=org.id,
            action="delete",
            actor_id=actor_id,
            before_state={"name": org.name, "domain": org.domain},
        )
        await self.repo.soft_delete(org, actor_id)
