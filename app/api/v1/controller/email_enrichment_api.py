"""Email Enrichment API controller.

Endpoints for finding email addresses for developer profiles.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, success_response
from app.common.auth.auth import UserContext, get_user_context
from app.db.session import get_db
from app.service.email_enrichment_service import EmailEnrichmentService

router = APIRouter(tags=[Tags.EmailEnrichment])


def get_enrichment_service(db: AsyncSession = Depends(get_db)) -> EmailEnrichmentService:
    return EmailEnrichmentService(db)


class EnrichmentResponse:
    """Simple response for enrichment results."""

    pass


@router.post("/email-enrichment/{profile_id}", response_model=BaseResponse[dict])
async def enrich_profile(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: EmailEnrichmentService = Depends(get_enrichment_service),
):
    """Find email for a single developer profile."""
    result = await service.find_email(profile_id)
    return success_response(
        {
            "developer_profile_id": profile_id,
            "email": result.email,
            "source": result.source,
            "confidence": result.confidence,
            "found": result.found,
        },
        "Enrichment complete",
    )


@router.post("/email-enrichment/batch", response_model=BaseResponse[list[dict]])
async def enrich_batch(
    profile_ids: list[str],
    _ctx: UserContext = Depends(get_user_context),
    service: EmailEnrichmentService = Depends(get_enrichment_service),
):
    """Find emails for multiple developer profiles."""
    results = await service.enrich_batch(profile_ids)
    items = [
        {
            "developer_profile_id": pid,
            "email": r.email,
            "source": r.source,
            "confidence": r.confidence,
            "found": r.found,
        }
        for pid, r in zip(profile_ids, results, strict=False)
    ]
    return success_response(items, "Batch enrichment complete")


@router.get("/email-enrichment/{profile_id}", response_model=BaseResponse[dict])
async def get_enrichment_status(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: EmailEnrichmentService = Depends(get_enrichment_service),
):
    """Check enrichment status for a developer profile."""
    result = await service.find_email(profile_id)
    return success_response(
        {
            "developer_profile_id": profile_id,
            "email": result.email,
            "source": result.source,
            "confidence": result.confidence,
            "found": result.found,
        },
        "Enrichment status fetched",
    )
