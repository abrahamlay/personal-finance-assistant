"""Premium command and callback handlers."""
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.services.subscription_service import SubscriptionService


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show plan selection with inline keyboard."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Bulanan — Rp 25.000", callback_data="premium_plan_monthly")],
        [InlineKeyboardButton("📆 Tahunan — Rp 200.000 (hemat 33%)", callback_data="premium_plan_yearly")],
        [InlineKeyboardButton("👑 Seumur Hidup — Rp 750.000", callback_data="premium_plan_lifetime")],
        [InlineKeyboardButton("💳 Bayar via Telegram Stars", callback_data="premium_pay_stars")],
        [InlineKeyboardButton("📱 Bayar via QRIS / GoPay", callback_data="premium_midtrans_qris")],
    ])
    text = (
        "⭐ *Upgrade ke Premium*\n\n"
        "Pilih paket yang cocok buat kamu:\n"
        "• 📅 Bulanan — Rp 25.000\n"
        "• 📆 Tahunan — Rp 200.000 (hemat 33%)\n"
        "• 👑 Seumur Hidup — Rp 750.000\n\n"
        "Pilih paket dulu, lalu pilih metode pembayaran."
    )
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium inline buttons: plan selection and payment method."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    data = query.data
    sub_service: SubscriptionService = context.bot_data["subscription_service"]

    if data.startswith("premium_plan_"):
        plan = data.replace("premium_plan_", "")
        context.user_data["premium_plan"] = plan
        plan_info = SubscriptionService.PLANS.get(plan, {})
        text = (
            f"⭐ *Premium {plan_info.get('name', plan.capitalize())}*\n"
            f"Harga: Rp {plan_info.get('price', 0):,}\n\n"
            "Sekarang pilih metode pembayaran:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Bayar via Telegram Stars", callback_data="premium_pay_stars")],
            [InlineKeyboardButton("📱 Bayar via QRIS / GoPay", callback_data="premium_midtrans_qris")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="premium_back")],
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    plan = context.user_data.get("premium_plan")
    if data in ("premium_pay_stars", "premium_midtrans_qris") and not plan:
        await query.edit_message_text(
            "⚠️ Pilih paket dulu ya. Ketik /premium untuk memilih.",
            parse_mode="Markdown",
        )
        return

    if data == "premium_pay_stars":
        stars_payment = context.bot_data["stars_payment"]
        await stars_payment.send_invoice(update, context, plan)
        return

    if data == "premium_midtrans_qris":
        midtrans_payment = context.bot_data["midtrans_payment"]
        order_id = f"order_{user_id}_{plan}_{int(time.time())}"
        amount = SubscriptionService.PLANS[plan]["price"]
        result = midtrans_payment.create_charge(order_id, amount, plan, user_id)
        payment_url = result.get("redirect_url") or result.get("token", "")
        await query.edit_message_text(
            f"📱 *Pembayaran {plan.capitalize()}*\n\n"
            f"Klik link ini buat bayar:\n{payment_url}\n\n"
            "Setelah bayar, status Premium kamu akan otomatis aktif.",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        return

    if data == "premium_back":
        await premium_command(update, context)
        return

    if data in ("premium_upgrade", "premium_plans"):
        await premium_command(update, context)
        return


async def statuspremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription status, sisa hari, plan, invoice history."""
    user_id = str(update.effective_user.id)
    sub_service: SubscriptionService = context.bot_data["subscription_service"]
    token_store = context.bot_data["token_store"]

    sub = sub_service.get_active(user_id)
    invoices = token_store.get_invoices_by_user(user_id)

    if sub is None:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Upgrade ke Premium", callback_data="premium_upgrade")],
        ])
        await update.message.reply_text(
            "🔒 Kamu belum berlangganan Premium.\n"
            "Upgrade sekarang buat akses semua fitur!",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    plan = sub.get("plan", "-")
    status = sub.get("status", "-")
    plan_info = SubscriptionService.PLANS.get(plan, {})

    remaining_text = "tidak terbatas"
    if plan != "lifetime":
        end_date = sub.get("end_date")
        if end_date:
            days_left = max(0, int((end_date - time.time()) / 86400))
            remaining_text = f"{days_left} hari lagi"

    lines = [
        "⭐ *Status Langganan*",
        f"Paket: {plan_info.get('name', plan.capitalize())}",
        f"Status: {status.capitalize()}",
        f"Sisa waktu: {remaining_text}",
    ]
    if sub.get("auto_renew"):
        lines.append("Auto-renew: Aktif")
    else:
        lines.append("Auto-renew: Nonaktif")

    if invoices:
        lines.append("\n*Riwayat Pembayaran:*")
        for inv in invoices[:5]:
            lines.append(
                f"• Rp {inv.get('amount', 0):,} — {inv.get('method', '-')} "
                f"({inv.get('status', '-')})"
            )
    else:
        lines.append("\nBelum ada riwayat pembayaran.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable auto-renew. Subscription stays active until period end."""
    user_id = str(update.effective_user.id)
    sub_service: SubscriptionService = context.bot_data["subscription_service"]

    try:
        sub_service.cancel_subscription(user_id)
        await update.message.reply_text(
            "✅ Auto-renew sudah dinonaktifkan.\n"
            "Langganan Premium kamu tetap aktif sampai masa berlaku habis.",
            parse_mode="Markdown",
        )
    except Exception:
        await update.message.reply_text(
            "⚠️ Kamu belum memiliki langganan Premium yang aktif.",
            parse_mode="Markdown",
        )
