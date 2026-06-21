"""Test Telegram Stars payment flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.payments.stars import StarsPayment, pre_checkout_handler, successful_payment_handler
from src.services.subscription_service import SubscriptionService


@pytest.fixture
def mock_sub_service():
    return MagicMock(spec=SubscriptionService)


@pytest.fixture
def stars_payment(mock_sub_service):
    return StarsPayment(mock_sub_service)


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_chat = MagicMock()
    update.effective_chat.id = 456
    update.message = AsyncMock()
    update.callback_query = AsyncMock()
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot_data = {"subscription_service": MagicMock()}
    return context


def test_get_prices(stars_payment):
    prices = stars_payment.get_prices("monthly")
    assert len(prices) == 1
    assert prices[0].label == "Bulanan"
    assert prices[0].amount == 25000 * 100


@pytest.mark.asyncio
async def test_send_invoice_creates_pending_and_sends_invoice(stars_payment, mock_sub_service, fake_update, fake_context):
    mock_sub_service.create_subscription.return_value = {"id": 7}

    await stars_payment.send_invoice(fake_update, fake_context, "yearly")

    mock_sub_service.create_subscription.assert_called_once_with("123", "yearly")
    fake_context.bot.send_invoice.assert_awaited_once()
    kwargs = fake_context.bot.send_invoice.call_args.kwargs
    assert kwargs["chat_id"] == 456
    assert kwargs["currency"] == "XTR"
    assert kwargs["provider_token"] == ""
    assert kwargs["prices"][0].amount == 200000 * 100
    assert kwargs["payload"].startswith("yearly:123:")


@pytest.mark.asyncio
async def test_pre_checkout_handler_answers_ok():
    update = MagicMock()
    update.pre_checkout_query = AsyncMock()
    context = MagicMock()

    await pre_checkout_handler(update, context)

    update.pre_checkout_query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_successful_payment_handler_activates_subscription(fake_context):
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.successful_payment = MagicMock()
    update.effective_message.successful_payment.invoice_payload = "yearly:123:999999"
    update.effective_message.successful_payment.telegram_payment_charge_id = "charge_abc"
    update.message = AsyncMock()

    await successful_payment_handler(update, fake_context)

    fake_context.bot_data["subscription_service"].activate_subscription.assert_called_once_with(
        "123", "stars_charge_abc"
    )
    update.message.reply_text.assert_awaited_once()
