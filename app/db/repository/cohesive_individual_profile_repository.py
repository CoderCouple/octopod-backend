import logging

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.cohesive_individual_profile_model import CohesiveIndividualProfile

logger = logging.getLogger(__name__)


class CohesiveIndividualProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: str) -> CohesiveIndividualProfile | None:
        result = await self.db.execute(
            select(CohesiveIndividualProfile).where(
                CohesiveIndividualProfile.id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_developer_profile_id(
        self, developer_profile_id: str
    ) -> CohesiveIndividualProfile | None:
        result = await self.db.execute(
            select(CohesiveIndividualProfile).where(
                CohesiveIndividualProfile.developer_profile_id == developer_profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[CohesiveIndividualProfile], int]:
        base = select(CohesiveIndividualProfile)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(base.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def list_by_ids(self, ids: list[str]) -> list[CohesiveIndividualProfile]:
        if not ids:
            return []
        result = await self.db.execute(
            select(CohesiveIndividualProfile).where(
                CohesiveIndividualProfile.id.in_(ids)
            )
        )
        return list(result.scalars().all())

    async def list_by_developer_profile_ids(
        self, developer_profile_ids: list[str]
    ) -> list[CohesiveIndividualProfile]:
        if not developer_profile_ids:
            return []
        result = await self.db.execute(
            select(CohesiveIndividualProfile).where(
                CohesiveIndividualProfile.developer_profile_id.in_(developer_profile_ids)
            )
        )
        return list(result.scalars().all())

    async def create(self, entity: CohesiveIndividualProfile) -> CohesiveIndividualProfile:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: CohesiveIndividualProfile) -> CohesiveIndividualProfile:
        await self.db.flush()
        return entity

    async def keyword_search(
        self,
        query: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[tuple[CohesiveIndividualProfile, float]]:
        tsquery = func.plainto_tsquery("english", query)
        rank = func.ts_rank(CohesiveIndividualProfile.search_tsv, tsquery)

        stmt = (
            select(CohesiveIndividualProfile, rank.label("rank"))
            .where(CohesiveIndividualProfile.search_tsv.op("@@")(tsquery))
        )

        if filters:
            if filters.get("languages"):
                stmt = stmt.where(
                    CohesiveIndividualProfile.languages.op("?|")(
                        text(f"ARRAY{filters['languages']!r}")
                    )
                )
            if filters.get("skills"):
                stmt = stmt.where(
                    CohesiveIndividualProfile.skills.op("?|")(
                        text(f"ARRAY{filters['skills']!r}")
                    )
                )
            if filters.get("min_stars") is not None:
                stmt = stmt.where(
                    CohesiveIndividualProfile.total_stars >= filters["min_stars"]
                )
            if filters.get("min_experience_years") is not None:
                stmt = stmt.where(
                    CohesiveIndividualProfile.years_of_experience
                    >= filters["min_experience_years"]
                )
            if filters.get("min_contributions") is not None:
                stmt = stmt.where(
                    CohesiveIndividualProfile.total_contributions
                    >= filters["min_contributions"]
                )
            if filters.get("min_followers") is not None:
                stmt = stmt.where(
                    CohesiveIndividualProfile.total_followers >= filters["min_followers"]
                )
            if filters.get("location"):
                stmt = stmt.where(
                    func.lower(CohesiveIndividualProfile.location)
                    == filters["location"].lower()
                )
            if filters.get("company"):
                stmt = stmt.where(
                    func.lower(CohesiveIndividualProfile.company)
                    == filters["company"].lower()
                )

        stmt = stmt.order_by(rank.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]
