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
