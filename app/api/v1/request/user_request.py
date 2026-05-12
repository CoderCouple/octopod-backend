from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=2048)


class SwitchContextRequest(BaseModel):
    organization_id: str | None = None
    project_id: str | None = None


class InviteMemberRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=320)
    role: str = Field(default="member")
