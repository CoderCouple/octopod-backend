"""Service layer for organizational reporting graph operations.

Provides business logic for building, querying, and validating the
directed graph of reporting relationships within an organization.
Supports graph retrieval, cycle detection, hypothetical cycle checking,
and enforcement of the single solid-line manager constraint.
"""

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository.reporting_relationship_repository import (
    ReportingRelationshipRepository,
)


class GraphService:
    """Service for organizational reporting graph analysis and validation.

    Builds and analyzes the directed graph formed by reporting relationships
    within an organization. The graph is modeled as edges from employees to
    their managers. Provides cycle detection, hypothetical edge testing, and
    structural validation to maintain graph integrity.
    """

    def __init__(self, db: AsyncSession):
        """Initialize GraphService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.rr_repo = ReportingRelationshipRepository(db)

    async def get_org_graph(
        self, org_id: str, include_weak: bool = False
    ) -> dict:
        """Build and return the full reporting graph for an organization.

        Fetches all current reporting relationships for the organization and
        constructs a graph representation with nodes (employee IDs) and
        edges (reporting relationships with metadata).

        Args:
            org_id: The UUID string of the organization whose graph to build.
            include_weak: Whether to include relationships with "weak" status.
                Defaults to False, which filters out weak relationships.

        Returns:
            A dictionary containing:
                - org_id: The organization identifier.
                - nodes: List of unique employee ID strings.
                - edges: List of edge dictionaries with id, source, target,
                    relationship_type, status, and confidence_score.
                - node_count: Total number of unique nodes.
                - edge_count: Total number of edges.
        """
        relationships, _ = await self.rr_repo.list_filtered(
            org_id=org_id, is_current=True, offset=0, limit=10000
        )

        if not include_weak:
            relationships = [r for r in relationships if r.status != "weak"]

        nodes = set()
        edges = []
        for rr in relationships:
            nodes.add(rr.employee_id)
            nodes.add(rr.manager_employee_id)
            edges.append(
                {
                    "id": rr.id,
                    "source": rr.employee_id,
                    "target": rr.manager_employee_id,
                    "relationship_type": rr.relationship_type,
                    "status": rr.status,
                    "confidence_score": str(rr.confidence_score),
                }
            )

        return {
            "org_id": org_id,
            "nodes": list(nodes),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    async def detect_cycles(self, org_id: str) -> list[list[str]]:
        """Detect all cycles in the organization's reporting graph.

        Uses depth-first search with a recursion stack to find all cycles
        in the directed graph of current reporting relationships.

        Args:
            org_id: The UUID string of the organization to check for cycles.

        Returns:
            A list of cycles, where each cycle is a list of employee ID
            strings forming the cycle. The first and last elements of each
            cycle list are the same node. Returns an empty list if no
            cycles exist.
        """
        relationships, _ = await self.rr_repo.list_filtered(
            org_id=org_id, is_current=True, offset=0, limit=10000
        )

        graph: dict[str, list[str]] = defaultdict(list)
        for rr in relationships:
            graph[rr.employee_id].append(rr.manager_employee_id)

        all_nodes = set(graph.keys())
        for targets in graph.values():
            all_nodes.update(targets)

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    dfs(neighbor, path)

            path.pop()
            rec_stack.discard(node)

        for node in all_nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    async def would_create_cycle(
        self, org_id: str, employee_id: str, manager_id: str
    ) -> bool:
        """Check whether adding a proposed edge would create a cycle.

        Builds the current reporting graph, adds the proposed
        employee -> manager edge, and performs a DFS from the manager
        to determine if the employee can be reached again (indicating
        a cycle).

        Args:
            org_id: The UUID string of the organization.
            employee_id: The UUID string of the employee (edge source).
            manager_id: The UUID string of the proposed manager (edge target).

        Returns:
            True if adding the edge would create a cycle, False otherwise.
        """
        relationships, _ = await self.rr_repo.list_filtered(
            org_id=org_id, is_current=True, offset=0, limit=10000
        )

        graph: dict[str, list[str]] = defaultdict(list)
        for rr in relationships:
            graph[rr.employee_id].append(rr.manager_employee_id)

        # Add the proposed edge
        graph[employee_id].append(manager_id)

        # DFS from employee_id to see if we can reach employee_id again
        visited = set()

        def has_cycle(node: str) -> bool:
            if node in visited:
                return False
            visited.add(node)
            for neighbor in graph.get(node, []):
                if neighbor == employee_id:
                    return True
                if has_cycle(neighbor):
                    return True
            return False

        return has_cycle(manager_id)

    async def validate_single_solid_manager(
        self, employee_id: str, org_id: str, proposed_manager_id: str
    ) -> str | None:
        """Validate that adding a solid-line manager does not violate constraints.

        Checks whether the employee already has a confirmed solid-line manager
        who is different from the proposed manager. An employee may only have
        one confirmed solid-line manager at a time within an organization.

        Args:
            employee_id: The UUID string of the employee.
            org_id: The UUID string of the organization.
            proposed_manager_id: The UUID string of the proposed new manager.

        Returns:
            A conflict description string if the employee already has a
            different confirmed solid-line manager, or None if there is
            no conflict.
        """
        relationships, _ = await self.rr_repo.list_filtered(
            org_id=org_id, employee_id=employee_id, is_current=True, offset=0, limit=100
        )

        for rr in relationships:
            if (
                rr.relationship_type == "solid_line"
                and rr.manager_employee_id != proposed_manager_id
                and rr.status == "confirmed"
            ):
                return (
                    f"Employee {employee_id} already has a confirmed solid-line manager: "
                    f"{rr.manager_employee_id}"
                )
        return None
