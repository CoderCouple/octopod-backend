from fastapi import APIRouter

from app.api.v1.controller.claim_api import router as claim_router
from app.api.v1.controller.developer_profile_api import router as developer_profile_router
from app.api.v1.controller.employee_api import router as employee_router
from app.api.v1.controller.employment_api import router as employment_router
from app.api.v1.controller.graph_api import router as graph_router
from app.api.v1.controller.health_api import router as health_router
from app.api.v1.controller.org_api import router as org_router
from app.api.v1.controller.relationship_api import router as relationship_router
from app.api.v1.controller.ingest_api import router as ingest_router
from app.api.v1.controller.timeline_api import router as timeline_router

router = APIRouter(prefix="/v1")

router.include_router(health_router)
router.include_router(org_router)
router.include_router(employee_router)
router.include_router(employment_router)
router.include_router(relationship_router)
router.include_router(claim_router)
router.include_router(graph_router)
router.include_router(timeline_router)
router.include_router(developer_profile_router)
router.include_router(ingest_router)
