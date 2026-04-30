import uuid

import pytest

from app.db.repository.email_message_repository import EmailMessageRepository
from app.model.email_message_model import EmailMessage


async def _seed_message(session, tracking_id):
    """Insert a test email message for tracking endpoint tests."""
    repo = EmailMessageRepository(session)
    message = EmailMessage(
        campaign_id="ec_test",
        step_id="cst_test",
        recipient_id="cr_test",
        mailbox_id="mbx_test",
        tracking_id=tracking_id,
        from_email="sender@example.com",
        to_email="recipient@example.com",
        subject="Test",
        body_html="<p>Test</p>",
        status="sent",
        scheduled_at="2024-01-01T00:00:00Z",
        link_map={"abc123": "https://example.com/page"},
    )
    await repo.create(message)
    await session.commit()


@pytest.mark.asyncio
async def test_open_pixel(async_client, async_engine):
    """Tracking pixel should return a 1x1 GIF."""
    # Note: We don't seed the DB here because the pixel endpoint
    # always returns the GIF regardless of whether the tracking ID exists
    tid = str(uuid.uuid4())
    resp = await async_client.get(f"/t/{tid}.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"
    assert resp.content[:3] == b"GIF"


@pytest.mark.asyncio
async def test_click_redirect_not_found(async_client):
    """Click tracking for unknown tracking ID should 404."""
    resp = await async_client.get("/c/nonexistent/link1", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unsubscribe_not_found(async_client):
    """Unsubscribe for unknown tracking ID should 404."""
    resp = await async_client.get("/unsub/nonexistent")
    assert resp.status_code == 404
