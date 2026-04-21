"""
FastAPI application entry point.

Initializes the Octopod Backend application with CORS middleware,
exception handlers, and API routers. Configures logging based on
the environment settings and provides a lifespan context manager
for startup/shutdown events.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.common.exceptions import register_exception_handlers
from app.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    try:
        from app.db.qdrant_client import ensure_collection

        await ensure_collection()
    except Exception:
        logger.warning("Qdrant collection setup skipped (Qdrant may be unavailable)")

    yield

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


@app.get("/")
async def root():
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
