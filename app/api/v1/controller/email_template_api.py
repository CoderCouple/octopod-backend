"""Email Template API controller."""

from fastapi import APIRouter, Depends, Query
from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.email_template_request import (
    CreateEmailTemplateRequest,
    PreviewTemplateRequest,
    UpdateEmailTemplateRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.email_template_response import (
    EmailTemplateResponse,
    TemplatePreviewResponse,
)
from app.common.auth.auth import UserContext, get_user_context
from app.common.exceptions import EntityNotFoundError
from app.common.pagination import PaginatedResponse
from app.db.repository.email_template_repository import EmailTemplateRepository
from app.db.session import get_db
from app.model.email_template_model import EmailTemplate as EmailTemplateModel

router = APIRouter(tags=[Tags.EmailTemplate])


def get_repo(db: AsyncSession = Depends(get_db)) -> EmailTemplateRepository:
    return EmailTemplateRepository(db)


@router.post(
    "/email-template", response_model=BaseResponse[EmailTemplateResponse], status_code=201
)
async def create_template(
    body: CreateEmailTemplateRequest,
    ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """Create a new email template."""
    template = EmailTemplateModel(
        owner_id=ctx.actor_id,
        project_id=ctx.project_id,
        name=body.name,
        category=body.category,
        subject=body.subject,
        body_html=body.body_html,
        body_text=body.body_text,
        variables=body.variables or [],
        metadata_=body.metadata or {},
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
    )
    template = await repo.create(template)
    return success_response(
        EmailTemplateResponse.model_validate(template), "Template created", 201
    )


@router.get(
    "/email-template",
    response_model=BaseResponse[PaginatedResponse[EmailTemplateResponse]],
)
async def list_templates(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """List email templates in the current project."""
    if category:
        templates, total = await repo.get_by_category(ctx.actor_id, category, offset, limit)
    else:
        templates, total = await repo.list_by_project(ctx.project_id, offset, limit)
    items = [EmailTemplateResponse.model_validate(t) for t in templates]
    page = PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
    return success_response(page, "Templates fetched")


@router.get("/email-template/{template_id}", response_model=BaseResponse[EmailTemplateResponse])
async def get_template(
    template_id: str,
    _ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """Retrieve a single template."""
    template = await repo.get_by_id(template_id)
    if not template:
        raise EntityNotFoundError("EmailTemplate", template_id)
    return success_response(EmailTemplateResponse.model_validate(template), "Template fetched")


@router.patch(
    "/email-template/{template_id}", response_model=BaseResponse[EmailTemplateResponse]
)
async def update_template(
    template_id: str,
    body: UpdateEmailTemplateRequest,
    ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """Update an email template."""
    from datetime import datetime, timezone

    template = await repo.get_by_id(template_id)
    if not template:
        raise EntityNotFoundError("EmailTemplate", template_id)

    update_data = body.model_dump(exclude_unset=True)
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")
    for key, value in update_data.items():
        setattr(template, key, value)
    template.updated_by = ctx.user_id
    template.updated_at = datetime.now(timezone.utc)
    template = await repo.update(template)
    return success_response(EmailTemplateResponse.model_validate(template), "Template updated")


@router.delete("/email-template/{template_id}", response_model=BaseResponse)
async def delete_template(
    template_id: str,
    ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """Soft-delete a template."""
    template = await repo.get_by_id(template_id)
    if not template:
        raise EntityNotFoundError("EmailTemplate", template_id)
    await repo.soft_delete(template, ctx.user_id)
    return success_response(None, "Template deleted")


@router.post(
    "/email-template/{template_id}/preview",
    response_model=BaseResponse[TemplatePreviewResponse],
)
async def preview_template(
    template_id: str,
    body: PreviewTemplateRequest,
    _ctx: UserContext = Depends(get_user_context),
    repo: EmailTemplateRepository = Depends(get_repo),
):
    """Render a template preview with sample variables."""
    template = await repo.get_by_id(template_id)
    if not template:
        raise EntityNotFoundError("EmailTemplate", template_id)

    rendered_subject = Template(template.subject).render(**body.variables)
    rendered_html = Template(template.body_html).render(**body.variables)
    rendered_text = None
    if template.body_text:
        rendered_text = Template(template.body_text).render(**body.variables)

    preview = TemplatePreviewResponse(
        subject=rendered_subject,
        body_html=rendered_html,
        body_text=rendered_text,
    )
    return success_response(preview, "Template preview rendered")
