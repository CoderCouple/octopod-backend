"""Service layer for Stripe billing and subscription management.

Handles checkout session creation, customer portal, webhook processing,
seat count synchronization, and plan state management.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.billing import stripe_client
from app.common.enum.org import OrgPlan, SubscriptionStatus
from app.db.repository.billing_event_repository import BillingEventRepository
from app.db.repository.organization_repository import OrganizationRepository
from app.db.repository.subscription_repository import SubscriptionRepository
from app.model.billing_event_model import BillingEvent
from app.model.subscription_model import Subscription
from app.settings import settings

logger = logging.getLogger(__name__)

_PRICE_TO_PLAN: dict[str, str] = {}


def _build_price_map() -> dict[str, str]:
    """Lazily build price-ID → plan-name mapping from settings."""
    if not _PRICE_TO_PLAN:
        if settings.stripe_price_id_pro:
            _PRICE_TO_PLAN[settings.stripe_price_id_pro] = OrgPlan.PRO.value
        if settings.stripe_price_id_enterprise:
            _PRICE_TO_PLAN[settings.stripe_price_id_enterprise] = OrgPlan.ENTERPRISE.value
    return _PRICE_TO_PLAN


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sub_repo = SubscriptionRepository(db)
        self.event_repo = BillingEventRepository(db)
        self.org_repo = OrganizationRepository(db)

    # ── Stripe Customer ───────────────────────────────────────────

    async def ensure_stripe_customer(
        self, org_id: str, org_name: str, email: str | None = None
    ) -> Subscription:
        """Get or create a Stripe customer + local subscription row for an org."""
        existing = await self.sub_repo.get_by_org_id(org_id)
        if existing:
            return existing

        customer_id = stripe_client.create_customer(
            name=org_name,
            email=email,
            metadata={"org_id": org_id},
        )

        subscription = Subscription(
            org_id=org_id,
            stripe_customer_id=customer_id,
            plan=OrgPlan.FREE.value,
            status=SubscriptionStatus.ACTIVE.value,
            seat_count=1,
        )
        return await self.sub_repo.create(subscription)

    # ── Checkout & Portal ─────────────────────────────────────────

    async def create_checkout_session(
        self, org_id: str, plan: str, success_url: str, cancel_url: str
    ) -> str:
        """Create a Stripe Checkout session for upgrading. Returns the checkout URL."""
        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No subscription found for org {org_id}",
            )

        price_map = {
            OrgPlan.PRO.value: settings.stripe_price_id_pro,
            OrgPlan.ENTERPRISE.value: settings.stripe_price_id_enterprise,
        }
        price_id = price_map.get(plan)
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No Stripe price configured for plan '{plan}'",
            )

        return stripe_client.create_checkout_session(
            customer_id=sub.stripe_customer_id,
            price_id=price_id,
            quantity=sub.seat_count,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"org_id": org_id, "plan": plan},
        )

    async def create_portal_session(self, org_id: str, return_url: str) -> str:
        """Create a Stripe Customer Portal session. Returns the portal URL."""
        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No subscription found for org {org_id}",
            )

        return stripe_client.create_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=return_url,
        )

    # ── Invoices ──────────────────────────────────────────────────

    async def get_invoices(self, org_id: str, limit: int = 20) -> list[dict]:
        """Return recent Stripe invoices for an org. Empty list if no customer yet."""
        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub or not sub.stripe_customer_id:
            return []
        try:
            return stripe_client.list_invoices(sub.stripe_customer_id, limit=limit)
        except Exception:
            logger.exception("Failed to list invoices for org=%s", org_id)
            return []

    # ── Usage vs Plan Limits ──────────────────────────────────────

    async def get_usage(self, org_id: str, project_id: str | None = None) -> dict:
        """Return current resource counts vs plan limits for the org's plan."""
        from sqlalchemy import func, select

        from app.common.billing.plan_limits import get_plan_limits
        from app.model.developer_profile_model import DeveloperProfile
        from app.model.email_campaign_model import EmailCampaign
        from app.model.mailbox_model import Mailbox
        from app.model.org_membership_model import OrgMembership
        from app.model.project_model import Project

        # Determine plan from subscription (fallback to free)
        sub = await self.sub_repo.get_by_org_id(org_id)
        plan = sub.plan if sub else OrgPlan.FREE.value
        limits = get_plan_limits(plan)

        async def count(model, *conds) -> int:
            q = select(func.count(model.id)).where(*conds)
            if hasattr(model, "is_deleted"):
                q = q.where(model.is_deleted == False)  # noqa: E712
            r = await self.db.execute(q)
            return r.scalar() or 0

        # Project-scoped counts
        mailboxes = 0
        campaigns = 0
        profiles = 0
        if project_id:
            mailboxes = await count(Mailbox, Mailbox.project_id == project_id)
            campaigns = await count(EmailCampaign, EmailCampaign.project_id == project_id)
            profiles = await count(DeveloperProfile, DeveloperProfile.project_id == project_id)

        # Org-scoped counts
        projects = await count(Project, Project.org_id == org_id)
        members_q = await self.db.execute(
            select(func.count(OrgMembership.id)).where(
                OrgMembership.org_id == org_id,
                OrgMembership.status.in_(["active", "invited"]),
            )
        )
        members = members_q.scalar() or 0

        return {
            "plan": plan,
            "items": [
                {"key": "mailboxes", "label": "Mailboxes", "used": mailboxes, "limit": limits.mailboxes},
                {"key": "campaigns", "label": "Campaigns", "used": campaigns, "limit": limits.campaigns},
                {"key": "developer_profiles", "label": "Developer profiles", "used": profiles, "limit": limits.developer_profiles},
                {"key": "projects", "label": "Projects", "used": projects, "limit": limits.projects},
                {"key": "org_members", "label": "Team members", "used": members, "limit": limits.org_members},
            ],
        }

    # ── Billing Info ──────────────────────────────────────────────

    async def get_billing_info(self, org_id: str) -> dict:
        """Return current billing state for an org."""
        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub:
            return {
                "plan": OrgPlan.FREE.value,
                "status": SubscriptionStatus.ACTIVE.value,
                "seat_count": 1,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "current_period_start": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
            }

        return {
            "plan": sub.plan,
            "status": sub.status,
            "seat_count": sub.seat_count,
            "stripe_customer_id": sub.stripe_customer_id,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end == "true",
        }

    # ── Seat Sync ─────────────────────────────────────────────────

    async def sync_seat_count(self, org_id: str, new_count: int) -> None:
        """Update seat count locally and on Stripe subscription."""
        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub:
            return

        sub.seat_count = new_count
        sub.updated_at = datetime.now(timezone.utc)
        await self.sub_repo.update(sub)

        if sub.stripe_subscription_id and sub.plan != OrgPlan.FREE.value:
            try:
                stripe_client.update_subscription_quantity(
                    sub.stripe_subscription_id, new_count
                )
            except Exception:
                logger.exception(
                    "Failed to sync seat count to Stripe for org=%s sub=%s",
                    org_id,
                    sub.stripe_subscription_id,
                )

    # ── Webhook Processing ────────────────────────────────────────

    async def handle_webhook_event(self, event) -> None:
        """Process a verified Stripe webhook event."""
        # Idempotency check
        if await self.event_repo.exists_by_stripe_event_id(event.id):
            logger.info("Duplicate webhook event %s — skipping", event.id)
            return

        # Determine org_id from event metadata or customer lookup
        org_id = self._extract_org_id(event)

        # Persist event for audit
        billing_event = BillingEvent(
            stripe_event_id=event.id,
            event_type=event.type,
            org_id=org_id,
            payload=json.dumps(event.data, default=str),
        )
        await self.event_repo.create(billing_event)

        # Dispatch by event type
        if event.type == "checkout.session.completed":
            await self._handle_checkout_completed(event.data["object"])
        elif event.type == "customer.subscription.updated":
            await self._handle_subscription_updated(event.data["object"])
        elif event.type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(event.data["object"])
        elif event.type == "invoice.payment_failed":
            await self._handle_payment_failed(event.data["object"])
        else:
            logger.info("Unhandled Stripe event type: %s", event.type)

    def _extract_org_id(self, event) -> str | None:
        """Try to extract org_id from event metadata or customer lookup."""
        obj = event.data.get("object", {})
        metadata = obj.get("metadata", {})
        return metadata.get("org_id")

    async def _handle_checkout_completed(self, session: dict) -> None:
        """Link Stripe subscription to our local subscription record."""
        org_id = session.get("metadata", {}).get("org_id")
        stripe_sub_id = session.get("subscription")
        if not org_id or not stripe_sub_id:
            logger.warning("Checkout completed but missing org_id or subscription ID")
            return

        sub = await self.sub_repo.get_by_org_id(org_id)
        if not sub:
            logger.warning("No local subscription for org %s", org_id)
            return

        sub.stripe_subscription_id = stripe_sub_id
        sub.updated_at = datetime.now(timezone.utc)
        await self.sub_repo.update(sub)
        logger.info("Linked Stripe subscription %s to org %s", stripe_sub_id, org_id)

    async def _handle_subscription_updated(self, stripe_sub: dict) -> None:
        """Sync plan, status, and period dates from Stripe."""
        sub = await self.sub_repo.get_by_stripe_subscription_id(stripe_sub["id"])
        if not sub:
            # Try by customer ID
            sub = await self.sub_repo.get_by_stripe_customer_id(stripe_sub["customer"])
            if not sub:
                logger.warning("No local subscription for Stripe sub %s", stripe_sub["id"])
                return

        # Update subscription ID if not yet set
        if not sub.stripe_subscription_id:
            sub.stripe_subscription_id = stripe_sub["id"]

        # Determine plan from price ID
        items = stripe_sub.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            price_map = _build_price_map()
            new_plan = price_map.get(price_id, sub.plan)
            sub.plan = new_plan

        # Sync status
        sub.status = stripe_sub.get("status", sub.status)
        sub.cancel_at_period_end = str(stripe_sub.get("cancel_at_period_end", False)).lower()

        # Sync period dates
        period_start = stripe_sub.get("current_period_start")
        period_end = stripe_sub.get("current_period_end")
        if period_start:
            sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
        if period_end:
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

        sub.updated_at = datetime.now(timezone.utc)
        await self.sub_repo.update(sub)

        # Sync plan to org table
        org = await self.org_repo.get_by_id(sub.org_id)
        if org and org.plan != sub.plan:
            org.plan = sub.plan
            org.updated_at = datetime.now(timezone.utc)
            await self.org_repo.update(org)
            logger.info("Updated org %s plan to %s", sub.org_id, sub.plan)

    async def _handle_subscription_deleted(self, stripe_sub: dict) -> None:
        """Downgrade org to free plan when subscription is canceled."""
        sub = await self.sub_repo.get_by_stripe_subscription_id(stripe_sub["id"])
        if not sub:
            return

        sub.status = SubscriptionStatus.CANCELED.value
        sub.plan = OrgPlan.FREE.value
        sub.stripe_subscription_id = None
        sub.current_period_start = None
        sub.current_period_end = None
        sub.cancel_at_period_end = "false"
        sub.updated_at = datetime.now(timezone.utc)
        await self.sub_repo.update(sub)

        # Downgrade org
        org = await self.org_repo.get_by_id(sub.org_id)
        if org:
            org.plan = OrgPlan.FREE.value
            org.updated_at = datetime.now(timezone.utc)
            await self.org_repo.update(org)
            logger.info("Downgraded org %s to free plan (subscription canceled)", sub.org_id)

    async def _handle_payment_failed(self, invoice: dict) -> None:
        """Mark subscription as past_due on payment failure."""
        stripe_sub_id = invoice.get("subscription")
        if not stripe_sub_id:
            return

        sub = await self.sub_repo.get_by_stripe_subscription_id(stripe_sub_id)
        if not sub:
            return

        sub.status = SubscriptionStatus.PAST_DUE.value
        sub.updated_at = datetime.now(timezone.utc)
        await self.sub_repo.update(sub)
        logger.warning("Payment failed for org %s — marked past_due", sub.org_id)
