"""Subscription state machine and premium management."""
import time

from src.auth.token_store import TokenStore


class SubscriptionState:
    NONE = "none"
    PENDING = "pending"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    TRIAL = "trial"


VALID_TRANSITIONS = {
    "none": ["pending"],
    "pending": ["active", "expired"],
    "active": ["grace", "expired", "cancelled"],
    "trial": ["active", "expired", "cancelled"],
    "grace": ["active", "expired"],
    "expired": ["pending"],
    "cancelled": ["pending"],
}


class InvalidStateTransitionError(Exception):
    """Raised when a subscription state transition is not allowed."""
    pass


class SubscriptionService:
    PLANS = {
        "monthly": {"name": "Bulanan", "price": 25000, "days": 30},
        "yearly": {"name": "Tahunan", "price": 200000, "days": 365},
        "lifetime": {"name": "Seumur Hidup", "price": 750000, "days": None},
    }

    def __init__(self, token_store: TokenStore):
        self.token_store = token_store

    def _now(self) -> float:
        return time.time()

    def _validate_transition(self, current: str, target: str) -> None:
        if target not in VALID_TRANSITIONS.get(current, []):
            raise InvalidStateTransitionError(
                f"Invalid transition from {current!r} to {target!r}"
            )

    def _get_current_subscription(self, telegram_id: str) -> dict | None:
        return self.token_store.get_subscription(telegram_id)

    def _current_status(self, subscription: dict | None) -> str:
        if subscription is None:
            return SubscriptionState.NONE
        return subscription.get("status", SubscriptionState.NONE)

    def start_free_trial(self, telegram_id: str) -> dict | None:
        """Start 7-day trial. Returns subscription dict or None if already used."""
        # Abuse check: a user may only ever start a trial once.
        existing = self.token_store.get_subscription(telegram_id)
        if existing is not None and existing.get("status") == SubscriptionState.TRIAL:
            return None
        # Also block if any prior subscription exists (trial already used or purchased before).
        if existing is not None:
            return None

        now = self._now()
        trial_end = now + 7 * 86400  # 7 days
        return self.token_store.create_subscription(
            telegram_id=telegram_id,
            plan="monthly",
            status=SubscriptionState.TRIAL,
            start_date=now,
            end_date=trial_end,
            trial_end=trial_end,
            payment_method="trial",
            payment_ref="trial",
            auto_renew=False,
        )

    def create_subscription(self, telegram_id: str, plan: str) -> dict:
        """Create pending subscription (awaiting payment)."""
        if plan not in self.PLANS:
            raise ValueError(f"Unknown plan: {plan!r}")

        current = self._get_current_subscription(telegram_id)
        current_status = self._current_status(current)

        self._validate_transition(current_status, SubscriptionState.PENDING)

        now = self._now()
        plan_info = self.PLANS[plan]
        end_date = None if plan_info["days"] is None else now + plan_info["days"] * 86400

        return self.token_store.create_subscription(
            telegram_id=telegram_id,
            plan=plan,
            status=SubscriptionState.PENDING,
            start_date=now,
            end_date=end_date,
            payment_method=None,
            payment_ref=None,
            auto_renew=False,
        )

    def activate_subscription(self, telegram_id: str, payment_ref: str) -> dict:
        """Activate subscription after successful payment and record an invoice."""
        current = self._get_current_subscription(telegram_id)
        current_status = self._current_status(current)

        if current_status == SubscriptionState.NONE:
            raise InvalidStateTransitionError(
                "Cannot activate: no subscription exists"
            )

        self._validate_transition(current_status, SubscriptionState.ACTIVE)

        plan = current.get("plan", "monthly")
        plan_info = self.PLANS.get(plan, self.PLANS["monthly"])
        now = self._now()
        end_date = None if plan_info["days"] is None else now + plan_info["days"] * 86400

        method = "unknown"
        if payment_ref and "_" in payment_ref:
            method = payment_ref.split("_", 1)[0]

        updated = self.token_store.update_subscription(
            current["id"],
            status=SubscriptionState.ACTIVE,
            end_date=end_date,
            auto_renew=(plan != "lifetime"),
            payment_ref=payment_ref,
            payment_method=method,
        )

        # Record paid invoice.
        self.token_store.create_invoice(
            telegram_id=telegram_id,
            subscription_id=updated["id"],
            amount=plan_info["price"],
            method=method,
            status="paid",
            payment_ref=payment_ref,
            raw_response="{}",
        )

        return updated

    def check_expiry(self, telegram_id: str) -> dict | None:
        """Check if subscription has expired. Handle state transitions."""
        current = self._get_current_subscription(telegram_id)
        if current is None:
            return None

        status = current.get("status")
        now = self._now()

        if status == SubscriptionState.TRIAL:
            trial_end = current.get("trial_end")
            if trial_end is not None and now > trial_end:
                self._validate_transition(status, SubscriptionState.EXPIRED)
                return self.token_store.update_subscription(
                    current["id"], status=SubscriptionState.EXPIRED
                )
            return current

        if status == SubscriptionState.ACTIVE:
            # Lifetime plans never expire.
            if current.get("plan") == "lifetime":
                return current
            end_date = current.get("end_date")
            if end_date is not None and now > end_date:
                self._validate_transition(status, SubscriptionState.EXPIRED)
                return self.token_store.update_subscription(
                    current["id"], status=SubscriptionState.EXPIRED
                )
            return current

        return current

    def cancel_subscription(self, telegram_id: str) -> dict:
        """Disable auto-renew. Subscription stays active until period end."""
        current = self._get_current_subscription(telegram_id)
        if current is None:
            raise InvalidStateTransitionError(
                "Cannot cancel: no subscription exists"
            )

        # Only disable auto-renew; status remains active (or trial/grace) until expiry.
        return self.token_store.update_subscription(
            current["id"], auto_renew=False
        )

    def get_active(self, telegram_id: str) -> dict | None:
        """Get active/trial subscription, handling auto-expiry checks."""
        current = self.check_expiry(telegram_id)
        if current is None:
            return None

        status = current.get("status")
        if status not in (SubscriptionState.ACTIVE, SubscriptionState.TRIAL, SubscriptionState.GRACE):
            return None

        now = self._now()

        if status == SubscriptionState.TRIAL:
            trial_end = current.get("trial_end")
            if trial_end is None or now <= trial_end:
                return current
            return None

        if status == SubscriptionState.ACTIVE:
            if current.get("plan") == "lifetime":
                return current
            end_date = current.get("end_date")
            if end_date is None or now <= end_date:
                return current
            return None

        # Grace period is treated as active for premium access.
        return current

    def is_premium(self, telegram_id: str) -> bool:
        """Check if user has active premium (trial, active, grace)."""
        return self.get_active(telegram_id) is not None
