"""Billing API controller — plan info, checkout, and customer portal."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.billing_request import CheckoutRequest, PortalRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.billing_response import (
    BillingInfoResponse,
    CheckoutResponse,
    InvoiceResponse,
    PortalResponse,
    UsageResponse,
)
from app.common.auth.auth import UserContext, get_user_context, require_role
from app.db.session import get_db
from app.service.billing_service import BillingService

router = APIRouter(tags=[Tags.Billing])


def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(db)


@router.get("/billing", response_model=BaseResponse[BillingInfoResponse])
async def get_billing_info(
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: BillingService = Depends(get_billing_service),
):
    """Get current billing and subscription info for the organization."""
    info = await service.get_billing_info(ctx.organization_id)
    result = BillingInfoResponse(**info)
    return success_response(result, "Billing info fetched")


@router.post("/billing/checkout", response_model=BaseResponse[CheckoutResponse], status_code=201)
async def create_checkout(
    body: CheckoutRequest,
    ctx: UserContext = Depends(require_role("owner")),
    service: BillingService = Depends(get_billing_service),
):
    """Create a Stripe Checkout session to upgrade the org's plan."""
    url = await service.create_checkout_session(
        org_id=ctx.organization_id,
        plan=body.plan,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return success_response(CheckoutResponse(checkout_url=url), "Checkout session created", 201)


@router.post("/billing/portal", response_model=BaseResponse[PortalResponse])
async def create_portal(
    body: PortalRequest,
    ctx: UserContext = Depends(require_role("owner")),
    service: BillingService = Depends(get_billing_service),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    url = await service.create_portal_session(
        org_id=ctx.organization_id,
        return_url=body.return_url,
    )
    return success_response(PortalResponse(portal_url=url), "Portal session created")


@router.get("/billing/invoices", response_model=BaseResponse[list[InvoiceResponse]])
async def list_invoices(
    ctx: UserContext = Depends(get_user_context),
    service: BillingService = Depends(get_billing_service),
):
    """List recent Stripe invoices for the organization's subscription."""
    invoices = await service.get_invoices(ctx.organization_id)
    result = [InvoiceResponse(**inv) for inv in invoices]
    return success_response(result, "Invoices fetched")


@router.get("/billing/usage", response_model=BaseResponse[UsageResponse])
async def get_usage(
    ctx: UserContext = Depends(get_user_context),
    service: BillingService = Depends(get_billing_service),
):
    """Return current resource counts vs plan limits for the org."""
    usage = await service.get_usage(ctx.organization_id, ctx.project_id)
    return success_response(UsageResponse(**usage), "Usage fetched")
