"""Tests for natural language message handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.messages import handle_natural_message
from src.services.transaction_service import TransactionService
from src.services.budget_service import BudgetService


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Test"
    update.message = AsyncMock()
    update.message.text = "makan siang 50rb"
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SPREADSHEET_ID"}

    tx_service = MagicMock(spec=TransactionService)
    tx_service.create.return_value = {
        "row_id": 7,
        "was_duplicate": False,
        "today_total": {"expense": 50000, "income": 0, "count": 1},
    }
    tx_service.get_today.return_value = []

    budget_service = MagicMock(spec=BudgetService)
    budget_service.track_transaction.return_value = None

    context.bot_data = {
        "token_store": token_store,
        "tx_service": tx_service,
        "budget_service": budget_service,
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_natural_message_creates_transaction(fake_update, fake_context):
    await handle_natural_message(fake_update, fake_context)

    tx_service = fake_context.bot_data["tx_service"]
    tx_service.create.assert_called_once()
    args = tx_service.create.call_args[0]
    assert args[0] == "123"
    assert args[1] == "SPREADSHEET_ID"
    assert args[2] == "expense"
    assert args[3] == "Makanan"
    assert args[4] == 50000
    assert args[5] == "makan siang"

    fake_update.message.reply_text.assert_called_once()
    sent, kwargs = fake_update.message.reply_text.call_args
    assert "✅ Tercatat" in sent[0]
    assert "Makanan" in sent[0]
    assert "#7" in sent[0]
    assert "Rp 50,000" in sent[0]


@pytest.mark.asyncio
async def test_unparseable_shows_error(fake_update, fake_context):
    fake_update.message.text = "halo bot"
    await handle_natural_message(fake_update, fake_context)

    fake_update.message.reply_text.assert_called_once()
    sent, kwargs = fake_update.message.reply_text.call_args
    assert "Gak bisa parse" in sent[0]


@pytest.mark.asyncio
async def test_ambiguous_category_prompts_user(fake_update, fake_context):
    fake_update.message.text = "halo 100rb"
    await handle_natural_message(fake_update, fake_context)

    tx_service = fake_context.bot_data["tx_service"]
    tx_service.create.assert_not_called()
    fake_update.message.reply_text.assert_called_once()
    sent, kwargs = fake_update.message.reply_text.call_args
    assert "kategori kurang jelas" in sent[0]


@pytest.mark.asyncio
async def test_budget_warning_appended_to_response(fake_update, fake_context):
    budget_service = fake_context.bot_data["budget_service"]
    budget_service.track_transaction.return_value = "🚨 Budget Makanan sudah 100% terpakai!"

    await handle_natural_message(fake_update, fake_context)

    budget_service.track_transaction.assert_called_once_with(
        "123", "SPREADSHEET_ID", "Makanan", 50000, "2026-06"
    )
    fake_update.message.reply_text.assert_called_once()
    sent, kwargs = fake_update.message.reply_text.call_args
    assert "🚨" in sent[0]
    assert "100%" in sent[0]
