import sqlite3
import time

import pytest
from cryptography.fernet import Fernet

from src.auth.token_store import TokenStore


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
    db_path = tmp_path / "test_token_store.db"
    token_store = TokenStore(str(db_path))
    token_store.init_db()
    return token_store


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


def test_init_db_creates_tables(store):
    with store._connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "user_tokens" in tables
    assert "subscriptions" in tables
    assert "invoices" in tables


def test_user_token_crud(store):
    user = _create_user(store, "111")
    assert user is not None
    assert user["telegram_id"] == "111"
    assert user["spreadsheet_id"] == "spreadsheet_1"
    assert user["access_token"] == "access_1"
    # refresh_token is stored encrypted and returned decrypted
    assert user["refresh_token"] == "refresh_1"

    retrieved = store.get_user_token("111")
    assert retrieved["refresh_token"] == "refresh_1"

    updated = store.update_user_token("111", refresh_token="new_refresh")
    assert updated["refresh_token"] == "new_refresh"

    deleted = store.delete_user_token("111")
    assert deleted is True
    assert store.get_user_token("111") is None


def test_subscription_crud(store):
    _create_user(store, "222")
    now = time.time()
    sub = store.create_subscription(
        telegram_id="222",
        plan="monthly",
        status="active",
        start_date=now,
        end_date=now + 30 * 24 * 3600,
        payment_method="midtrans",
        payment_ref="order-123",
        auto_renew=True,
    )
    assert sub is not None
    assert sub["telegram_id"] == "222"
    assert sub["plan"] == "monthly"
    assert sub["status"] == "active"
    assert sub["auto_renew"] == 1

    retrieved = store.get_subscription("222")
    assert retrieved["id"] == sub["id"]

    updated = store.update_subscription_status(sub["id"], "expired")
    assert updated["status"] == "expired"


def test_active_subscription(store):
    _create_user(store, "333")
    now = time.time()
    active = store.create_subscription(
        telegram_id="333",
        plan="monthly",
        status="active",
        start_date=now,
        end_date=now + 30 * 24 * 3600,
    )
    expired = store.create_subscription(
        telegram_id="333",
        plan="monthly",
        status="active",
        start_date=now - 60 * 24 * 3600,
        end_date=now - 1,
    )

    result = store.get_active_subscription("333")
    assert result is not None
    assert result["id"] == active["id"]
    assert result["id"] != expired["id"]


def test_invoice_crud(store):
    _create_user(store, "444")
    sub = store.create_subscription(
        telegram_id="444",
        plan="yearly",
        status="active",
        start_date=time.time(),
        end_date=time.time() + 365 * 24 * 3600,
    )
    invoice = store.create_invoice(
        telegram_id="444",
        subscription_id=sub["id"],
        amount=250000,
        method="midtrans",
        status="paid",
        payment_ref="inv-123",
        raw_response="{}",
    )
    assert invoice["telegram_id"] == "444"
    assert invoice["amount"] == 250000

    invoices = store.get_invoices_by_user("444")
    assert len(invoices) == 1
    assert invoices[0]["id"] == invoice["id"]


def test_subscription_check_constraints(store):
    _create_user(store, "555")
    with pytest.raises(sqlite3.IntegrityError):
        store.create_subscription(
            telegram_id="555",
            plan="invalid_plan",
            status="active",
            start_date=time.time(),
            end_date=time.time() + 3600,
        )

    with pytest.raises(sqlite3.IntegrityError):
        store.create_subscription(
            telegram_id="555",
            plan="monthly",
            status="unknown_status",
            start_date=time.time(),
            end_date=time.time() + 3600,
        )


def test_foreign_key_constraints(store):
    with pytest.raises(sqlite3.IntegrityError):
        store.create_subscription(
            telegram_id="no_such_user",
            plan="monthly",
            status="active",
            start_date=time.time(),
            end_date=time.time() + 3600,
        )

    with pytest.raises(sqlite3.IntegrityError):
        store.create_invoice(
            telegram_id="no_such_user",
            subscription_id=1,
            amount=1000,
            method="midtrans",
            status="paid",
        )


def test_delete_user_cascade_via_fk_blocked(store):
    # SQLite FK does not automatically cascade here, but deleting a referenced
    # user while subscriptions exist should fail unless subscriptions are gone.
    _create_user(store, "666")
    store.create_subscription(
        telegram_id="666",
        plan="monthly",
        status="active",
        start_date=time.time(),
        end_date=time.time() + 3600,
    )
    # Deleting user should fail because a subscription references it.
    with pytest.raises(sqlite3.IntegrityError):
        store.delete_user_token("666")


def test_user_token_ocr_and_recurring_columns(store):
    _create_user(store, "777")
    updated = store.update_user_token(
        "777",
        ocr_usage='{"ocr:777:2026-06": 1}',
        recurring_config='[{"id": 1}]',
    )
    assert updated["ocr_usage"] == '{"ocr:777:2026-06": 1}'
    assert updated["recurring_config"] == '[{"id": 1}]'


def test_init_db_migration_runs_without_error(valid_key, tmp_path):
    db_path = tmp_path / "migration_test.db"
    store = TokenStore(str(db_path))
    store.init_db()
    # Second init should be idempotent (duplicate columns ignored)
    store.init_db()
    user = _create_user(store, "888")
    assert "ocr_usage" in user
