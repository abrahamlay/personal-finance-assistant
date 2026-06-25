"""Tests for OCR photo handler and callbacks."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.handlers.messages import handle_photo, ocr_callback


@pytest.fixture
def fake_photo_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    update.message.photo = [MagicMock(file_id="file1"), MagicMock(file_id="file2")]
    update.callback_query = None
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    context.bot = MagicMock()
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake"))
    context.bot.get_file = AsyncMock(return_value=file_mock)

    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SS1", "access_token": "test_access_token"}
    token_store.get_active_subscription.return_value = {"plan": "monthly"}

    ocr_service = MagicMock()
    ocr_service.scan = AsyncMock(return_value={
        "merchant": "Indomaret",
        "total_amount": 50000,
        "items": [{"name": "Mineral", "qty": 1, "price": 5000}],
        "category_suggestion": "Belanja",
        "confidence": 0.9,
    })

    tx_service = MagicMock()
    tx_service.create.return_value = {
        "row_id": 8,
        "was_duplicate": False,
        "today_total": {"expense": 50000, "count": 1},
    }

    context.bot_data = {
        "token_store": token_store,
        "ocr_service": ocr_service,
        "tx_service": tx_service,
        "budget_service": None,
        "subscription_service": MagicMock(),
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_handle_photo_premium_user_shows_scan_result(fake_photo_update, fake_context):
    await handle_photo(fake_photo_update, fake_context)

    fake_context.bot_data["ocr_service"].scan.assert_awaited_once_with("123", b"fake")
    fake_photo_update.message.reply_text.assert_awaited_once()
    args, kwargs = fake_photo_update.message.reply_text.call_args
    assert "Indomaret" in args[0]
    assert "Rp 50,000" in args[0]
    assert "Mau simpan" in args[0]
    assert kwargs.get("reply_markup") is not None
    buttons = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
    assert any("Edit Manual" in text for text in buttons)


@pytest.mark.asyncio
async def test_handle_photo_low_confidence_prompts_user(fake_photo_update, fake_context):
    fake_context.bot_data["ocr_service"].scan = AsyncMock(return_value={
        "merchant": "Unknown",
        "total_amount": 10000,
        "items": [],
        "category_suggestion": "Lainnya",
        "confidence": 0.4,
    })

    await handle_photo(fake_photo_update, fake_context)

    args, _ = fake_photo_update.message.reply_text.call_args
    assert "Gak yakin" in args[0]
    assert "Unknown" in args[0]


@pytest.mark.asyncio
async def test_ocr_callback_save_creates_transaction():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = None
    query = AsyncMock()
    query.data = "ocr:save"
    update.callback_query = query

    context = MagicMock()
    context.user_data = {
        "ocr_result": {
            "merchant": "Indomaret",
            "total_amount": 50000,
            "category_suggestion": "Belanja",
        }
    }
    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SS1"}
    tx_service = MagicMock()
    tx_service.create.return_value = {
        "row_id": 9,
        "was_duplicate": False,
        "today_total": {"expense": 50000, "count": 1},
    }
    context.bot_data = {"token_store": token_store, "tx_service": tx_service, "budget_service": None}

    await ocr_callback(update, context)

    tx_service.create.assert_called_once()
    query.edit_message_text.assert_awaited_once()
    text = query.edit_message_text.call_args[0][0]
    assert "Tercatat" in text


@pytest.mark.asyncio
async def test_ocr_callback_manual_prompts_text_input():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = None
    query = AsyncMock()
    query.data = "ocr:manual"
    update.callback_query = query

    context = MagicMock()
    context.user_data = {"ocr_result": {"total_amount": 50000}}
    context.bot_data = {"token_store": MagicMock(), "tx_service": MagicMock()}

    await ocr_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    assert "Ketik transaksi manual" in query.edit_message_text.call_args[0][0]
