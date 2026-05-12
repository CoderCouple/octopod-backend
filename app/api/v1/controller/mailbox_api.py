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
from app.common.auth.auth import UserContext, get_user_context
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
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect a Gmail mailbox via OAuth authorization code."""
    result = await service.connect_gmail(
        body, ctx.actor_id, ctx.user_id, project_id=ctx.project_id, org_id=ctx.organization_id
    )
    return success_response(result, "Gmail mailbox connected", 201)


@router.post(
    "/mailbox/outlook/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_outlook(
    body: ConnectOutlookRequest,
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect an Outlook mailbox via OAuth authorization code."""
    result = await service.connect_outlook(
        body, ctx.actor_id, ctx.user_id, project_id=ctx.project_id, org_id=ctx.organization_id
    )
    return success_response(result, "Outlook mailbox connected", 201)


@router.post(
    "/mailbox/smtp/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_smtp(
    body: ConnectSmtpRequest,
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect a generic SMTP mailbox."""
    result = await service.connect_smtp(
        body, ctx.actor_id, ctx.user_id, project_id=ctx.project_id, org_id=ctx.organization_id
    )
    return success_response(result, "SMTP mailbox connected", 201)


@router.post(
    "/mailbox/ses/connect", response_model=BaseResponse[MailboxResponse], status_code=201
)
async def connect_ses(
    body: ConnectSesRequest,
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Connect an AWS SES mailbox."""
    result = await service.connect_ses(
        body, ctx.actor_id, ctx.user_id, project_id=ctx.project_id, org_id=ctx.organization_id
    )
    return success_response(result, "SES mailbox connected", 201)


@router.get("/mailbox", response_model=BaseResponse[PaginatedResponse[MailboxResponse]])
async def list_mailboxes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """List mailboxes for the current project."""
    mailboxes, total = await service.list_mailboxes(
        ctx.actor_id, offset, limit, project_id=ctx.project_id
    )
    page = PaginatedResponse(items=mailboxes, total=total, offset=offset, limit=limit)
    return success_response(page, "Mailboxes fetched")


@router.get("/mailbox/{mailbox_id}", response_model=BaseResponse[MailboxResponse])
async def get_mailbox(
    mailbox_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Retrieve a single mailbox."""
    result = await service.get_mailbox(mailbox_id)
    return success_response(result, "Mailbox fetched")


@router.patch("/mailbox/{mailbox_id}", response_model=BaseResponse[MailboxResponse])
async def update_mailbox(
    mailbox_id: str,
    body: UpdateMailboxRequest,
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Update mailbox settings."""
    result = await service.update_mailbox(mailbox_id, body, ctx.user_id)
    return success_response(result, "Mailbox updated")


@router.delete("/mailbox/{mailbox_id}", response_model=BaseResponse)
async def disconnect_mailbox(
    mailbox_id: str,
    ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Disconnect (soft-delete) a mailbox."""
    await service.disconnect(mailbox_id, ctx.user_id)
    return success_response(None, "Mailbox disconnected")


@router.post("/mailbox/{mailbox_id}/test", response_model=BaseResponse[dict])
async def test_mailbox(
    mailbox_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: MailboxService = Depends(get_mailbox_service),
):
    """Test if a mailbox connection is working."""
    result = await service.test_connection(mailbox_id)
    return success_response(result, "Connection test complete")
