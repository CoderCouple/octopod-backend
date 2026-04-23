"""Pure merge functions for each level of the 4-layer pipeline.

All functions are pure (no DB I/O) and return dicts suitable for
upsert operations + merge audit log entries.
"""
from __future__ import annotations

from typing import Any

# ---- Priority definitions ----

DEV_FIELD_PRIORITY: dict[str, list[str]] = {
    "display_name": ["github", "huggingface"],
    "bio": ["github", "huggingface"],
    "avatar_url": ["github", "huggingface"],
    "company": ["github", "huggingface"],
    "location": ["github", "huggingface"],
    "website": ["github", "huggingface"],
}

SOCIAL_FIELD_PRIORITY: dict[str, list[str]] = {
    "display_name": ["linkedin", "x_twitter"],
    "headline": ["linkedin", "x_twitter"],
    "bio": ["linkedin", "x_twitter"],
    "avatar_url": ["linkedin", "x_twitter"],
    "location": ["linkedin", "x_twitter"],
    "current_title": ["linkedin", "x_twitter"],
    "current_company": ["linkedin", "x_twitter"],
    "industry": ["linkedin"],
}

AGGREGATION_FIELD_PRIORITY: dict[str, list[str]] = {
    "display_name": ["social_profile", "developer_profile"],
    "bio": ["social_profile", "developer_profile"],
    "avatar_url": ["developer_profile", "social_profile"],
    "company": ["social_profile", "developer_profile"],
    "location": ["social_profile", "developer_profile"],
    "website": ["developer_profile", "social_profile"],
    "headline": ["social_profile"],
    "current_title": ["social_profile"],
    "current_company": ["social_profile"],
    "industry": ["social_profile"],
}


def _pick_winner(
    field: str,
    priorities: list[str],
    source_data: dict[str, dict[str, Any]],
    previous_value: Any = None,
) -> dict[str, Any]:
    """Pick the winning value for a field from prioritized sources.

    Returns a dict with keys: field, winner, value, previous, overridden, action.
    """
    winner = None
    winning_value = None
    overridden: list[dict[str, Any]] = []

    for source in priorities:
        data = source_data.get(source, {})
        val = data.get(field)
        if val:
            if winner is None:
                winner = source
                winning_value = val
            else:
                overridden.append({"source": source, "value": str(val)[:500]})

    if winner is None:
        return {
            "field": field,
            "winner": "none",
            "value": None,
            "previous": str(previous_value)[:500] if previous_value else None,
            "overridden": overridden or None,
            "action": "unchanged",
        }

    if str(winning_value) == str(previous_value):
        action = "unchanged"
    elif previous_value is None:
        action = "created"
    else:
        action = "updated"

    return {
        "field": field,
        "winner": winner,
        "value": str(winning_value)[:500] if winning_value else None,
        "previous": str(previous_value)[:500] if previous_value else None,
        "overridden": overridden or None,
        "action": action,
    }


