from dataclasses import dataclass


@dataclass
class FusedResult:
    profile_id: str
    rrf_score: float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0
    vector_rank: int = 0
    keyword_rank: int = 0


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[str, float]],
    k: int = 60,
) -> list[FusedResult]:
    """Merge N ranked lists using Reciprocal Rank Fusion.

    Args:
        *ranked_lists: Variable number of (profile_id, score) lists.
        k: RRF constant (default 60).

    Returns:
        Sorted list of FusedResult by descending rrf_score.
    """
    merged: dict[str, FusedResult] = {}

    for list_idx, ranked_list in enumerate(ranked_lists):
        for rank, (pid, score) in enumerate(ranked_list, start=1):
            if pid not in merged:
                merged[pid] = FusedResult(profile_id=pid)
            merged[pid].rrf_score += 1.0 / (k + rank)

            # Store scores for the first two lists (vector + keyword) for backwards compat
            if list_idx == 0:
                merged[pid].vector_score = score
                merged[pid].vector_rank = rank
            elif list_idx == 1:
                merged[pid].keyword_score = score
                merged[pid].keyword_rank = rank

    results = sorted(merged.values(), key=lambda r: r.rrf_score, reverse=True)
    return results
