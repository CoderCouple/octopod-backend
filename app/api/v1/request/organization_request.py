from pydantic import BaseModel, Field


class CreateOrganizationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
