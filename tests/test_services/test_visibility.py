from app.service.visibility_service import VisibilityService


def test_bfs_nodes():
    svc = VisibilityService.__new__(VisibilityService)
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
    ]
    # 2-hop from A should reach A, B, C
    result = svc._bfs_nodes(edges, "A", 2)
    assert "A" in result
    assert "B" in result
    assert "C" in result
    assert "D" not in result


def test_bfs_nodes_full_depth():
    svc = VisibilityService.__new__(VisibilityService)
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
    ]
    result = svc._bfs_nodes(edges, "A", 5)
    assert len(result) == 4


def test_blur_node():
    svc = VisibilityService.__new__(VisibilityService)
    blurred = svc._blur_node("emp_1", "emp_2")
    assert blurred["blurred"] is True
    assert blurred["display_name"] == "Anonymous"

    own = svc._blur_node("emp_1", "emp_1")
    assert own["blurred"] is False


def test_filter_graph_level_3_returns_full():
    svc = VisibilityService.__new__(VisibilityService)
    graph = {
        "org_id": "org1",
        "nodes": ["A", "B", "C"],
        "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "node_count": 3,
        "edge_count": 2,
    }
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        svc.filter_graph_by_visibility(graph, "A", 3)
    )
    assert result == graph
