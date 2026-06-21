"""Tests for /tagihan and /reminder handlers."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers import recurring


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    update.callback_query = AsyncMock()
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SS1"}

    rec_service = MagicMock()
    rec_service.add_recurring.return_value = {"success": True, "id": 1}
    rec_service.list_recurring.return_value = [
        {
            "id": 1,
            "description": "Wifi",
            "amount": 350000,
            "category": "Tagihan",
            "interval_days": 30,
            "next_run": 1750000000.0,
            "hours_until": 72.0,
            "enabled": True,
        }
    ]
    rec_service.parse_interval.return_value = 30
    rec_service.parse_date.return_value = MagicMock()
    rec_service.parse_date.return_value.timestamp = MagicMock(return_value=1750000000.0)

    context.bot_data = {
        "token_store": token_store,
        "recurring_service": rec_service,
        "subscription_service": MagicMock(),
    }
    context.user_data = {"recurring": {}}
    return context


@pytest.mark.asyncio
async def test_tagihan_command_starts_conversation(fake_update, fake_context):
    state = await recurring.tagihan_command(fake_update, fake_context)
    assert state == recurring.DESC
    fake_update.message.reply_text.assert_awaited_once()
    assert "Tambah Tagihan" in fake_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_tagihan_description_asks_amount(fake_update, fake_context):
    fake_update.message.text = "Wifi"
    state = await recurring.tagihan_description(fake_update, fake_context)
    assert state == recurring.AMOUNT
    assert fake_context.user_data["recurring"]["description"] == "Wifi"


@pytest.mark.asyncio
async def test_tagihan_amount_parses_value(fake_update, fake_context):
    fake_update.message.text = "350rb"
    state = await recurring.tagihan_amount(fake_update, fake_context)
    assert state == recurring.CATEGORY
    assert fake_context.user_data["recurring"]["amount"] == 350000


@pytest.mark.asyncio
async def test_tagihan_amount_invalid_retries(fake_update, fake_context):
    fake_update.message.text = "gratis"
    state = await recurring.tagihan_amount(fake_update, fake_context)
    assert state == recurring.AMOUNT


@pytest.mark.asyncio
async def test_tagihan_category_asks_interval(fake_update, fake_context):
    fake_context.user_data["recurring"] = {"amount": 350000}
    fake_update.message.text = "Tagihan"
    state = await recurring.tagihan_category(fake_update, fake_context)
    assert state == recurring.INTERVAL
    assert fake_context.user_data["recurring"]["category"] == "Tagihan"


@pytest.mark.asyncio
async def test_tagihan_interval_asks_date(fake_update, fake_context):
    fake_context.user_data["recurring"] = {"description": "Wifi", "amount": 350000, "category": "Tagihan"}
    query = fake_update.callback_query
    query.data = "recur:interval:bulanan"

    state = await recurring.tagihan_interval(fake_update, fake_context)

    assert state == recurring.DATE
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_tagihan_confirm_saves_config(fake_update, fake_context):
    fake_context.user_data["recurring"] = {
        "description": "Wifi",
        "amount": 350000,
        "category": "Tagihan",
        "interval_days": 30,
        "next_run": 1750000000.0,
        "reminder_hours": 24,
    }
    query = fake_update.callback_query
    query.data = "recur:confirm:yes"

    state = await recurring.tagihan_confirm(fake_update, fake_context)

    assert state == -1  # ConversationHandler.END
    fake_context.bot_data["recurring_service"].add_recurring.assert_called_once()
    query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_tagihan_confirm_cancel(fake_update, fake_context):
    fake_context.user_data["recurring"] = {"description": "Wifi"}
    query = fake_update.callback_query
    query.data = "recur:confirm:no"

    state = await recurring.tagihan_confirm(fake_update, fake_context)

    assert state == -1
    fake_context.bot_data["recurring_service"].add_recurring.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_command_lists_bills(fake_update, fake_context):
    await recurring.reminder_command(fake_update, fake_context)

    fake_update.message.reply_text.assert_awaited_once()
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Wifi" in text
    assert "350,000" in text
