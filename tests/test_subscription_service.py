"""Test subscription state machine and premium management."""
import sqlite3
import time

import pytest
from cryptography.fernet import Fernet

from src.auth.token_store import TokenStore
from src.services.subscription_service import (
    SubscriptionService,
    SubscriptionState,
    InvalidStateTransitionError,
    VALID_TRANSITIONS,
)


@pytest.fixture
def valid_key(monkeypatch):
    key = Fernet.generate_key().decode()
    for env_name, value in {
        "TELEGRAM_TOKEN": "token",
        "GOOGLE_CLIENT_ID": "id",
        "GOOGLE_CLIENT_SECRET": "secret",
        "FERNET_KEY": key,
    }.items():
        monkeypatch.setenv(env_name, value)
    monkeypatch.setattr("src.config._settings", None)
    return key


@pytest.fixture
def store(valid_key, tmp_path):
    db_path = tmp_path / "test_subscriptions.db"
    token_store = TokenStore(str(db_path))
    token_store.init_db()
    return token_store


@pytest.fixture
def service(store):
    return SubscriptionService(store)


def _create_user(store, telegram_id="12345"):
    return store.create_user_token(
        telegram_id=telegram_id,
        spreadsheet_id="spreadsheet_1",
        access_token="access_1",
        refresh_token="refresh_1",
        token_expiry=time.time() + 3600,
        display_name="Test User",
        language="id",
    )


def test_state_transition_rules():
    """Valid state transition map covers required flows."""
    assert "pending" in VALID_TRANSITIONS["none"]
    assert "active" in VALID_TRANSITIONS["pending"]
    assert "expired" in VALID_TRANSITIONS["pending"]
    assert "grace" in VALID_TRANSITIONS["active"]
    assert "expired" in VALID_TRANSITIONS["active"]
    assert "cancelled" in VALID_TRANSITIONS["active"]
    assert "active" in VALID_TRANSITIONS["trial"]
    assert "expired" in VALID_TRANSITIONS["trial"]


def test_start_free_trial_creates_trial_subscription(service, store):
    _create_user(store, "111")
    sub = service.start_free_trial("111")

    assert sub is not None
    assert sub["status"] == SubscriptionState.TRIAL
    assert sub["plan"] == "monthly"
    assert sub["trial_end"] == pytest.approx(time.time() + 7 * 86400, abs=5)
    assert sub["auto_renew"] == 0


def test_start_free_trial_only_once(service, store):
    _create_user(store, "112")
    first = service.start_free_trial("112")
    assert first is not None

    second = service.start_free_trial("112")
    assert second is None


def test_create_subscription_pending(service, store):
    _create_user(store, "113")
    sub = service.create_subscription("113", "yearly")

    assert sub["status"] == SubscriptionState.PENDING
    assert sub["plan"] == "yearly"
    assert sub["end_date"] == pytest.approx(time.time() + 365 * 86400, abs=5)


def test_create_unknown_plan_raises(service, store):
    _create_user(store, "114")
    with pytest.raises(ValueError):
        service.create_subscription("114", "daily")


def test_invalid_transition_raises(service, store):
    _create_user(store, "115")
    service.create_subscription("115", "monthly")
    service.activate_subscription("115", "stars_x")

    # Active -> active is not a valid transition
    with pytest.raises(InvalidStateTransitionError):
        service.activate_subscription("115", "stars_y")


def test_activate_pending_subscription(service, store):
    _create_user(store, "116")
    pending = service.create_subscription("116", "monthly")
    active = service.activate_subscription("116", "stars_charge_123")

    assert active["status"] == SubscriptionState.ACTIVE
    assert active["id"] == pending["id"]
    assert active["payment_ref"] == "stars_charge_123"
    assert active["payment_method"] == "stars"
    assert active["auto_renew"] == 1

    invoices = store.get_invoices_by_user("116")
    assert len(invoices) == 1
    assert invoices[0]["status"] == "paid"
    assert invoices[0]["method"] == "stars"


def test_activate_trial_subscription(service, store):
    _create_user(store, "117")
    trial = service.start_free_trial("117")
    active = service.activate_subscription("117", "midtrans_order_456")

    assert active["status"] == SubscriptionState.ACTIVE
    assert active["id"] == trial["id"]
    assert active["payment_method"] == "midtrans"


def test_lifetime_never_expires(service, store):
    _create_user(store, "118")
    pending = service.create_subscription("118", "lifetime")
    active = service.activate_subscription("118", "stars_lifetime")

    assert active["plan"] == "lifetime"
    assert active["end_date"] is None
    assert active["auto_renew"] == 0

    # Simulate time passing far into the future.
    service._now = lambda: time.time() + 10 * 365 * 86400
    still = service.check_expiry("118")
    assert still["status"] == SubscriptionState.ACTIVE


def test_check_expiry_trial(service, store):
    _create_user(store, "119")
    sub = service.start_free_trial("119")

    # Not expired yet
    assert service.check_expiry("119")["status"] == SubscriptionState.TRIAL

    # Expire trial by manipulating trial_end in the DB
    store.update_subscription(sub["id"], trial_end=time.time() - 1)
    expired = service.check_expiry("119")
    assert expired["status"] == SubscriptionState.EXPIRED


def test_check_expiry_active(service, store):
    _create_user(store, "120")
    service.create_subscription("120", "monthly")
    service.activate_subscription("120", "stars_x")

    # Move end_date to the past
    sub = store.get_subscription("120")
    store.update_subscription(sub["id"], end_date=time.time() - 1)
    expired = service.check_expiry("120")
    assert expired["status"] == SubscriptionState.EXPIRED


def test_get_active_and_is_premium(service, store):
    _create_user(store, "121")
    assert service.get_active("121") is None
    assert service.is_premium("121") is False

    service.start_free_trial("121")
    assert service.get_active("121") is not None
    assert service.is_premium("121") is True


def test_cancel_subscription_disables_auto_renew(service, store):
    _create_user(store, "122")
    service.create_subscription("122", "monthly")
    service.activate_subscription("122", "stars_x")

    cancelled = service.cancel_subscription("122")
    assert cancelled["auto_renew"] == 0
    assert cancelled["status"] == SubscriptionState.ACTIVE
    assert service.is_premium("122") is True


def test_cancel_without_subscription_raises(service, store):
    _create_user(store, "123")
    with pytest.raises(InvalidStateTransitionError):
        service.cancel_subscription("123")
