from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cognito_sub: str
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    default_org_id: str | None = None
    default_project_id: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserContextResponse(BaseModel):
    user: UserResponse
    organization_id: str
    project_id: str
    role: str
