import pytest

from app.api.v1.request.email_campaign_request import (
    AddRecipientRequest,
    CreateCampaignRequest,
    CreateStepRequest,
)
from app.api.v1.request.mailbox_request import ConnectSmtpRequest
from app.common.exceptions import EntityNotFoundError, InvalidStateTransitionError
from app.service.campaign_service import CampaignService
from app.service.mailbox_service import MailboxService


async def _setup_mailbox(session):
    """Create a test mailbox and return its ID."""
    svc = MailboxService(session)
    data = ConnectSmtpRequest(
        email_address="campaign@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="campaign@example.com",
        smtp_password="pass",
    )
    result = await svc.connect_smtp(data, "owner1")
    await session.commit()
    return result.id


@pytest.mark.asyncio
async def test_create_campaign(async_session):
    mbx_id = await _setup_mailbox(async_session)
    service = CampaignService(async_session)
    data = CreateCampaignRequest(name="Test", mailbox_id=mbx_id)
    result = await service.create_campaign(data, "owner1", "actor1")
    assert result.id.startswith("ec_")
    assert result.status == "draft"


@pytest.mark.asyncio
async def test_campaign_state_machine(async_session):
    mbx_id = await _setup_mailbox(async_session)
    service = CampaignService(async_session)

    campaign = await service.create_campaign(
        CreateCampaignRequest(name="SM", mailbox_id=mbx_id), "owner1"
    )
    await async_session.commit()

    # Cannot pause from draft
    with pytest.raises(InvalidStateTransitionError):
        await service.pause_campaign(campaign.id)

    # Start
    result = await service.start_campaign(campaign.id)
    assert result.status == "active"
    await async_session.commit()

    # Pause
    result = await service.pause_campaign(campaign.id)
    assert result.status == "paused"
    await async_session.commit()

    # Resume
    result = await service.resume_campaign(campaign.id)
    assert result.status == "active"
    await async_session.commit()

    # Cancel
    result = await service.cancel_campaign(campaign.id)
    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_add_step(async_session):
    mbx_id = await _setup_mailbox(async_session)
    service = CampaignService(async_session)

    campaign = await service.create_campaign(
        CreateCampaignRequest(name="Steps", mailbox_id=mbx_id), "owner1"
    )
    await async_session.commit()

    step1 = await service.add_step(
        campaign.id, CreateStepRequest(delay_days=0, subject_override="Hello")
    )
    assert step1.step_order == 1

    step2 = await service.add_step(
        campaign.id, CreateStepRequest(delay_days=3, subject_override="Follow up")
    )
    assert step2.step_order == 2


@pytest.mark.asyncio
async def test_add_recipient(async_session):
    mbx_id = await _setup_mailbox(async_session)
    service = CampaignService(async_session)

    campaign = await service.create_campaign(
        CreateCampaignRequest(name="Recips", mailbox_id=mbx_id), "owner1"
    )
    await async_session.commit()

    recipient = await service.add_recipient(
        campaign.id,
        AddRecipientRequest(email="dev@example.com", first_name="Alice"),
    )
    assert recipient.id.startswith("cr_")
    assert recipient.email == "dev@example.com"


@pytest.mark.asyncio
async def test_analytics(async_session):
    mbx_id = await _setup_mailbox(async_session)
    service = CampaignService(async_session)

    campaign = await service.create_campaign(
        CreateCampaignRequest(name="Analytics", mailbox_id=mbx_id), "owner1"
    )
    await async_session.commit()

    analytics = await service.get_analytics(campaign.id)
    assert analytics.campaign_id == campaign.id
    assert analytics.total_recipients == 0
