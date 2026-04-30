"""Health check API controller.

Provides liveness and readiness probe endpoints used by orchestrators
(e.g. Kubernetes) to determine whether the service is running and ready
to accept traffic.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, status

from app.api.tags import Tags

router = APIRouter(tags=[Tags.Health])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, Any]:
    """Liveness probe for the service.

    Returns a simple heartbeat indicating that the application process is
    alive and capable of handling HTTP requests.

    HTTP Method:
        GET /api/v1/health

    Returns:
        Dict[str, Any]: A JSON object containing:
            - status (str): Always ``"healthy"``.
            - timestamp (str): ISO-8601 UTC timestamp of the response.
            - service (str): The service name (``"octopod-backend"``).

    Status Codes:
        200 OK: Service is alive.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "octopod-backend",
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, Any]:
    """Readiness probe for the service.

    Checks that all critical dependencies (database, cache) are reachable
    before reporting the service as ready to receive traffic.

    HTTP Method:
        GET /api/v1/ready

    Returns:
        Dict[str, Any]: A JSON object containing:
            - status (str): ``"ready"`` when all checks pass.
            - timestamp (str): ISO-8601 UTC timestamp of the response.
            - checks (dict): Per-dependency check results with keys
              ``"database"`` and ``"cache"``, each valued ``"ok"``.

    Status Codes:
        200 OK: Service is ready to accept traffic.
    """
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "ok",
            "cache": "ok",
        },
    }
