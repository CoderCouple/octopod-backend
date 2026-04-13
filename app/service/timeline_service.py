"""Service layer for employee timeline and reporting history queries.

Provides business logic for retrieving chronologically ordered career events
and reporting relationship histories for individual employees.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.career_event_model import CareerEvent
from app.model.reporting_relationship_model import ReportingRelationship


class TimelineService:
    """Service for querying employee career timelines and reporting histories.

    Provides paginated access to an employee's career events (joins, leaves,
    promotions, etc.) and their historical reporting relationships, both
    ordered reverse-chronologically.
    """

    def __init__(self, db: AsyncSession):
        """Initialize TimelineService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db

    async def get_employee_timeline(
        self, employee_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """Retrieve the career event timeline for an employee.

        Returns a paginated, reverse-chronologically ordered list of career
        events (e.g., joins, leaves, promotions) for the specified employee.

        Args:
            employee_id: The UUID string of the employee whose timeline
                to retrieve.
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of event dictionaries, total count of events).
            Each dictionary contains id, event_type, effective_at,
            recorded_at, org_id, employment_id, and payload.
        """
        base = select(CareerEvent).where(CareerEvent.employee_id == employee_id)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(CareerEvent.effective_at.desc()).offset(offset).limit(limit)
        )
        events = result.scalars().all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "effective_at": e.effective_at.isoformat() if e.effective_at else None,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
                "org_id": e.org_id,
                "employment_id": e.employment_id,
                "payload": e.payload,
            }
            for e in events
        ], total

    async def get_employee_reporting_history(
        self, employee_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """Retrieve the reporting relationship history for an employee.

        Returns a paginated, reverse-chronologically ordered list of all
        reporting relationships (both current and historical, excluding
        soft-deleted) for the specified employee.

        Args:
            employee_id: The UUID string of the employee whose reporting
                history to retrieve.
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of relationship dictionaries, total count).
            Each dictionary contains id, org_id, manager_employee_id,
            relationship_type, status, confidence_score, valid_from,
            valid_to, and is_current.
        """
        base = select(ReportingRelationship).where(
            ReportingRelationship.employee_id == employee_id,
            ReportingRelationship.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(ReportingRelationship.valid_from.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        rrs = result.scalars().all()
        return [
            {
                "id": rr.id,
                "org_id": rr.org_id,
                "manager_employee_id": rr.manager_employee_id,
                "relationship_type": rr.relationship_type,
                "status": rr.status,
                "confidence_score": str(rr.confidence_score),
                "valid_from": rr.valid_from.isoformat() if rr.valid_from else None,
                "valid_to": rr.valid_to.isoformat() if rr.valid_to else None,
                "is_current": rr.is_current,
            }
            for rr in rrs
        ], total
