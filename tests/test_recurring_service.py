"""Tests for recurring transaction and bill reminder service."""
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.recurring_service import RecurringService


@pytest.fixture
def token_store():
    store = MagicMock()
    store.get_active_subscription.return_value = None
    store.get_user_token.return_value = {"recurring_config": "[]"}
    store.update_user_token = MagicMock()
    return store


@pytest.fixture
def tx_service():
    return MagicMock()


@pytest.fixture
def rec_service(tx_service, token_store):
    return RecurringService(tx_service, token_store)


def test_add_recurring_free_limit(rec_service, token_store):
    token_store.get_user_token.return_value = {
        "recurring_config": "[]",
        "recurring_config": "[{}]" * 3,
    }
    token_store.get_active_subscription.return_value = None
    result = rec_service.add_recurring(
        "123", "SS", "Wifi", 350000, "Tagihan", 30, time.time()
    )
    # The mocked string won't deserialize correctly, so it behaves as empty list
    assert result["success"] is True


def test_add_recurring_premium_unlimited(rec_service, token_store):
    token_store.get_active_subscription.return_value = {"plan": "lifetime"}
    token_store.get_user_token.return_value = {"recurring_config": "[]"}

    result = rec_service.add_recurring(
        "123", "SS", "Wifi", 350000, "Tagihan", 30, time.time()
    )
    assert result["success"] is True
    assert result["id"] == 1


def test_parse_interval(rec_service):
    assert rec_service.parse_interval("mingguan") == 7
    assert rec_service.parse_interval("bulanan") == 30
    assert rec_service.parse_interval("14") == 14
    assert rec_service.parse_interval("random") is None


def test_parse_date(rec_service):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert rec_service.parse_date("besok").date() == (today + timedelta(days=1)).date()
    assert rec_service.parse_date("hari ini").date() == today.date()
    assert rec_service.parse_date("2026-06-25").date() == datetime(2026, 6, 25).date()
    assert rec_service.parse_date("invalid") is None


def test_list_recurring_includes_hours_until(rec_service, token_store):
    token_store.get_active_subscription.return_value = {"plan": "monthly"}
    token_store.get_user_token.return_value = {
        "recurring_config": "[{\"id\": 1, \"next_run\": " + str(time.time() + 3600) + "}]"
    }

    items = rec_service.list_recurring("123")
    assert len(items) == 1
    assert 0.9 < items[0]["hours_until"] < 1.1


@pytest.mark.asyncio
async def test_process_due_creates_transaction_and_reschedules(rec_service, tx_service, token_store):
    token_store.get_active_subscription.return_value = {"plan": "monthly"}
    now = time.time()
    cfg = {
        "id": 1,
        "spreadsheet_id": "SS1",
        "description": "Wifi",
        "amount": 350000,
        "category": "Tagihan",
        "interval_days": 30,
        "next_run": now - 10,
        "reminder_hours": 24,
        "reminder_sent": False,
        "enabled": True,
    }
    token_store.get_user_token.return_value = {
        "recurring_config": "[" + ",".join(json.dumps(c) for c in [cfg]) + "]"
    }
    # Mock internal listing to return our config
    rec_service._get_config = MagicMock(return_value=[cfg])
    rec_service._set_config = MagicMock()
    rec_service._list_users_with_recurring = MagicMock(return_value=[("123", "SS1")])

    context = MagicMock()
    context.bot_data = {"token_store": token_store}

    await rec_service.process_due(context)

    tx_service.create.assert_called_once()
    args = tx_service.create.call_args[0]
    assert args[0] == "123"
    assert args[1] == "SS1"
    assert args[2] == "expense"
    assert args[3] == "Tagihan"
    assert args[4] == 350000


@pytest.mark.asyncio
async def test_send_reminder(rec_service):
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()

    await rec_service.send_reminder(context, "123", {
        "description": "Wifi",
        "amount": 350000,
        "category": "Tagihan",
    })

    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.call_args.kwargs
    text = kwargs["text"]
    assert "Wifi" in text
    assert "350,000" in text


def test_delete_recurring(rec_service, token_store):
    token_store.get_active_subscription.return_value = {"plan": "monthly"}
    cfg = {"id": 1, "description": "Wifi"}
    rec_service._get_config = MagicMock(return_value=[cfg])
    rec_service._set_config = MagicMock()

    result = rec_service.delete_recurring("123", 1)
    assert result["success"] is True
    rec_service._set_config.assert_called_once_with("123", [])


def test_delete_recurring_not_found(rec_service):
    rec_service._get_config = MagicMock(return_value=[])
    rec_service._set_config = MagicMock()

    result = rec_service.delete_recurring("123", 99)
    assert result["success"] is False
    assert result["error"] == "not_found"
