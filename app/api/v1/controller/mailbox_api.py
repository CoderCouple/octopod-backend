"""Mailbox API controller.

Endpoints for connecting, managing, and testing email mailboxes.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.mailbox_request import (
    ConnectGmailRequest,
    ConnectOutlookRequest,
    ConnectSesRequest,
    ConnectSmtpRequest,
    UpdateMailboxRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.mailbox_response import MailboxResponse
from app.common.auth.auth import get_actor_id_required
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.mailbox_service import MailboxService

router = APIRouter(tags=[Tags.Mailbox])


def get_mailbox_service(db: AsyncSession = Depends(get_db)) -> MailboxService:
    return MailboxService(db)


@router.post(
    "/mailbox/gmail/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_gmail(
    body: ConnectGmailRequest,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect a Gmail mailbox via OAuth authorization code."""
    owner_id = actor_id
    result = await service.connect_gmail(body, owner_id, actor_id)
    return success_response(result, "Gmail mailbox connected", 201)


@router.post(
    "/mailbox/outlook/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_outlook(
    body: ConnectOutlookRequest,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect an Outlook mailbox via OAuth authorization code."""
    owner_id = actor_id
    result = await service.connect_outlook(body, owner_id, actor_id)
    return success_response(result, "Outlook mailbox connected", 201)


@router.post(
    "/mailbox/smtp/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_smtp(
    body: ConnectSmtpRequest,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect a generic SMTP mailbox."""
    owner_id = actor_id
    result = await service.connect_smtp(body, owner_id, actor_id)
    return success_response(result, "SMTP mailbox connected", 201)


@router.post(
    "/mailbox/ses/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_ses(
    body: ConnectSesRequest,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect an AWS SES mailbox."""
    owner_id = actor_id
    result = await service.connect_ses(body, owner_id, actor_id)
    return success_response(result, "SES mailbox connected", 201)


@router.get("/mailbox", response_model=BaseResponse[PaginatedResponse[MailboxResponse]])
async def list_mailboxes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """List mailboxes for the current user."""
    owner_id = actor_id
    mailboxes, total = await service.list_mailboxes(owner_id, offset, limit)
    page = PaginatedResponse(items=mailboxes, total=total, offset=offset, limit=limit)
    return success_response(page, "Mailboxes fetched")


@router.get("/mailbox/{mailbox_id}", response_model=BaseResponse[MailboxResponse])
async def get_mailbox(
    mailbox_id: str,
    _actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Retrieve a single mailbox."""
    result = await service.get_mailbox(mailbox_id)
    return success_response(result, "Mailbox fetched")


@router.patch("/mailbox/{mailbox_id}", response_model=BaseResponse[MailboxResponse])
async def update_mailbox(
    mailbox_id: str,
    body: UpdateMailboxRequest,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Update mailbox settings."""
    result = await service.update_mailbox(mailbox_id, body, actor_id)
    return success_response(result, "Mailbox updated")


@router.delete("/mailbox/{mailbox_id}", response_model=BaseResponse)
async def disconnect_mailbox(
    mailbox_id: str,
    actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Disconnect (soft-delete) a mailbox."""
    await service.disconnect(mailbox_id, actor_id)
    return success_response(None, "Mailbox disconnected")


@router.post("/mailbox/{mailbox_id}/test", response_model=BaseResponse[dict])
async def test_mailbox(
    mailbox_id: str,
    _actor_id: str = Depends(get_actor_id_required),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Test if a mailbox connection is working."""
    result = await service.test_connection(mailbox_id)
    return success_response(result, "Connection test complete")
