"""
FastAPI application entry point.

Initializes the Octopod Backend application with CORS middleware,
exception handlers, and API routers. Configures logging based on
the environment settings and provides a lifespan context manager
for startup/shutdown events.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.api.v1.controller.billing_webhook_api import router as stripe_webhook_router
from app.api.v1.controller.email_tracking_api import router as tracking_router
from app.common.exceptions import register_exception_handlers
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    try:
        from app.db.qdrant_client import ensure_collection

        await ensure_collection()
    except Exception:
        logger.warning("Qdrant collection setup skipped (Qdrant may be unavailable)")

    # Recover stale pipeline executions (mark running → paused)
    try:
        import asyncpg

        from app.ingest.pipeline.tracker import PipelineTracker

        pool = await asyncpg.create_pool(settings.asyncpg_dsn, min_size=1, max_size=2)
        try:
            count = await PipelineTracker.mark_stale_running_as_paused(pool)
            if count:
                logger.warning(
                    "Recovered %d stale pipeline execution(s) — marked as paused. "
                    "Resume via POST /api/v1/ingest/pipeline/{id}/resume",
                    count,
                )
        finally:
            await pool.close()
    except Exception:
        logger.warning("Pipeline recovery check skipped (DB may be unavailable)")

    # Ensure OpenSearch index exists
    if settings.opensearch_enabled:
        try:
            from app.db.opensearch_client import ensure_index

            await ensure_index()
        except Exception:
            logger.warning("OpenSearch index setup skipped (OpenSearch may be unavailable)")

    # Start email outreach workers
    try:
        from app.outreach.reply_worker import reply_worker
        from app.outreach.send_worker import send_worker

        await send_worker.start()
        await reply_worker.start()
    except Exception:
        logger.warning("Email outreach workers startup skipped")

    # Start pipeline scheduler
    try:
        from app.ingest.pipeline.scheduler import pipeline_scheduler

        await pipeline_scheduler.start()
    except Exception:
        logger.warning("Pipeline scheduler startup skipped")

    # Pre-warm ML models so the first search request doesn't pay the load cost
    # (reranker is ~2.3 GB and takes 60-90s to download + load on cold start).
    # Runs as a background task so it doesn't block startup health checks.
    # Skip for managed providers (Bedrock) where there's no in-process model.
    if settings.reranker_enabled and settings.reranker_provider == "local":
        try:
            import asyncio

            from app.service.reranking.cross_encoder_reranker import _get_model

            async def _warm_reranker() -> None:
                try:
                    await asyncio.to_thread(_get_model)
                    logger.info("Reranker model pre-warmed: %s", settings.reranker_model)
                except Exception:
                    logger.exception("Reranker pre-warm failed (will load on first request)")

            asyncio.create_task(_warm_reranker())
        except Exception:
            logger.warning("Reranker pre-warm scheduling skipped")

    yield

    # Stop pipeline scheduler
    try:
        from app.ingest.pipeline.scheduler import pipeline_scheduler

        await pipeline_scheduler.stop()
    except Exception:
        pass

    # Stop email outreach workers
    try:
        from app.outreach.reply_worker import reply_worker
        from app.outreach.send_worker import send_worker

        await send_worker.stop()
        await reply_worker.stop()
    except Exception:
        pass

    logger.info("Shutting down application")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description=settings.app_desc,
    debug=settings.debug,
    version=settings.app_version,
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(api_router)

# Tracking routes mounted at root (short URLs, not behind /api/v1)
app.include_router(tracking_router)

# Stripe webhook at root — no JWT auth, uses Stripe signature verification
app.include_router(stripe_webhook_router)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint returning application metadata.

    Returns:
        dict: Application name, environment, and link to API docs.
    """
    return {
        "message": f"Welcome to {settings.app_name}",
        "environment": settings.environment,
        "api_docs": "/docs",
    }
