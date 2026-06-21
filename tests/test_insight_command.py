"""Tests for /insight command handler."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers.commands import insight_command


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SS1"}

    tx_service = MagicMock()
    tx_service.get_by_month.return_value = [
        {"id": "1", "tipe": "expense", "jumlah": 100000, "kategori": "Makanan", "tanggal": "2026-06-01"},
    ]

    insight_service = AsyncMock()
    insight_service.analyze.return_value = "💡 *Insight Keuangan*\n\nKamu hemat!"

    context.bot_data = {
        "token_store": token_store,
        "tx_service": tx_service,
        "insight_service": insight_service,
        "sheets_categories": None,
        "subscription_service": MagicMock(),
    }
    return context


@pytest.mark.asyncio
async def test_insight_command_sends_analysis(fake_update, fake_context):
    await insight_command(fake_update, fake_context)

    fake_context.bot_data["insight_service"].analyze.assert_awaited_once()
    assert fake_update.message.reply_text.call_count == 2
    first_call = fake_update.message.reply_text.call_args_list[0]
    assert "Sedang menganalisis" in first_call[0][0]
    second_call = fake_update.message.reply_text.call_args_list[1]
    assert "Insight Keuangan" in second_call[0][0]
