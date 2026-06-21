"""Recurring transaction and bill reminder handlers."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from src.auth.token_store import TokenStore
from src.services.recurring_service import RecurringService
from src.services.parser_service import normalize_amount
from src.middleware import require_login, premium_required
from src.services.error_handler import bot_error_handler

(DESC, AMOUNT, CATEGORY, INTERVAL, DATE, REMINDER, CONFIRM) = range(200, 207)


@require_login
@premium_required("Tagihan & Pengingat")
@bot_error_handler
async def tagihan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start /tagihan conversation to add a recurring bill."""
    await update.message.reply_text(
        "🔄 *Tambah Tagihan Rutin*\n\n"
        "Ketik nama tagihan. Contoh: `Wifi IndiHome`, `Spotify`, `Listrik`",
        parse_mode="Markdown",
    )
    context.user_data["recurring"] = {}
    return DESC


@bot_error_handler
async def tagihan_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture description, ask amount."""
    context.user_data["recurring"]["description"] = update.message.text.strip()
    await update.message.reply_text(
        "💰 Berapa jumlah tagihan?\nContoh: `350000` atau `350rb`",
        parse_mode="Markdown",
    )
    return AMOUNT


@bot_error_handler
async def tagihan_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse amount, ask category."""
    text = update.message.text.strip()
    amount, _ = normalize_amount(text)
    if amount == 0:
        await update.message.reply_text(
            "⚠️ Gak bisa baca jumlah. Coba lagi ya. Contoh: `350000` atau `350rb`",
            parse_mode="Markdown",
        )
        return AMOUNT

    context.user_data["recurring"]["amount"] = amount
    await update.message.reply_text(
        "📂 Ketik kategori tagihan. Contoh: `Tagihan`, `Hiburan`, `Belanja`",
    )
    return CATEGORY


@bot_error_handler
async def tagihan_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture category, ask interval."""
    context.user_data["recurring"]["category"] = update.message.text.strip()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Mingguan", callback_data="recur:interval:mingguan")],
        [InlineKeyboardButton("📆 Bulanan", callback_data="recur:interval:bulanan")],
    ])
    await update.message.reply_text(
        "🗓️ Pilih frekuensi tagihan:",
        reply_markup=keyboard,
    )
    return INTERVAL


@bot_error_handler
async def tagihan_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture interval from callback, ask first due date."""
    query = update.callback_query
    await query.answer()

    rec_service: RecurringService = context.bot_data["recurring_service"]
    interval_text = query.data.replace("recur:interval:", "")
    interval_days = rec_service.parse_interval(interval_text)
    if interval_days is None:
        await query.edit_message_text(
            "⚠️ Frekuensi tidak dikenali. Ketik /tagihan untuk ulang."
        )
        return ConversationHandler.END

    context.user_data["recurring"]["interval_days"] = interval_days
    await query.edit_message_text(
        "📅 Kapan pertama kali jatuh tempo?\n"
        "Ketik `besok`, `hari ini`, atau tanggal `YYYY-MM-DD`.",
    )
    return DATE


