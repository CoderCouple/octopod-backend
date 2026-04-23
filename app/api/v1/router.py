from fastapi import APIRouter

from app.api.v1.controller.developer_profile_api import router as developer_profile_router
from app.api.v1.controller.email_campaign_api import router as email_campaign_router
from app.api.v1.controller.email_enrichment_api import router as email_enrichment_router
from app.api.v1.controller.email_template_api import router as email_template_router
from app.api.v1.controller.health_api import router as health_router
from app.api.v1.controller.ingest_api import router as ingest_router
from app.api.v1.controller.mailbox_api import router as mailbox_router

router = APIRouter(prefix="/v1")

router.include_router(health_router)
router.include_router(developer_profile_router)
router.include_router(ingest_router)
router.include_router(mailbox_router)
router.include_router(email_template_router)
router.include_router(email_campaign_router)
router.include_router(email_enrichment_router)
