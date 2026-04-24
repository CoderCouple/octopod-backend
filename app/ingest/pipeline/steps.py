"""Declarative step definitions for each pipeline type."""
from __future__ import annotations

from app.common.enum.ingest import PipelineType

DAILY_STEPS = [
    {"name": "gh_discover", "label": "GH Discover"},
    {"name": "gh_ingest", "label": "GH Ingest"},
    {"name": "hf_discover", "label": "HF Discover"},
    {"name": "hf_ingest", "label": "HF Ingest"},
    {"name": "identity_resolve", "label": "Identity Resolve"},
    {"name": "bridge_sync", "label": "Bridge Sync"},
    {"name": "embed", "label": "Embed"},
]

WEEKLY_STEPS = [
    {"name": "ln_discover", "label": "LN Discover"},
    {"name": "ln_ingest", "label": "LN Ingest"},
    {"name": "bridge_sync", "label": "Bridge Sync"},
    {"name": "embed", "label": "Embed"},
]

SEED_STEPS = [
    {"name": "gh_discover", "label": "GH Discover"},
    {"name": "gh_ingest", "label": "GH Ingest"},
    {"name": "bridge_sync", "label": "Bridge Sync"},
    {"name": "embed", "label": "Embed"},
]

GH_ONLY_STEPS = [
    {"name": "gh_discover", "label": "GH Discover"},
    {"name": "gh_ingest", "label": "GH Ingest"},
]

HF_ONLY_STEPS = [
    {"name": "hf_discover", "label": "HF Discover"},
    {"name": "hf_ingest", "label": "HF Ingest"},
]

LN_ONLY_STEPS = [
    {"name": "ln_discover", "label": "LN Discover"},
    {"name": "ln_ingest", "label": "LN Ingest"},
]

DEPENDENT_STEPS = [
    {"name": "gh_discover", "label": "GH Discover"},
    {"name": "gh_ingest", "label": "GH Ingest"},
    {"name": "hf_crossref", "label": "HF Cross-Reference"},
    {"name": "hf_ingest", "label": "HF Ingest"},
    {"name": "identity_resolve", "label": "Identity Resolve"},
    {"name": "ln_crossref", "label": "LN Cross-Reference"},
    {"name": "ln_ingest", "label": "LN Ingest"},
    {"name": "bridge_sync", "label": "Bridge Sync"},
    {"name": "embed", "label": "Embed"},
]

_STEP_MAP = {
    PipelineType.DAILY: DAILY_STEPS,
    PipelineType.WEEKLY: WEEKLY_STEPS,
    PipelineType.SEED: SEED_STEPS,
    PipelineType.GH_ONLY: GH_ONLY_STEPS,
    PipelineType.HF_ONLY: HF_ONLY_STEPS,
    PipelineType.LN_ONLY: LN_ONLY_STEPS,
    PipelineType.DEPENDENT: DEPENDENT_STEPS,
}


def get_steps(pipeline_type: str) -> list[dict[str, str]]:
    """Return the step list for a given pipeline type."""
    return _STEP_MAP[PipelineType(pipeline_type)]
