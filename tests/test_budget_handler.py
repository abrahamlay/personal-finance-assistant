"""Tests for /anggaran handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import InlineKeyboardMarkup

from src.handlers.budgets import (
    anggaran_command,
    budget_category,
    budget_amount,
    budget_period,
    budget_confirm,
    BUDGET_CATEGORY,
    BUDGET_AMOUNT,
    BUDGET_PERIOD,
    BUDGET_CONFIRM,
    ConversationHandler,
)
from src.services.budget_service import BudgetService
from src.sheets.categories import SheetsCategories
from src.auth.token_store import TokenStore


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Test"
    update.message = AsyncMock()
    update.message.text = "/anggaran"
    update.callback_query = AsyncMock()
    update.callback_query.data = "budget:set"
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock(spec=TokenStore)
    token_store.get_user_token.return_value = {"spreadsheet_id": "SPREADSHEET_ID"}

    sheets_budgets = MagicMock()
    sheets_budgets.list_all.return_value = [
        {"id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 400000, "periode": "bulanan"}
    ]
    sheets_budgets.set.return_value = {"success": True, "id": "1"}
    sheets_budgets.get.return_value = {
        "id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 400000
    }
    sheets_budgets.delete.return_value = True

    budget_service = MagicMock(spec=BudgetService)
    budget_service.budgets = sheets_budgets
    budget_service.get_usage.return_value = {
        "found": True, "kategori": "Makanan", "jumlah_bulan": 500000, "terpakai": 400000, "percentage": 80.0
    }
    budget_service.set_budget.return_value = {"success": True, "id": "1"}

    sheets_categories = MagicMock(spec=SheetsCategories)
    sheets_categories.list_all.return_value = [
        {"id": "1", "nama": "Makanan", "tipe": "expense", "is_default": True, "icon": "🍔"},
        {"id": "2", "nama": "Transportasi", "tipe": "expense", "is_default": True, "icon": "🚗"},
    ]

    context.bot_data = {
        "token_store": token_store,
        "budget_service": budget_service,
        "sheets_categories": sheets_categories,
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_anggaran_command_shows_budgets(fake_update, fake_context):
    state = await anggaran_command(fake_update, fake_context)

    assert state == BUDGET_CATEGORY
    fake_update.message.reply_text.assert_called_once()
    text, kwargs = fake_update.message.reply_text.call_args
    assert "Makanan" in text[0]
    assert "80%" in text[0]
    assert "⚠️" in text[0]
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_budget_category_set_asks_amount(fake_update, fake_context):
    fake_update.callback_query.data = "budget:cat:1:Makanan"
    state = await budget_category(fake_update, fake_context)

    assert state == BUDGET_AMOUNT
    fake_update.callback_query.edit_message_text.assert_called_once()
    text = fake_update.callback_query.edit_message_text.call_args[0][0]
    assert "Makanan" in text
    assert "berapa" in text.lower()


@pytest.mark.asyncio
async def test_budget_amount_parses_and_asks_period(fake_update, fake_context):
    fake_update.message.text = "500rb"
    state = await budget_amount(fake_update, fake_context)

    assert state == BUDGET_PERIOD
    assert fake_context.user_data["budget_amount"] == 500000
    fake_update.message.reply_text.assert_called_once()
    text, kwargs = fake_update.message.reply_text.call_args
    assert "periode" in text[0].lower()
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_budget_period_shows_confirmation(fake_update, fake_context):
    fake_context.user_data["budget_category"] = "Makanan"
    fake_context.user_data["budget_amount"] = 500000
    fake_update.callback_query.data = "budget:period:bulanan"

    state = await budget_period(fake_update, fake_context)

    assert state == BUDGET_CONFIRM
    fake_update.callback_query.edit_message_text.assert_called_once()
    text = fake_update.callback_query.edit_message_text.call_args[0][0]
    assert "Konfirmasi" in text
    assert "Makanan" in text
    assert "Rp 500k" in text


@pytest.mark.asyncio
async def test_budget_confirm_saves_budget(fake_update, fake_context):
    fake_context.user_data["budget_category"] = "Makanan"
    fake_context.user_data["budget_amount"] = 500000
    fake_context.user_data["budget_period"] = "bulanan"
    fake_update.callback_query.data = "budget:confirm:yes"

    state = await budget_confirm(fake_update, fake_context)

    assert state == ConversationHandler.END
    budget_service = fake_context.bot_data["budget_service"]
    budget_service.set_budget.assert_called_once()
    args = budget_service.set_budget.call_args[0]
    assert args[0] == "123"
    assert args[1] == "SPREADSHEET_ID"
    assert args[2] == "Makanan"
    assert args[3] == 500000
    assert args[4] == "bulanan"
    fake_update.callback_query.edit_message_text.assert_called_once()
    assert "disimpan" in fake_update.callback_query.edit_message_text.call_args[0][0]