@bot_error_handler
async def tagihan_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse due date, ask reminder hours."""
    rec_service: RecurringService = context.bot_data["recurring_service"]
    date_obj = rec_service.parse_date(update.message.text.strip())
    if date_obj is None:
        await update.message.reply_text(
            "⚠️ Format tanggal gak dikenali. Coba `besok`, `hari ini`, atau `YYYY-MM-DD`.",
        )
        return DATE

    context.user_data["recurring"]["next_run"] = date_obj.timestamp()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ 24 jam sebelumnya", callback_data="recur:reminder:24")],
        [InlineKeyboardButton("⏰ 3 hari sebelumnya", callback_data="recur:reminder:72")],
        [InlineKeyboardButton("⏰ 7 hari sebelumnya", callback_data="recur:reminder:168")],
    ])
    await update.message.reply_text(
        "🔔 Kapan kirim pengingat?",
        reply_markup=keyboard,
    )
    return REMINDER


@bot_error_handler
async def tagihan_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture reminder preference, show confirmation."""
    query = update.callback_query
    await query.answer()

    reminder_text = query.data.replace("recur:reminder:", "")
    try:
        reminder_hours = int(reminder_text)
    except ValueError:
        reminder_hours = 24
    context.user_data["recurring"]["reminder_hours"] = reminder_hours

    data = context.user_data["recurring"]
    text = (
        f"📝 *Konfirmasi Tagihan*\n\n"
        f"Nama: {data.get('description')}\n"
        f"Jumlah: Rp {data.get('amount', 0):,}\n"
        f"Kategori: {data.get('category')}\n"
        f"Frekuensi: tiap {data.get('interval_days')} hari\n"
        f"Jatuh tempo pertama: {__import__('datetime').datetime.fromtimestamp(data['next_run']).strftime('%Y-%m-%d')}\n"
        f"Pengingat: {reminder_hours} jam sebelumnya\n\n"
        f"Benar?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Simpan", callback_data="recur:confirm:yes")],
        [InlineKeyboardButton("❌ Batal", callback_data="recur:confirm:no")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRM


@bot_error_handler
async def tagihan_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save or cancel recurring config."""
    query = update.callback_query
    await query.answer()

    if query.data == "recur:confirm:no":
        await query.edit_message_text("❌ Tagihan rutin dibatalkan.")
        context.user_data.pop("recurring", None)
        return ConversationHandler.END

    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    rec_service: RecurringService = context.bot_data["recurring_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")
    data = context.user_data["recurring"]

    result = rec_service.add_recurring(
        telegram_id=user_id,
        ss_id=ss_id,
        description=data.get("description", ""),
        amount=data.get("amount", 0),
        category=data.get("category", "Lainnya"),
        interval_days=data.get("interval_days", 30),
        next_run=data.get("next_run"),
        reminder_hours=data.get("reminder_hours", 24),
    )

    if result.get("success"):
        await query.edit_message_text(
            f"✅ Tagihan rutin tersimpan!\n"
            f"Aku akan ingetin dan otomatis catat *{data.get('description')}* "
            f"sebesar Rp {data.get('amount', 0):,} tiap {data.get('interval_days')} hari.",
            parse_mode="Markdown",
        )
    else:
        error_map = {
            "free_tier_limit": (
                "⚠️ Akun gratis cuma bisa 3 tagihan rutin. "
                "Upgrade Premium buat unlimited!"
            ),
        }
        await query.edit_message_text(
            error_map.get(result.get("error"), "⚠️ Gagal menyimpan tagihan. Coba lagi ya."),
            parse_mode="Markdown",
        )

    context.user_data.pop("recurring", None)
    return ConversationHandler.END


@require_login
@premium_required("Tagihan & Pengingat")
@bot_error_handler
async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List upcoming recurring bills."""
    user_id = str(update.effective_user.id)
    rec_service: RecurringService = context.bot_data["recurring_service"]

    items = rec_service.list_recurring(user_id)
    if not items:
        await update.message.reply_text(
            "📭 Belum ada tagihan rutin. Tambah pakai /tagihan ya."
        )
        return

    lines = ["⏰ *Tagihan Rutin Mendatang*\n"]
    for item in items:
        status = "✅ Aktif" if item.get("enabled") else "⏸️ Nonaktif"
        next_run_str = __import__('datetime').datetime.fromtimestamp(item["next_run"]).strftime("%Y-%m-%d")
        lines.append(
            f"#{item['id']} *{item['description']}* — Rp {item['amount']:,}\n"
            f"   Kategori: {item['category']} | {item['interval_days']} hari\n"
            f"   Jatuh tempo: {next_run_str} ({status})\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_login
@premium_required("Tagihan & Pengingat")
@bot_error_handler
async def tagihan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel /tagihan conversation."""
    await update.message.reply_text("❌ Tagihan rutin dibatalkan.")
    context.user_data.pop("recurring", None)
    return ConversationHandler.END
