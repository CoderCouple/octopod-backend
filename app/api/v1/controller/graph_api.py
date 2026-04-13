"""Organization graph API controller.

Exposes endpoints for retrieving the reporting-relationship graph of an
organization and for detecting cycles within that graph.  Results can
optionally be filtered based on the authenticated actor's visibility
level.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.response.base_response import BaseResponse, success_response
from app.common.auth.auth import get_actor_id
from app.db.session import get_db
from app.service.graph_service import GraphService
from app.service.visibility_service import VisibilityService

router = APIRouter(tags=[Tags.Graph])


def get_graph_service(db: AsyncSession = Depends(get_db)) -> GraphService:
    """Construct a ``GraphService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        GraphService: A new service instance bound to the given session.
    """
    return GraphService(db)


def get_visibility_service(db: AsyncSession = Depends(get_db)) -> VisibilityService:
    """Construct a ``VisibilityService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers
    that need to apply visibility-based filtering on graph data.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        VisibilityService: A new service instance bound to the given
        session.
    """
    return VisibilityService(db)


@router.get("/graph/org/{org_id}", response_model=BaseResponse[dict])
async def get_org_graph(
    org_id: str,
    include_weak: bool = Query(default=False),
    actor_id: str | None = Depends(get_actor_id),
    graph_svc: GraphService = Depends(get_graph_service),
    vis_svc: VisibilityService = Depends(get_visibility_service),
):
    """Retrieve the reporting-relationship graph for an organization.

    Builds a directed graph of all reporting relationships within the
    specified organization.  When an authenticated actor is present, the
    graph is pruned according to the actor's visibility level so that
    only permitted nodes and edges are returned.

    HTTP Method:
        GET /api/v1/graph/org/{org_id}

    Args:
        org_id: Unique identifier of the organization.
        include_weak: When ``True``, include weak (e.g. dotted-line)
            relationships in addition to strong ones.  Defaults to
            ``False``.
        actor_id: Authenticated user ID extracted from the request.
            When present, triggers visibility-based graph filtering.
        graph_svc: Injected ``GraphService`` instance.
        vis_svc: Injected ``VisibilityService`` instance.

    Returns:
        BaseResponse[dict]: A dictionary representation of the
        organization graph (nodes and edges) wrapped in a standard
        response envelope.

    Status Codes:
        200 OK: Organization graph fetched successfully.
        404 Not Found: No organization exists with the given ID.
    """
    graph = await graph_svc.get_org_graph(org_id, include_weak)

    if actor_id:
        level = await vis_svc.get_visibility_level(actor_id)
        graph = await vis_svc.filter_graph_by_visibility(graph, actor_id, level)

    return success_response(graph, "Org graph fetched")


@router.get("/graph/org/{org_id}/cycles", response_model=BaseResponse[dict])
async def detect_cycles(
    org_id: str,
    service: GraphService = Depends(get_graph_service),
):
    """Detect cycles in the organization's reporting-relationship graph.

    Analyzes the directed graph of reporting relationships and returns any
    cycles found.  This is useful for identifying data-integrity issues
    where circular reporting chains exist.

    HTTP Method:
        GET /api/v1/graph/org/{org_id}/cycles

    Args:
        org_id: Unique identifier of the organization to analyze.
        service: Injected ``GraphService`` instance.

    Returns:
        BaseResponse[dict]: A dictionary containing:
            - org_id (str): The organization ID that was analyzed.
            - cycles (list): A list of detected cycles, where each cycle
              is represented as a list of employee IDs.
            - has_cycles (bool): ``True`` if at least one cycle was found.

    Status Codes:
        200 OK: Cycle detection completed successfully.
        404 Not Found: No organization exists with the given ID.
    """
    cycles = await service.detect_cycles(org_id)
    return success_response(
        {"org_id": org_id, "cycles": cycles, "has_cycles": len(cycles) > 0},
        "Cycle detection complete",
    )
