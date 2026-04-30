import pytest

from app.api.v1.request.mailbox_request import ConnectSmtpRequest, UpdateMailboxRequest
from app.service.mailbox_service import MailboxService


@pytest.mark.asyncio
async def test_connect_smtp(async_session):
    service = MailboxService(async_session)
    data = ConnectSmtpRequest(
        email_address="test@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="test@example.com",
        smtp_password="pass",
    )
    result = await service.connect_smtp(data, "owner1", "actor1")
    assert result.id.startswith("mbx_")
    assert result.provider == "smtp"
    assert result.email_address == "test@example.com"
    await async_session.commit()


@pytest.mark.asyncio
async def test_connect_smtp_duplicate(async_session):
    service = MailboxService(async_session)
    data = ConnectSmtpRequest(
        email_address="dup@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="dup@example.com",
        smtp_password="pass",
    )
    await service.connect_smtp(data, "owner1")
    await async_session.commit()

    from app.common.exceptions import DuplicateEntityError

    with pytest.raises(DuplicateEntityError):
        await service.connect_smtp(data, "owner1")


@pytest.mark.asyncio
async def test_update_mailbox(async_session):
    service = MailboxService(async_session)
    data = ConnectSmtpRequest(
        email_address="upd@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="upd@example.com",
        smtp_password="pass",
    )
    created = await service.connect_smtp(data, "owner1")
    await async_session.commit()

    update = UpdateMailboxRequest(daily_send_limit=100)
    updated = await service.update_mailbox(created.id, update, "actor1")
    assert updated.daily_send_limit == 100


@pytest.mark.asyncio
async def test_check_capacity(async_session):
    service = MailboxService(async_session)
    data = ConnectSmtpRequest(
        email_address="cap@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="cap@example.com",
        smtp_password="pass",
    )
    created = await service.connect_smtp(data, "owner1")
    await async_session.commit()

    remaining = await service.check_capacity(created.id)
    assert remaining == 35  # default daily_send_limit


@pytest.mark.asyncio
async def test_disconnect(async_session):
    service = MailboxService(async_session)
    data = ConnectSmtpRequest(
        email_address="disc@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="disc@example.com",
        smtp_password="pass",
    )
    created = await service.connect_smtp(data, "owner1")
    await async_session.commit()

    await service.disconnect(created.id, "actor1")
    await async_session.commit()

    from app.common.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        await service.get_mailbox(created.id)
