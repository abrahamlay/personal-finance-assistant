"""Tests for centralized error handler decorator."""
from unittest.mock import AsyncMock, MagicMock

import gspread
import pytest

from src.services.error_handler import bot_error_handler, _get_user_message
from src.sheets.client import SheetNotFoundError, SheetAuthError


@pytest.mark.asyncio
async def test_handler_routes_sheet_not_found_to_friendly_message():
    @bot_error_handler
    async def handler(update, context):
        raise SheetNotFoundError("missing")

    update = MagicMock()
    update.message = AsyncMock()
    update.callback_query = None

    await handler(update, {})

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert "gak ketemu" in text


@pytest.mark.asyncio
async def test_handler_routes_auth_error_to_login_prompt():
    @bot_error_handler
    async def handler(update, context):
        raise SheetAuthError("expired")

    update = MagicMock()
    update.message = AsyncMock()
    update.callback_query = None

    await handler(update, {})

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert "/login" in text


@pytest.mark.asyncio
async def test_handler_uses_callback_query_when_requested():
    @bot_error_handler(reply_target="callback_query")
    async def handler(update, context):
        raise ValueError("boom")

    update = MagicMock()
    update.message = AsyncMock()
    update.callback_query = AsyncMock()

    await handler(update, {})

    update.message.reply_text.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_calls_wrapped_function_on_success():
    wrapped = AsyncMock(return_value="ok")
    decorated = bot_error_handler(wrapped)

    update = MagicMock()
    update.message = AsyncMock()

    result = await decorated(update, {})
    assert result == "ok"
    wrapped.assert_awaited_once_with(update, {})


def test_get_user_message_gspread_api_error():
    exc = gspread.exceptions.APIError(MagicMock())
    msg = _get_user_message(exc)
    assert "Google Sheets" in msg or "Sistem sibuk" in msg


def test_get_user_message_unknown_error():
    msg = _get_user_message(ValueError("something weird"))
    assert "kendala teknis" in msg
