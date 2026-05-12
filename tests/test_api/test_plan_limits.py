"""Unit tests for plan limits and enforcement."""

from app.common.billing.plan_limits import (
    ENTERPRISE_LIMITS,
    FREE_LIMITS,
    PRO_LIMITS,
    get_plan_limits,
)


def test_free_plan_limits():
    limits = get_plan_limits("free")
    assert limits is FREE_LIMITS
    assert limits.emails_per_month == 200
    assert limits.mailboxes == 1
    assert limits.campaigns == 2
    assert limits.developer_profiles == 100
    assert limits.ingestion_jobs_per_month == 5
    assert limits.enrichment_calls_per_month == 50
    assert limits.projects == 1
    assert limits.org_members == 1


def test_pro_plan_limits():
    limits = get_plan_limits("pro")
    assert limits is PRO_LIMITS
    assert limits.emails_per_month == 5_000
    assert limits.mailboxes == 5
    assert limits.campaigns == 20
    assert limits.org_members == 10


def test_enterprise_plan_limits():
    limits = get_plan_limits("enterprise")
    assert limits is ENTERPRISE_LIMITS
    assert limits.emails_per_month == 100_000
    assert limits.mailboxes == 50
    assert limits.org_members == 100


def test_unknown_plan_defaults_to_free():
    limits = get_plan_limits("nonexistent")
    assert limits is FREE_LIMITS


def test_plan_limits_are_frozen():
    limits = get_plan_limits("free")
    try:
        limits.mailboxes = 999
        raise AssertionError("Should not be able to mutate frozen dataclass")
    except AttributeError:
        pass
