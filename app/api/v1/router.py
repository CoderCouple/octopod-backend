from fastapi import APIRouter

from app.api.v1.controller.billing_api import router as billing_router
from app.api.v1.controller.developer_profile_api import router as developer_profile_router
from app.api.v1.controller.email_campaign_api import router as email_campaign_router
from app.api.v1.controller.email_enrichment_api import router as email_enrichment_router
from app.api.v1.controller.email_template_api import router as email_template_router
from app.api.v1.controller.health_api import router as health_router
from app.api.v1.controller.ingest_identity_api import router as ingest_identity_router
from app.api.v1.controller.ingest_job_api import router as ingest_job_router
from app.api.v1.controller.ingest_pipeline_api import router as ingest_pipeline_router
from app.api.v1.controller.ingest_schedule_api import router as ingest_schedule_router
from app.api.v1.controller.ingest_source_api import router as ingest_source_router
from app.api.v1.controller.mailbox_api import router as mailbox_router
from app.api.v1.controller.organization_api import router as organization_router
from app.api.v1.controller.project_api import router as project_router
from app.api.v1.controller.user_api import router as user_router

router = APIRouter(prefix="/v1")

router.include_router(health_router)
router.include_router(user_router)
router.include_router(organization_router)
router.include_router(project_router)
router.include_router(developer_profile_router)
router.include_router(ingest_source_router)
router.include_router(ingest_job_router)
router.include_router(ingest_pipeline_router)
router.include_router(ingest_schedule_router)
router.include_router(ingest_identity_router)
router.include_router(mailbox_router)
router.include_router(email_template_router)
router.include_router(email_campaign_router)
router.include_router(email_enrichment_router)
router.include_router(billing_router)
