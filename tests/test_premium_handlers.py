"""Test /premium, /statuspremium, /cancel handlers and premium callbacks."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.handlers import premium
from src.services.subscription_service import SubscriptionService


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
    context.bot_data = {
        "subscription_service": MagicMock(spec=SubscriptionService),
        "token_store": MagicMock(),
        "stars_payment": AsyncMock(),
        "midtrans_payment": MagicMock(),
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_premium_command_shows_plans_and_payment_methods(fake_update, fake_context):
    await premium.premium_command(fake_update, fake_context)

    fake_update.message.reply_text.assert_awaited_once()
    args, kwargs = fake_update.message.reply_text.call_args
    text = args[0]
    assert "Bulanan" in text
    assert "Tahunan" in text
    assert "Seumur Hidup" in text
    reply_markup = kwargs["reply_markup"]
    buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert "premium_plan_monthly" in buttons
    assert "premium_plan_yearly" in buttons
    assert "premium_plan_lifetime" in buttons
    assert "premium_pay_stars" in buttons
    assert "premium_midtrans_qris" in buttons


@pytest.mark.asyncio
async def test_premium_callback_selects_plan(fake_update, fake_context):
    query = fake_update.callback_query
    query.data = "premium_plan_yearly"

    await premium.premium_callback(fake_update, fake_context)

    query.answer.assert_awaited_once()
    assert fake_context.user_data["premium_plan"] == "yearly"
    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.call_args
    assert "Tahunan" in args[0]


@pytest.mark.asyncio
async def test_premium_callback_stars_requires_plan(fake_update, fake_context):
    query = fake_update.callback_query
    query.data = "premium_pay_stars"

    await premium.premium_callback(fake_update, fake_context)

    fake_context.bot_data["stars_payment"].send_invoice.assert_not_called()
    query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_premium_callback_stars_sends_invoice(fake_update, fake_context):
    query = fake_update.callback_query
    query.data = "premium_pay_stars"
    fake_context.user_data["premium_plan"] = "monthly"

    await premium.premium_callback(fake_update, fake_context)

    fake_context.bot_data["stars_payment"].send_invoice.assert_awaited_once_with(
        fake_update, fake_context, "monthly"
    )


@pytest.mark.asyncio
async def test_premium_callback_midtrans_sends_payment_url(fake_update, fake_context):
    query = fake_update.callback_query
    query.data = "premium_midtrans_qris"
    fake_context.user_data["premium_plan"] = "monthly"
    fake_context.bot_data["midtrans_payment"].create_charge.return_value = {
        "redirect_url": "https://pay.test/abc"
    }

    await premium.premium_callback(fake_update, fake_context)

    fake_context.bot_data["midtrans_payment"].create_charge.assert_called_once()
    query.edit_message_text.assert_awaited_once()
    args, _ = query.edit_message_text.call_args
    assert "https://pay.test/abc" in args[0]


@pytest.mark.asyncio
async def test_statuspremium_active_subscription(fake_update, fake_context):
    sub_service = fake_context.bot_data["subscription_service"]
    sub_service.get_active.return_value = {
        "plan": "monthly",
        "status": "active",
        "end_date": __import__("time").time() + 10 * 86400,
        "auto_renew": 1,
    }
    fake_context.bot_data["token_store"].get_invoices_by_user.return_value = [
        {"amount": 25000, "method": "stars", "status": "paid"}
    ]

    await premium.statuspremium_command(fake_update, fake_context)

    fake_update.message.reply_text.assert_awaited_once()
    args, _ = fake_update.message.reply_text.call_args
    assert "Bulanan" in args[0]
    assert "hari lagi" in args[0]
    assert "stars" in args[0]


@pytest.mark.asyncio
async def test_statuspremium_no_subscription(fake_update, fake_context):
    fake_context.bot_data["subscription_service"].get_active.return_value = None
    fake_context.bot_data["token_store"].get_invoices_by_user.return_value = []

    await premium.statuspremium_command(fake_update, fake_context)

    fake_update.message.reply_text.assert_awaited_once()
    args, kwargs = fake_update.message.reply_text.call_args
    assert "belum berlangganan" in args[0]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cancel_command_disables_auto_renew(fake_update, fake_context):
    sub_service = fake_context.bot_data["subscription_service"]
    sub_service.cancel_subscription.return_value = {"auto_renew": 0}

    await premium.cancel_command(fake_update, fake_context)

    sub_service.cancel_subscription.assert_called_once_with("123")
    fake_update.message.reply_text.assert_awaited_once()
    args, _ = fake_update.message.reply_text.call_args
    assert "Auto-renew" in args[0]


@pytest.mark.asyncio
async def test_cancel_command_without_subscription(fake_update, fake_context):
    sub_service = fake_context.bot_data["subscription_service"]
    sub_service.cancel_subscription.side_effect = Exception("no subscription")

    await premium.cancel_command(fake_update, fake_context)

    fake_update.message.reply_text.assert_awaited_once()
    args, _ = fake_update.message.reply_text.call_args
    assert "belum memiliki" in args[0]
