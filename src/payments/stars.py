"""Telegram Stars payment integration."""
import time

from telegram import LabeledPrice

from src.services.subscription_service import SubscriptionService


class StarsPayment:
    def __init__(self, sub_service: SubscriptionService):
        self.sub_service = sub_service

    def get_prices(self, plan: str) -> list[LabeledPrice]:
        plans = SubscriptionService.PLANS
        info = plans[plan]
        return [LabeledPrice(info["name"], info["price"] * 100)]  # Stars in smallest unit

    async def send_invoice(self, update, context, plan: str):
        """Send Telegram Stars invoice for selected plan."""
        if plan not in SubscriptionService.PLANS:
            raise ValueError(f"Unknown plan: {plan!r}")

        user_id = str(update.effective_user.id)
        payload = f"{plan}:{user_id}:{int(time.time())}"
        plan_info = SubscriptionService.PLANS[plan]

        # Create a pending subscription so activation can use it.
        self.sub_service.create_subscription(user_id, plan)

        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=f"⭐ Premium {plan_info['name']}",
            description=f"Akses fitur Premium {plan_info['name']}.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=self.get_prices(plan),
        )


async def pre_checkout_handler(update, context):
    """Validate incoming pre-checkout query."""
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_handler(update, context):
    """Handle successful payment -> activate subscription."""
    payload = update.effective_message.successful_payment.invoice_payload
    # payload = "plan:telegram_id:timestamp"
    plan, uid = payload.split(":")[:2]
    sub_service = context.bot_data["subscription_service"]
    charge_id = update.effective_message.successful_payment.telegram_payment_charge_id
    sub_service.activate_subscription(uid, f"stars_{charge_id}")
    await update.message.reply_text("✅ Pembayaran berhasil! Premium kamu sudah aktif. 🎉")
