import uuid
from datetime import datetime, timezone

import pytest

from app.db.repository.email_message_repository import EmailMessageRepository
from app.model.email_message_model import EmailMessage
from app.service.email_tracking_service import EmailTrackingService


async def _create_test_message(session, tracking_id=None):
    """Create a test email message for tracking tests."""
    repo = EmailMessageRepository(session)
    tid = tracking_id or str(uuid.uuid4())
    message = EmailMessage(
        campaign_id="ec_test",
        step_id="cst_test",
        recipient_id="cr_test",
        mailbox_id="mbx_test",
        tracking_id=tid,
        from_email="sender@example.com",
        to_email="recipient@example.com",
        subject="Test",
        body_html="<p>Test</p>",
        status="sent",
        scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        link_map={"link1": "https://example.com"},
    )
    await repo.create(message)
    await session.commit()
    return message, tid


@pytest.mark.asyncio
async def test_record_open(async_session):
    message, tid = await _create_test_message(async_session)
    service = EmailTrackingService(async_session)

    result = await service.record_open(tid, "1.2.3.4", "TestAgent")
    assert result is True

    # Verify open was recorded
    repo = EmailMessageRepository(async_session)
    msg = await repo.get_by_tracking_id(tid)
    assert msg.open_count == 1
    assert msg.opened_at is not None


@pytest.mark.asyncio
async def test_record_open_not_found(async_session):
    service = EmailTrackingService(async_session)
    result = await service.record_open("nonexistent", "1.2.3.4")
    assert result is False


@pytest.mark.asyncio
async def test_record_click(async_session):
    message, tid = await _create_test_message(async_session)
    service = EmailTrackingService(async_session)

    url = await service.record_click(tid, "link1", "1.2.3.4")
    assert url == "https://example.com"

    repo = EmailMessageRepository(async_session)
    msg = await repo.get_by_tracking_id(tid)
    assert msg.click_count == 1


@pytest.mark.asyncio
async def test_record_click_unknown_link(async_session):
    message, tid = await _create_test_message(async_session)
    service = EmailTrackingService(async_session)

    url = await service.record_click(tid, "unknown_link")
    assert url is None


@pytest.mark.asyncio
async def test_process_unsubscribe(async_session):
    message, tid = await _create_test_message(async_session)
    service = EmailTrackingService(async_session)

    result = await service.process_unsubscribe(tid, reason="not interested")
    assert result is True


@pytest.mark.asyncio
async def test_process_unsubscribe_not_found(async_session):
    service = EmailTrackingService(async_session)
    result = await service.process_unsubscribe("nonexistent")
    assert result is False
