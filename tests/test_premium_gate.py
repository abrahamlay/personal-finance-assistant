"""Test premium_required decorator."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.middleware.premium_gate import premium_required


@pytest.fixture
def premium_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def callback_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.message = None
    update.callback_query = AsyncMock()
    return update


@pytest.fixture
def premium_context():
    context = MagicMock()
    sub_service = MagicMock()
    sub_service.is_premium.return_value = True
    context.bot_data = {"subscription_service": sub_service}
    return context


@pytest.fixture
def free_context():
    context = MagicMock()
    sub_service = MagicMock()
    sub_service.is_premium.return_value = False
    context.bot_data = {"subscription_service": sub_service}
    return context


@pytest.mark.asyncio
async def test_premium_user_allowed(premium_update, premium_context):
    handler = AsyncMock(return_value="ok")
    decorated = premium_required("Fitur Rahasia")(handler)

    result = await decorated(premium_update, premium_context)

    assert result == "ok"
    handler.assert_awaited_once_with(premium_update, premium_context)


@pytest.mark.asyncio
async def test_free_user_blocked_in_message(premium_update, free_context):
    handler = AsyncMock(return_value="ok")
    decorated = premium_required("Fitur Rahasia")(handler)

    result = await decorated(premium_update, free_context)

    assert result is None
    handler.assert_not_called()
    premium_update.message.reply_text.assert_awaited_once()
    args, kwargs = premium_update.message.reply_text.call_args
    assert "Fitur Rahasia" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_free_user_blocked_in_callback(callback_update, free_context):
    handler = AsyncMock()
    decorated = premium_required("Fitur Rahasia")(handler)

    await decorated(callback_update, free_context)

    handler.assert_not_called()
    callback_update.callback_query.edit_message_text.assert_awaited_once()
    args, kwargs = callback_update.callback_query.edit_message_text.call_args
    assert "Fitur Rahasia" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_no_subscription_service_treated_as_free(premium_update):
    handler = AsyncMock()
    decorated = premium_required("Fitur Rahasia")(handler)
    context = MagicMock()
    context.bot_data = {}

    await decorated(premium_update, context)

    handler.assert_not_called()
    premium_update.message.reply_text.assert_awaited_once()
