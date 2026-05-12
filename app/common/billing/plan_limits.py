"""Plan limit definitions for each subscription tier.

Frozen dataclasses — change limits by editing this file and deploying.
"""

from dataclasses import dataclass

from app.common.enum.org import OrgPlan


@dataclass(frozen=True)
class PlanLimits:
    emails_per_month: int
    mailboxes: int
    campaigns: int
    developer_profiles: int
    ingestion_jobs_per_month: int
    enrichment_calls_per_month: int
    projects: int
    org_members: int


FREE_LIMITS = PlanLimits(
    emails_per_month=200,
    mailboxes=1,
    campaigns=2,
    developer_profiles=100,
    ingestion_jobs_per_month=5,
    enrichment_calls_per_month=50,
    projects=1,
    org_members=1,
)

PRO_LIMITS = PlanLimits(
    emails_per_month=5_000,
    mailboxes=5,
    campaigns=20,
    developer_profiles=5_000,
    ingestion_jobs_per_month=50,
    enrichment_calls_per_month=2_000,
    projects=10,
    org_members=10,
)

ENTERPRISE_LIMITS = PlanLimits(
    emails_per_month=100_000,
    mailboxes=50,
    campaigns=200,
    developer_profiles=100_000,
    ingestion_jobs_per_month=500,
    enrichment_calls_per_month=50_000,
    projects=100,
    org_members=100,
)

_PLAN_MAP: dict[str, PlanLimits] = {
    OrgPlan.FREE.value: FREE_LIMITS,
    OrgPlan.PRO.value: PRO_LIMITS,
    OrgPlan.ENTERPRISE.value: ENTERPRISE_LIMITS,
}


def get_plan_limits(plan: str) -> PlanLimits:
    """Return the limits for a given plan tier. Defaults to free."""
    return _PLAN_MAP.get(plan, FREE_LIMITS)
