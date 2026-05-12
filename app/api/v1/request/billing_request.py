from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Target plan: 'pro' or 'enterprise'")
    success_url: str = Field(..., max_length=2048)
    cancel_url: str = Field(..., max_length=2048)


class PortalRequest(BaseModel):
    return_url: str = Field(..., max_length=2048)
