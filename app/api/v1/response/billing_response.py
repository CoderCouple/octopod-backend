from datetime import datetime

from pydantic import BaseModel


class BillingInfoResponse(BaseModel):
    plan: str
    status: str
    seat_count: int
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class InvoiceResponse(BaseModel):
    id: str
    number: str | None = None
    status: str
    amount_paid: int
    amount_due: int
    currency: str
    created: int
    period_start: int | None = None
    period_end: int | None = None
    hosted_invoice_url: str | None = None
    invoice_pdf: str | None = None


class UsageItemResponse(BaseModel):
    key: str
    label: str
    used: int
    limit: int


class UsageResponse(BaseModel):
    plan: str
    items: list[UsageItemResponse]
