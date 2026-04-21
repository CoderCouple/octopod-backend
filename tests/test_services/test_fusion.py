from app.service.search.fusion import reciprocal_rank_fusion


def test_rrf_basic_fusion():
    """Profiles appearing in both lists get the highest fused scores."""
    vector = [("p1", 0.9), ("p2", 0.8), ("p3", 0.7)]
    keyword = [("p2", 0.5), ("p4", 0.4), ("p1", 0.3)]

    results = reciprocal_rank_fusion(vector, keyword)

    # p1 and p2 appear in both lists, so should have highest RRF scores
    result_ids = [r.profile_id for r in results]
    assert result_ids[0] in ("p1", "p2")
    assert result_ids[1] in ("p1", "p2")

    # Profiles in both lists should have higher scores than those in just one
    dual_scores = {r.profile_id: r.rrf_score for r in results if r.profile_id in ("p1", "p2")}
    single_scores = {r.profile_id: r.rrf_score for r in results if r.profile_id in ("p3", "p4")}
    assert min(dual_scores.values()) > max(single_scores.values())


def test_rrf_empty_lists():
    results = reciprocal_rank_fusion([], [])
    assert results == []


def test_rrf_one_empty_list():
    vector = [("p1", 0.9), ("p2", 0.8)]
    results = reciprocal_rank_fusion(vector, [])
    assert len(results) == 2
    assert results[0].profile_id == "p1"
    assert results[0].vector_score == 0.9
    assert results[0].keyword_score == 0.0


def test_rrf_deduplication():
    """Same profile in both lists should produce a single entry with summed RRF."""
    vector = [("p1", 0.9)]
    keyword = [("p1", 0.8)]

    results = reciprocal_rank_fusion(vector, keyword)

    assert len(results) == 1
    assert results[0].profile_id == "p1"
    # RRF score should be sum of both contributions: 1/(60+1) + 1/(60+1)
    expected = 1.0 / 61 + 1.0 / 61
    assert abs(results[0].rrf_score - expected) < 1e-9
    assert results[0].vector_score == 0.9
    assert results[0].keyword_score == 0.8


def test_rrf_preserves_ranks():
    vector = [("p1", 0.9), ("p2", 0.8)]
    keyword = [("p3", 0.7), ("p1", 0.6)]

    results = reciprocal_rank_fusion(vector, keyword)

    result_map = {r.profile_id: r for r in results}
    assert result_map["p1"].vector_rank == 1
    assert result_map["p1"].keyword_rank == 2
    assert result_map["p2"].vector_rank == 2
    assert result_map["p2"].keyword_rank == 0  # not in keyword results
    assert result_map["p3"].keyword_rank == 1
    assert result_map["p3"].vector_rank == 0  # not in vector results