def merge_dev_fields(
    gh_data: dict[str, Any],
    hf_data: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge GH+HF data into developer_profile fields.

    Returns (merged_data, field_decisions) where merged_data is ready
    for DB upsert and field_decisions is for merge_audit_log.
    """
    existing = existing or {}
    source_data = {"github": gh_data, "huggingface": hf_data}
    merged: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []
    source_priority: dict[str, str] = {}

    # Priority-based text fields
    for field, priorities in DEV_FIELD_PRIORITY.items():
        result = _pick_winner(field, priorities, source_data, existing.get(field))
        if result["value"] is not None:
            merged[field] = result["value"]
            source_priority[field] = result["winner"]
        decisions.append(result)

    # Numeric fields: sum or max from each source
    numeric_fields = {
        "total_repos": ("github", "total_repos"),
        "total_stars": ("github", "total_stars"),
        "total_contributions": ("github", "total_contributions"),
        "total_followers": ("github", "total_followers"),
        "total_hf_models": ("huggingface", "total_hf_models"),
        "total_hf_datasets": ("huggingface", "total_hf_datasets"),
        "total_hf_spaces": ("huggingface", "total_hf_spaces"),
        "total_hf_downloads": ("huggingface", "total_hf_downloads"),
        "total_papers": ("huggingface", "total_papers"),
    }
    for field, (source, key) in numeric_fields.items():
        val = source_data.get(source, {}).get(key, 0) or 0
        merged[field] = val
        prev = existing.get(field)
        action = "unchanged" if val == prev else ("created" if prev is None else "updated")
        decisions.append({
            "field": field,
            "winner": source,
            "value": str(val),
            "previous": str(prev) if prev is not None else None,
            "overridden": None,
            "action": action,
        })

    # Languages from GitHub (authoritative)
    gh_langs = gh_data.get("languages", [])
    merged["languages"] = gh_langs
    if gh_langs:
        source_priority["languages"] = "github"

    # Topics from GitHub
    gh_topics = gh_data.get("topics", [])
    merged["topics"] = gh_topics
    if gh_topics:
        source_priority["topics"] = "github"

    # Skills: union from all sources
    all_skills: set[str] = set()
    for _source_name, data in source_data.items():
        skills = data.get("skills", [])
        if isinstance(skills, list):
            all_skills.update(s for s in skills if isinstance(s, str))
    merged["skills"] = sorted(all_skills)
    if all_skills:
        source_priority["skills"] = "union"

    merged["dev_source_priority"] = source_priority
    return merged, decisions


def merge_social_fields(
    ln_data: dict[str, Any],
    x_data: dict[str, Any] | None = None,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge LN+X data into social_profile fields."""
    existing = existing or {}
    x_data = x_data or {}
    source_data = {"linkedin": ln_data, "x_twitter": x_data}
    merged: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []
    source_priority: dict[str, str] = {}

    # Priority-based text fields
    for field, priorities in SOCIAL_FIELD_PRIORITY.items():
        result = _pick_winner(field, priorities, source_data, existing.get(field))
        if result["value"] is not None:
            merged[field] = result["value"]
            source_priority[field] = result["winner"]
        decisions.append(result)

    # LinkedIn-specific fields
    for field in [
        "years_of_experience", "job_history", "education",
        "certifications", "connections",
    ]:
        val = ln_data.get(field)
        if val is not None:
            merged[field] = val
            source_priority[field] = "linkedin"

    # Skills: union
    all_skills: set[str] = set()
    for _source_name, data in source_data.items():
        skills = data.get("skills", [])
        if isinstance(skills, list):
            all_skills.update(s for s in skills if isinstance(s, str))
    merged["skills"] = sorted(all_skills)
    if all_skills:
        source_priority["skills"] = "union"

    merged["social_source_priority"] = source_priority
    return merged, decisions


def merge_aggregated_fields(
    dev_data: dict[str, Any],
    social_data: dict[str, Any] | None = None,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge developer_profile + social_profile → aggregated_individual_profile."""
    existing = existing or {}
    social_data = social_data or {}
    source_data = {"developer_profile": dev_data, "social_profile": social_data}
    merged: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []
    source_priority: dict[str, str] = {}

    # Priority-based text fields
    for field, priorities in AGGREGATION_FIELD_PRIORITY.items():
        result = _pick_winner(field, priorities, source_data, existing.get(field))
        if result["value"] is not None:
            merged[field] = result["value"]
            source_priority[field] = result["winner"]
        decisions.append(result)

    # Numeric fields: straight from developer_profile
    for field in [
        "total_repos", "total_stars", "total_contributions", "total_followers",
        "total_hf_models", "total_hf_datasets", "total_hf_spaces",
        "total_hf_downloads", "total_papers",
    ]:
        val = dev_data.get(field, 0) or 0
        merged[field] = val

    # JSONB arrays: from developer_profile
    for field in ["languages", "topics"]:
        merged[field] = dev_data.get(field, [])

    # Skills: union of dev + social skills
    dev_skills = set(dev_data.get("skills", []))
    soc_skills = set(social_data.get("skills", []))
    merged["skills"] = sorted(dev_skills | soc_skills)

    # Social fields from social_profile
    for field in [
        "years_of_experience", "job_history", "education",
        "certifications", "connections",
    ]:
        val = social_data.get(field)
        if val is not None:
            merged[field] = val

    merged["source_priority"] = source_priority
    return merged, decisions


def merge_cohesive_fields(
    aggregated_data: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """aggregated_individual_profile → cohesive_individual_profile.

    This level primarily copies data and adds computed attributes.
    """
    existing = existing or {}
    merged: dict[str, Any] = {}
    decisions: list[dict[str, Any]] = []

    # Direct copy of all fields
    copy_fields = [
        "display_name", "bio", "headline", "location", "avatar_url",
        "company", "website", "total_repos", "total_stars", "total_contributions",
        "total_followers", "total_hf_models", "total_hf_datasets", "total_hf_spaces",
        "total_hf_downloads", "total_papers", "languages", "skills", "topics",
        "years_of_experience", "current_title", "current_company", "job_history",
    ]
    for field in copy_fields:
        val = aggregated_data.get(field)
        merged[field] = val
        prev = existing.get(field)
        action = "unchanged" if str(val) == str(prev) else (
            "created" if prev is None else "updated"
        )
        decisions.append({
            "field": field,
            "winner": "aggregated",
            "value": str(val)[:500] if val is not None else None,
            "previous": str(prev)[:500] if prev is not None else None,
            "overridden": None,
            "action": action,
        })

    merged["source_priority"] = aggregated_data.get("source_priority", {})
    return merged, decisions


def build_embedding_text(profile_data: dict[str, Any]) -> str:
    """Build embedding text from profile data dict."""
    parts: list[str] = []
    if profile_data.get("headline"):
        parts.append(profile_data["headline"])
    if profile_data.get("bio"):
        parts.append(profile_data["bio"])
    if profile_data.get("current_title") and profile_data.get("current_company"):
        parts.append(f"{profile_data['current_title']} at {profile_data['current_company']}")
    elif profile_data.get("current_title"):
        parts.append(profile_data["current_title"])
    if profile_data.get("location"):
        parts.append(f"Located in {profile_data['location']}")
    if profile_data.get("skills"):
        parts.append(f"Skills: {', '.join(profile_data['skills'][:20])}")
    if profile_data.get("languages"):
        parts.append(f"Languages: {', '.join(profile_data['languages'][:15])}")
    if profile_data.get("topics"):
        parts.append(f"Topics: {', '.join(profile_data['topics'][:15])}")
    if profile_data.get("total_contributions"):
        parts.append(f"{profile_data['total_contributions']} contributions")
    if profile_data.get("total_stars"):
        parts.append(f"{profile_data['total_stars']} GitHub stars")
    if profile_data.get("total_hf_models"):
        parts.append(f"{profile_data['total_hf_models']} HuggingFace models")
    if profile_data.get("website"):
        parts.append(profile_data["website"])
    if profile_data.get("job_history"):
        for job in profile_data["job_history"][:5]:
            title = job.get("title", "")
            company = job.get("company", "")
            if title and company:
                parts.append(f"{title} at {company}")
    return ". ".join(parts)
