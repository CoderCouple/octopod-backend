from dataclasses import dataclass, field


@dataclass
class FusedResult:
    profile_id: str
    rrf_score: float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0
    vector_rank: int = 0
    keyword_rank: int = 0


def reciprocal_rank_fusion(
    vector_results: list[tuple[str, float]],
    keyword_results: list[tuple[str, float]],
    k: int = 60,
) -> list[FusedResult]:
    """Merge vector and keyword search results using Reciprocal Rank Fusion.

    Args:
        vector_results: List of (profile_id, score) from vector search.
        keyword_results: List of (profile_id, score) from keyword search.
        k: RRF constant (default 60).

    Returns:
        Sorted list of FusedResult by descending rrf_score.
    """
    merged: dict[str, FusedResult] = {}

    for rank, (pid, score) in enumerate(vector_results, start=1):
        if pid not in merged:
            merged[pid] = FusedResult(profile_id=pid)
        merged[pid].rrf_score += 1.0 / (k + rank)
        merged[pid].vector_score = score
        merged[pid].vector_rank = rank

    for rank, (pid, score) in enumerate(keyword_results, start=1):
        if pid not in merged:
            merged[pid] = FusedResult(profile_id=pid)
        merged[pid].rrf_score += 1.0 / (k + rank)
        merged[pid].keyword_score = score
        merged[pid].keyword_rank = rank

    results = sorted(merged.values(), key=lambda r: r.rrf_score, reverse=True)
    return results
