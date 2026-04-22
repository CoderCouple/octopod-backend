"""Email Campaign API controller.

CRUD for campaigns, steps, recipients; state transitions; analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.email_campaign_request import (
    AddRecipientRequest,
    AddRecipientsFromSearchRequest,
    CreateCampaignRequest,
    CreateStepRequest,
    UpdateCampaignRequest,
    UpdateStepRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.email_campaign_response import (
    CampaignAnalyticsResponse,
    CampaignRecipientResponse,
    CampaignStepResponse,
    EmailCampaignResponse,
    EmailMessageResponse,
)
from app.common.auth.auth import get_actor_id
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.campaign_service import CampaignService

router = APIRouter(tags=[Tags.Campaign])


def get_campaign_service(db: AsyncSession = Depends(get_db)) -> CampaignService:
    return CampaignService(db)


# ── Campaign CRUD ──────────────────────────────────────────────

@router.post(
    "/email-campaign", response_model=BaseResponse[EmailCampaignResponse], status_code=201
)
async def create_campaign(
    body: CreateCampaignRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Create a new email campaign."""
    owner_id = actor_id or "system"
    result = await service.create_campaign(body, owner_id, actor_id)
    return success_response(result, "Campaign created", 201)


@router.get(
    "/email-campaign",
    response_model=BaseResponse[PaginatedResponse[EmailCampaignResponse]],
)
async def list_campaigns(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """List campaigns for the current user."""
    owner_id = actor_id or "system"
    campaigns, total = await service.list_campaigns(owner_id, offset, limit)
    page = PaginatedResponse(items=campaigns, total=total, offset=offset, limit=limit)
    return success_response(page, "Campaigns fetched")


@router.get(
    "/email-campaign/{campaign_id}",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def get_campaign(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service),
):
    """Retrieve a single campaign."""
    result = await service.get_campaign(campaign_id)
    return success_response(result, "Campaign fetched")


@router.patch(
    "/email-campaign/{campaign_id}",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def update_campaign(
    campaign_id: str,
    body: UpdateCampaignRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Update a campaign."""
    result = await service.update_campaign(campaign_id, body, actor_id)
    return success_response(result, "Campaign updated")


@router.delete("/email-campaign/{campaign_id}", response_model=BaseResponse)
async def delete_campaign(
    campaign_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Soft-delete a campaign."""
    await service.delete_campaign(campaign_id, actor_id)
    return success_response(None, "Campaign deleted")


# ── State transitions ──────────────────────────────────────────

@router.post(
    "/email-campaign/{campaign_id}/start",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def start_campaign(
    campaign_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Start a draft campaign."""
    result = await service.start_campaign(campaign_id, actor_id)
    return success_response(result, "Campaign started")


@router.post(
    "/email-campaign/{campaign_id}/pause",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def pause_campaign(
    campaign_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Pause an active campaign."""
    result = await service.pause_campaign(campaign_id, actor_id)
    return success_response(result, "Campaign paused")


@router.post(
    "/email-campaign/{campaign_id}/resume",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def resume_campaign(
    campaign_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Resume a paused campaign."""
    result = await service.resume_campaign(campaign_id, actor_id)
    return success_response(result, "Campaign resumed")


@router.post(
    "/email-campaign/{campaign_id}/cancel",
    response_model=BaseResponse[EmailCampaignResponse],
)
async def cancel_campaign(
    campaign_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Cancel a campaign permanently."""
    result = await service.cancel_campaign(campaign_id, actor_id)
    return success_response(result, "Campaign cancelled")


# ── Steps ──────────────────────────────────────────────────────

@router.post(
    "/email-campaign/{campaign_id}/steps",
    response_model=BaseResponse[CampaignStepResponse],
    status_code=201,
)
async def add_step(
    campaign_id: str,
    body: CreateStepRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Add a step to a campaign sequence."""
    result = await service.add_step(campaign_id, body, actor_id)
    return success_response(result, "Step added", 201)


@router.get(
    "/email-campaign/{campaign_id}/steps",
    response_model=BaseResponse[list[CampaignStepResponse]],
)
async def list_steps(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service),
):
    """List all steps in a campaign."""
    result = await service.list_steps(campaign_id)
    return success_response(result, "Steps fetched")


@router.patch(
    "/email-campaign/steps/{step_id}",
    response_model=BaseResponse[CampaignStepResponse],
)
async def update_step(
    step_id: str,
    body: UpdateStepRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Update a campaign step."""
    result = await service.update_step(step_id, body, actor_id)
    return success_response(result, "Step updated")


@router.delete("/email-campaign/steps/{step_id}", response_model=BaseResponse)
async def delete_step(
    step_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Delete a campaign step."""
    await service.delete_step(step_id, actor_id)
    return success_response(None, "Step deleted")


# ── Recipients ─────────────────────────────────────────────────

@router.post(
    "/email-campaign/{campaign_id}/recipients",
    response_model=BaseResponse[CampaignRecipientResponse],
    status_code=201,
)
async def add_recipient(
    campaign_id: str,
    body: AddRecipientRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Add a recipient to a campaign."""
    result = await service.add_recipient(campaign_id, body, actor_id)
    return success_response(result, "Recipient added", 201)


@router.get(
    "/email-campaign/{campaign_id}/recipients",
    response_model=BaseResponse[PaginatedResponse[CampaignRecipientResponse]],
)
async def list_recipients(
    campaign_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CampaignService = Depends(get_campaign_service),
):
    """List recipients in a campaign."""
    recipients, total = await service.list_recipients(campaign_id, offset, limit)
    page = PaginatedResponse(items=recipients, total=total, offset=offset, limit=limit)
    return success_response(page, "Recipients fetched")


@router.delete(
    "/email-campaign/recipients/{recipient_id}", response_model=BaseResponse
)
async def remove_recipient(
    recipient_id: str,
    actor_id: str | None = Depends(get_actor_id),
    service: CampaignService = Depends(get_campaign_service),
):
    """Remove a recipient from a campaign."""
    await service.remove_recipient(recipient_id, actor_id)
    return success_response(None, "Recipient removed")


@router.post(
    "/email-campaign/{campaign_id}/recipients/from-search",
    response_model=BaseResponse[list[CampaignRecipientResponse]],
)
async def add_recipients_from_search(
    campaign_id: str,
    body: AddRecipientsFromSearchRequest,
    actor_id: str | None = Depends(get_actor_id),
    db: AsyncSession = Depends(get_db),
):
    """Add recipients from developer profile IDs with auto-enrichment."""
    from app.common.enum.email import RecipientStatus
    from app.db.repository.campaign_recipient_repository import CampaignRecipientRepository
    from app.db.repository.email_campaign_repository import EmailCampaignRepository
    from app.model.campaign_recipient_model import CampaignRecipient
    from app.service.email_enrichment_service import EmailEnrichmentService

    campaign_repo = EmailCampaignRepository(db)
    recipient_repo = CampaignRecipientRepository(db)
    enrichment_svc = EmailEnrichmentService(db)

    from app.common.exceptions import EntityNotFoundError

    campaign = await campaign_repo.get_by_id(campaign_id)
    if not campaign:
        raise EntityNotFoundError("Campaign", campaign_id)

    results = []
    for profile_id in body.profile_ids:
        enrichment = await enrichment_svc.find_email(profile_id)
        if not enrichment.found or not enrichment.email:
            continue

        existing = await recipient_repo.get_by_email_and_campaign(
            enrichment.email, campaign_id
        )
        if existing:
            continue

        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            developer_profile_id=profile_id,
            email=enrichment.email,
            email_source=enrichment.source,
            status=RecipientStatus.ACTIVE.value,
            created_by=actor_id,
            updated_by=actor_id,
        )
        recipient = await recipient_repo.create(recipient)
        await campaign_repo.increment_stat(campaign_id, "total_recipients")
        results.append(CampaignRecipientResponse.model_validate(recipient))

    return success_response(results, f"{len(results)} recipients added from search")


# ── Analytics & Messages ───────────────────────────────────────

@router.get(
    "/email-campaign/{campaign_id}/analytics",
    response_model=BaseResponse[CampaignAnalyticsResponse],
)
async def get_campaign_analytics(
    campaign_id: str,
    service: CampaignService = Depends(get_campaign_service),
):
    """Get campaign-level analytics."""
    result = await service.get_analytics(campaign_id)
    return success_response(result, "Analytics fetched")


@router.get(
    "/email-campaign/{campaign_id}/messages",
    response_model=BaseResponse[PaginatedResponse[EmailMessageResponse]],
)
async def list_campaign_messages(
    campaign_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CampaignService = Depends(get_campaign_service),
):
    """List all messages for a campaign."""
    messages, total = await service.list_messages(campaign_id, offset, limit)
    page = PaginatedResponse(items=messages, total=total, offset=offset, limit=limit)
    return success_response(page, "Messages fetched")
