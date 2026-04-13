"""Service layer for visibility-based graph filtering.

Provides business logic for filtering the organizational reporting graph
based on a contributor's visibility level. Higher visibility levels grant
access to more of the graph. At lower levels, node identities are blurred
and only nearby nodes (determined by BFS hop distance) are visible.

Visibility levels and their behavior:
    - Level 0: Only direct edges involving the actor; all other node names
      are blurred to "Anonymous".
    - Level 1: 2-hop BFS neighborhood from the actor; non-actor node names
      are blurred.
    - Level 2: 5-hop BFS neighborhood from the actor; full node IDs are
      visible.
    - Level 3: Full graph access with no filtering or blurring.
"""

from collections import deque

from sqlalchemy.ext.asyncio import AsyncSession

from app.service.contributor_service import ContributorService
from app.service.graph_service import GraphService


class VisibilityService:
    """Service for filtering organizational graphs based on contributor visibility.

    Applies visibility-level-based filtering to org graph data, controlling
    which nodes and edges a contributor can see and whether node identities
    are blurred. Uses BFS to determine reachable nodes within a hop limit.
    """

    def __init__(self, db: AsyncSession):
        """Initialize VisibilityService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.contributor = ContributorService(db)
        self.graph = GraphService(db)

    async def get_visibility_level(self, actor_id: str) -> int:
        """Get the visibility level for a given actor.

        Delegates to the ContributorService to retrieve the actor's current
        visibility level based on their reputation score.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            An integer visibility level from 0 (least access) to 3
            (full access).
        """
        return await self.contributor.get_visibility_level(actor_id)

    async def filter_graph_by_visibility(
        self, graph: dict, actor_employee_id: str | None, level: int
    ) -> dict:
        """Filter an organization graph based on the actor's visibility level.

        Applies visibility restrictions to the graph data. At level 3, the
        full graph is returned unmodified. At lower levels, only nodes
        within a certain BFS hop distance from the actor are included, and
        node identities may be blurred.

        Args:
            graph: The full organization graph dictionary as returned by
                GraphService.get_org_graph, containing org_id, nodes, edges,
                node_count, and edge_count.
            actor_employee_id: The UUID string of the employee associated
                with the requesting actor, or None if unknown.
            level: The visibility level (0-3) determining the filtering
                behavior.

        Returns:
            A filtered graph dictionary with the same structure as the input
            but containing only visible nodes and edges. Includes an
            additional "visibility_level" key for levels below 3.
        """
        if level >= 3:
            return graph

        edges = graph.get("edges", [])

        if level == 0:
            # Only direct edges for the actor, names blurred
            filtered_edges = [
                e
                for e in edges
                if e["source"] == actor_employee_id
                or e["target"] == actor_employee_id
            ]
            visible_nodes = set()
            for e in filtered_edges:
                visible_nodes.add(e["source"])
                visible_nodes.add(e["target"])
            blurred_nodes = [
                self._blur_node(n, actor_employee_id) for n in visible_nodes
            ]
            return {
                "org_id": graph["org_id"],
                "nodes": blurred_nodes,
                "edges": filtered_edges,
                "node_count": len(blurred_nodes),
                "edge_count": len(filtered_edges),
                "visibility_level": level,
            }

        # Level 1: 2-hop BFS, Level 2: 5-hop BFS
        max_hops = 2 if level == 1 else 5
        visible_nodes = self._bfs_nodes(edges, actor_employee_id, max_hops)

        filtered_edges = [
            e
            for e in edges
            if e["source"] in visible_nodes and e["target"] in visible_nodes
        ]

        result_nodes = list(visible_nodes)
        if level == 1:
            result_nodes = [
                self._blur_node(n, actor_employee_id) for n in visible_nodes
            ]

        return {
            "org_id": graph["org_id"],
            "nodes": result_nodes,
            "edges": filtered_edges,
            "node_count": len(result_nodes),
            "edge_count": len(filtered_edges),
            "visibility_level": level,
        }

    def _bfs_nodes(
        self, edges: list[dict], start: str | None, max_hops: int
    ) -> set[str]:
        """Find all nodes reachable within a given hop distance via BFS.

        Builds an undirected adjacency list from the edges and performs
        breadth-first search from the start node, stopping at the
        specified maximum depth.

        Args:
            edges: A list of edge dictionaries, each containing "source"
                and "target" keys with node ID strings.
            start: The node ID to start BFS from, or None. If None, an
                empty set is returned.
            max_hops: The maximum number of hops (edges) to traverse from
                the start node.

        Returns:
            A set of node ID strings reachable within max_hops from the
            start node, including the start node itself.
        """
        if not start:
            return set()

        adjacency: dict[str, set[str]] = {}
        for e in edges:
            adjacency.setdefault(e["source"], set()).add(e["target"])
            adjacency.setdefault(e["target"], set()).add(e["source"])

        visited = {start}
        queue = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return visited

    def _blur_node(self, node_id: str, actor_id: str | None) -> dict:
        """Create a blurred representation of a node for privacy.

        Returns the node's full identity if it belongs to the requesting
        actor, otherwise replaces the display name with "Anonymous".

        Args:
            node_id: The UUID string of the node to represent.
            actor_id: The UUID string of the requesting actor, or None.

        Returns:
            A dictionary with "id" and "blurred" keys. If blurred is True,
            also includes a "display_name" key set to "Anonymous".
        """
        if node_id == actor_id:
            return {"id": node_id, "blurred": False}
        return {"id": node_id, "blurred": True, "display_name": "Anonymous"}
