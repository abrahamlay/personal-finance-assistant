"""General command handlers."""
import logging
import os
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.auth.token_store import TokenStore
from src.auth.oauth import OAuthManager
from src.services.parser_service import normalize_amount
from src.middleware import require_login, premium_required
from src.services.error_handler import bot_error_handler

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message. If new user, trigger onboarding. If returning, welcome back."""
    user = update.effective_user
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(user.id))

    if user_token and user_token.get("spreadsheet_id"):
        await update.message.reply_text(
            f"Halo {user.first_name}! 👋\n"
            f"Kamu sudah siap pakai. Ketik transaksi langsung atau /bantuan untuk lihat menu."
        )
    else:
        # New user — will be handled by ConversationHandler in Task 3.2
        await update.message.reply_text(
            f"Selamat datang di *Asisten Keuangan*! 💰\n\n"
            f"Aku bantu kamu catat pengeluaran & pemasukan dengan mudah.\n\n"
            f"Ketik /login dulu ya buat sambungin Google Sheet kamu!",
            parse_mode="Markdown",
        )


async def bantuan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all commands with descriptions in Bahasa Indonesia."""
    text = (
        "*📋 Daftar Perintah*\n\n"
        "*Pencatatan:*\n"
        "/catat — Panduan input transaksi\n"
        "/masuk — Catat pemasukan\n"
        "/keluar — Catat pengeluaran\n"
        "Atau langsung ketik: _makan siang 50rb_\n\n"
        "*Manajemen:*\n"
        "/edit — Edit transaksi: `/edit <id> <field> <value>`\n"
        "/hapus — Hapus transaksi: `/hapus <id>`\n"
        "/hariini — Lihat transaksi hari ini\n\n"
        "*Laporan:*\n"
        "/laporan — Lihat laporan keuangan\n"
        "/dashboard — Buka dashboard Google Sheet\n\n"
        "*Pengaturan:*\n"
        "/kategori — Atur kategori\n"
        "/budget — Atur budget\n"
        "/login — Sambungkan Google Sheet\n"
        "/logout — Putuskan koneksi\n\n"
        "*Premium:*\n"
        "/premium — Upgrade ke Premium\n"
        "/statuspremium — Cek status langganan\n"
        "/ocr — Scan struk belanja (kirim foto)\n"
        "/tagihan — Tambah tagihan rutin\n"
        "/reminder — Lihat tagihan mendatang\n"
        "/insight — Analisis keuangan AI\n\n"
        "*Lainnya:*\n"
        "/status — Status akun & langganan\n"
        "/verify — Login manual (paste kode dari browser)\n"
        "/export — Download data CSV\n"
        "/bantuan — Lihat panduan ini"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export transactions as CSV. Placeholder — implemented later."""
    await update.message.reply_text("📥 Fitur export sedang dikembangkan. Sabar ya!")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text("❓ Command tidak dikenali. Ketik /bantuan untuk lihat daftar perintah.")


# ---------------------------------------------------------------------------
# /catat ConversationHandler
# ---------------------------------------------------------------------------
(AMOUNT, CATEGORY, CONFIRM) = range(100, 103)

DEFAULT_CATEGORIES = [
    ("Makanan", "expense"),
    ("Transportasi", "expense"),
    ("Belanja", "expense"),
    ("Tagihan", "expense"),
    ("Kesehatan", "expense"),
    ("Hiburan", "expense"),
    ("Pendidikan", "expense"),
    ("Donasi", "expense"),
    ("Liburan", "expense"),
    ("Lainnya", "expense"),
    ("Gaji", "income"),
    ("Investasi", "income"),
    ("Hadiah", "income"),
]


@require_login
async def catat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guided transaction entry: step 1 — ask amount."""
    await update.message.reply_text("💰 Berapa jumlahnya?\nContoh: `50000` atau `50rb`", parse_mode="Markdown")
    return AMOUNT


async def catat_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse amount, then show category keyboard."""
    text = update.message.text.strip()
    amount, _ = normalize_amount(text)
    if amount == 0:
        await update.message.reply_text("⚠️ Gak bisa baca jumlah. Coba lagi ya. Contoh: `50000` atau `50rb`", parse_mode="Markdown")
        return AMOUNT

    context.user_data["catat_amount"] = amount

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"{cat_id}:{name}:{tipe}")]
        for cat_id, (name, tipe) in enumerate(DEFAULT_CATEGORIES)
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("📂 Pilih kategori:", reply_markup=reply_markup)
    return CATEGORY


async def catat_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture category selection, ask for description/confirm."""
    query = update.callback_query
    await query.answer()

    _, category, transaction_type = query.data.split(":", 2)
    context.user_data["catat_category"] = category
    context.user_data["catat_tipe"] = transaction_type

    amount = context.user_data.get("catat_amount", 0)
    emoji = {"income": "💰", "expense": "📤"}.get(transaction_type, "📌")
    text = (
        f"{emoji} *{category}* — Rp {amount:,}\n\n"
        "Ketik deskripsi singkat, atau kirim /skip buat lanjut tanpa deskripsi."
    )
    await query.edit_message_text(text, parse_mode="Markdown")
    return CONFIRM


async def catat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and create transaction."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    tx_service = context.bot_data["tx_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    amount = context.user_data.get("catat_amount", 0)
    category = context.user_data.get("catat_category", "Lainnya")
    transaction_type = context.user_data.get("catat_tipe", "expense")

    text = update.message.text.strip()
    if text == "/skip":
        description = ""
    else:
        description = text

    today = datetime.now().strftime("%Y-%m-%d")
    r = tx_service.create(user_id, ss_id, transaction_type, category, amount, description, today)

    if r.get("was_duplicate"):
        await update.message.reply_text(f"⚠️ Duplikat: {category} Rp {amount:,}")
    else:
        emoji = {"income": "💰", "expense": "📤"}.get(transaction_type, "📌")
        total = r.get("today_total", {})
        await update.message.reply_text(
            f"✅ Tercatat: {emoji} {category} — Rp {amount:,} [#{r['row_id']}]\n"
            f"📊 *Hari ini:* Rp {total.get('expense', 0):,} ({total.get('count', 0)} transaksi)",
            parse_mode="Markdown",
        )

    context.user_data.pop("catat_amount", None)
    context.user_data.pop("catat_category", None)
    context.user_data.pop("catat_tipe", None)
    return ConversationHandler.END


async def catat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel /catat conversation."""
    await update.message.reply_text("❌ Pencatatan dibatalkan.")
    context.user_data.pop("catat_amount", None)
    context.user_data.pop("catat_category", None)
    context.user_data.pop("catat_tipe", None)
    return ConversationHandler.END


@require_login
async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit transaction: /edit 5 kategori Makanan"""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    tx_service = context.bot_data["tx_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    args = update.message.text.split(maxsplit=3)
    if len(args) < 4:
        await update.message.reply_text(
            "⚠️ Format salah. Gunakan: `/edit <id> <field> <value>`\n"
            "Contoh: `/edit 5 kategori Makanan` atau `/edit 5 jumlah 75000`",
            parse_mode="Markdown",
        )
        return

    _, row_id_str, field, value = args
    try:
        row_id = int(row_id_str)
    except ValueError:
        await update.message.reply_text("⚠️ ID harus angka. Contoh: `/edit 5 kategori Makanan`", parse_mode="Markdown")
        return

    field_map = {
        "kategori": "kategori",
        "tipe": "tipe",
        "jumlah": "jumlah",
        "deskripsi": "deskripsi",
    }
    if field.lower() not in field_map:
        await update.message.reply_text(
            "⚠️ Field tidak dikenali. Pilih: kategori, tipe, jumlah, deskripsi.",
        )
        return

    success = tx_service.update(user_id, ss_id, row_id, **{field_map[field.lower()]: value})
    if success:
        await update.message.reply_text(f"✅ Transaksi #{row_id} diperbarui: {field} = {value}")
    else:
        await update.message.reply_text(f"⚠️ Transaksi #{row_id} tidak ditemukan.")


@require_login
async def hapus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete transaction: /hapus 5"""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    tx_service = context.bot_data["tx_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text("⚠️ Format: `/hapus <id>`\nContoh: `/hapus 5`", parse_mode="Markdown")
        return

    try:
        row_id = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ ID harus angka. Contoh: `/hapus 5`", parse_mode="Markdown")
        return

    success = tx_service.delete(user_id, ss_id, row_id)
    if success:
        await update.message.reply_text(f"🗑️ Transaksi #{row_id} berhasil dihapus.")
    else:
        await update.message.reply_text(f"⚠️ Transaksi #{row_id} tidak ditemukan.")


@require_login
async def hariini_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's text recap with category breakdown."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    report_service = context.bot_data["report_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    summary = report_service.get_daily_summary(user_id, ss_id)
    if summary["count"] == 0:
        await update.message.reply_text("📭 Belum ada transaksi hari ini.")
        return

    text = _format_summary(summary, "📊 *Laporan Hari Ini*")
    await update.message.reply_text(text, parse_mode="Markdown")


@require_login
async def mingguan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show weekly text recap and send matplotlib bar chart PNG."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    report_service = context.bot_data["report_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    summary = report_service.get_weekly_summary(user_id, ss_id)
    text = _format_summary(summary, "📈 *Laporan Minggu Ini*")
    await update.message.reply_text(text, parse_mode="Markdown")

    chart_path = report_service.generate_weekly_chart(user_id, ss_id)
    try:
        with open(chart_path, "rb") as photo:
            await update.message.reply_photo(photo=photo)
    finally:
        if os.path.exists(chart_path):
            os.remove(chart_path)


@require_login
async def bulanan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly summary + comparison vs last month + link to Dashboard."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    report_service = context.bot_data["report_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    summary = report_service.get_monthly_summary(user_id, ss_id)
    text = _format_monthly_summary(summary)
    dashboard_generator = context.bot_data["dashboard_generator"]
    dashboard_url = dashboard_generator.get_dashboard_url(user_id, ss_id)
    text += f"\n\n📎 *Dashboard lengkap:* [Buka Sheet]({dashboard_url})"
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


@require_login
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send link to the Dashboard tab."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    dashboard_generator = context.bot_data["dashboard_generator"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")
    dashboard_url = dashboard_generator.get_dashboard_url(user_id, ss_id)

    await update.message.reply_text(
        f"📊 *Dashboard Keuangan*\n\n[Lihat di Google Sheet]({dashboard_url})",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


@require_login
async def perbaiki_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regenerate the Dashboard tab."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    dashboard_generator = context.bot_data["dashboard_generator"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")
    is_premium = token_store.get_active_subscription(user_id) is not None

    await update.message.reply_text("⏳ Memperbarui dashboard...")
    try:
        dashboard_generator.regenerate(user_id, ss_id, is_premium)
        await update.message.reply_text("✅ Dashboard berhasil diperbarui!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal memperbarui dashboard: {e}")


@require_login
@premium_required("Insight AI")
@bot_error_handler
async def insight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate AI-powered spending insight for premium users."""
    user_id = str(update.effective_user.id)
    token_store: TokenStore = context.bot_data["token_store"]
    insight_service = context.bot_data["insight_service"]
    tx_service = context.bot_data["tx_service"]

    user = token_store.get_user_token(user_id)
    ss_id = user.get("spreadsheet_id")

    # Analyze last 6 months of transactions
    now = datetime.now()
    transactions: list[dict] = []
    for i in range(6):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        transactions.extend(tx_service.get_by_month(user_id, ss_id, year, month))

    # Simple deduplication by id
    seen = set()
    unique_transactions = []
    for t in transactions:
        tid = t.get("id")
        if tid and tid not in seen:
            seen.add(tid)
            unique_transactions.append(t)

    categories = []
    sheets_categories = context.bot_data.get("sheets_categories")
    if sheets_categories:
        try:
            categories = sheets_categories.list_all(user_id, ss_id)
        except Exception:
            pass

    await update.message.reply_text("⏳ Sedang menganalisis keuangan kamu...")
    insight = await insight_service.analyze(unique_transactions, categories)
    await update.message.reply_text(insight, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_summary(summary: dict, title: str) -> str:
    lines = [title]
    lines.append(f"💰 Pemasukan: Rp {summary['income']:,}")
    lines.append(f"📤 Pengeluaran: Rp {summary['expense']:,}")
    lines.append(f"💵 Saldo: Rp {summary['saldo']:,}")
    lines.append(f"📝 Total: {summary['count']} transaksi")

    expense_breakdown = summary.get("category_breakdown", {}).get("expense", {})
    if expense_breakdown:
        lines.append("\n*Pengeluaran per kategori:*")
        for cat, amount in list(expense_breakdown.items())[:5]:
            lines.append(f"• {cat}: Rp {amount:,}")

    latest = summary.get("latest", [])
    if latest:
        lines.append(f"\n*5 transaksi terakhir:*")
        for t in latest:
            emoji = {"income": "💰", "expense": "📤"}.get(t.get("tipe"), "📌")
            lines.append(
                f"#{t.get('id')} {emoji} {t.get('kategori')} — Rp {t.get('jumlah', 0):,} ({t.get('deskripsi', '')})"
            )
    return "\n".join(lines)


async def _create_sheet_if_needed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Create Google Sheet if user doesn't have one. Returns True if successful or already exists."""
    from src.sheets.setup import SheetSetupService
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(update.effective_user.id))
    if user_token and user_token.get("spreadsheet_id"):
        return True
    try:
        setup: SheetSetupService = context.bot_data["sheet_setup"]
        msg = await update.message.reply_text("⏳ Membuat Google Sheet...")
        ss_id = setup.setup_new_user(
            str(update.effective_user.id),
            update.effective_user.first_name,
        )
        await msg.edit_text("✅ Google Sheet berhasil dibuat!")
        return True
    except Exception as e:
        logger.error("Sheet creation failed after verify: %s", e, exc_info=True)
        return False


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manual /verify <code> <state> — complete OAuth from desktop fallback."""
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Format: `/verify <kode> <state>`\n\n"
            "Salin kode dari halaman browser setelah login Google.",
            parse_mode="Markdown",
        )
        return

    code, state = args[0], args[1]
    user_id = str(update.effective_user.id)
    oauth: OAuthManager = context.bot_data["oauth_manager"]
    token_store: TokenStore = context.bot_data["token_store"]

    pending_tokens: dict = context.bot_data.get("pending_tokens", {})
    token_data = pending_tokens.pop(state, None)

    if not token_data:
        # The WebApp may have already consumed the pending token and stored the
        # credentials. Treat /verify as idempotent instead of trying to re-exchange
        # an already-used Google authorization code.
        existing = token_store.get_user_token(user_id)
        if existing and existing.get("access_token"):
            sheet_ok = await _create_sheet_if_needed(update, context)
            if sheet_ok:
                await update.message.reply_text(
                    "✅ *Login berhasil!* Google Sheet kamu sudah terhubung.\n\n"
                    "Sekarang kamu bisa:\n"
                    "💰 *Catat pengeluaran* — cukup ketik \"makan siang 50rb\"\n"
                    "📊 *Lihat laporan* — /bulanan /mingguan /dashboard\n\n"
                    "Atau ketik /bantuan buat lihat semua perintah.",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    "✅ Login berhasil, tapi gagal membuat Google Sheet.\n"
                    "Coba ketik /start buat setup ulang, atau /status buat cek.",
                )
            return

        try:
            token_data = oauth.exchange_code(code, state)
        except Exception as e:
            logger.error("Manual /verify failed for %s: %s", user_id, e)
            await update.message.reply_text(
                "❌ Kode tidak valid atau sudah kedaluwarsa. Coba /login lagi.",
            )
            return

    oauth.store_credentials(user_id, token_data, update.effective_user.first_name)

    sheet_ok = await _create_sheet_if_needed(update, context)
    if sheet_ok:
        await update.message.reply_text(
            "✅ *Login berhasil!* Google Sheet kamu sudah terhubung.\n\n"
            "Sekarang kamu bisa:\n"
            "💰 *Catat pengeluaran* — cukup ketik \"makan siang 50rb\"\n"
            "📊 *Lihat laporan* — /bulanan /mingguan /dashboard\n\n"
            "Atau ketik /bantuan buat lihat semua perintah.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "✅ Login berhasil, tapi gagal membuat Google Sheet.\n"
            "Coba ketik /start buat setup ulang, atau /status buat cek.",
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user status: login, sheet, premium, subscription expiry."""
    import time
    user = update.effective_user
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(user.id))

    lines = [f"👤 *Status Akun — {user.first_name}*"]

    # Login status
    if user_token and user_token.get("access_token"):
        lines.append("\n🔐 *Login Google:* ✅ Aktif")
        if user_token.get("spreadsheet_id"):
            lines.append("📊 *Google Sheet:* ✅ Terhubung")
        else:
            lines.append("📊 *Google Sheet:* ❌ Belum ada — ketik /start buat setup")
    else:
        lines.append("\n🔐 *Login Google:* ❌ Belum login — ketik /login")

    # Premium status
    sub_service = context.bot_data.get("subscription_service")
    if sub_service:
        sub = sub_service.get_active(str(user.id))
        if sub:
            plan = sub.get("plan", "-")
            status = sub.get("status", "-")
            plan_info = sub_service.PLANS.get(plan, {})
            lines.append(f"\n⭐ *Premium:* ✅ Aktif")
            lines.append(f"   Paket: {plan_info.get('name', plan.capitalize())}")
            lines.append(f"   Status: {status.capitalize()}")
            end_date = sub.get("end_date")
            if plan == "lifetime":
                lines.append("   Berlaku: 🕐 Seumur hidup")
            elif end_date:
                days_left = max(0, int((end_date - time.time()) / 86400))
                expiry = datetime.fromtimestamp(end_date).strftime("%d %b %Y")
                lines.append(f"   Berlaku sampai: {expiry} ({days_left} hari lagi)")
                if sub.get("auto_renew"):
                    lines.append("   Auto-renew: ✅ Aktif")
                else:
                    lines.append("   Auto-renew: ❌ Nonaktif")
            trial_end = sub.get("trial_end")
            if trial_end and trial_end > time.time():
                trial_days = max(0, int((trial_end - time.time()) / 86400))
                lines.append(f"   🎁 Masa trial: {trial_days} hari lagi")
        else:
            lines.append("\n⭐ *Premium:* ❌ Tidak aktif — ketik /premium")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _format_monthly_summary(summary: dict) -> str:
    lines = ["📅 *Laporan Bulan Ini*"]
    lines.append(f"💰 Pemasukan: Rp {summary['income']:,}")
    lines.append(f"📤 Pengeluaran: Rp {summary['expense']:,}")
    lines.append(f"💵 Saldo: Rp {summary['saldo']:,}")
    lines.append(f"📝 Total: {summary['count']} transaksi")

    comp = summary.get("comparison", {})
    prev = summary.get("previous", {})
    lines.append("\n*Dibandingkan bulan lalu:*")
    lines.append(f"• Pemasukan: {comp.get('income_pct', 0):+.1f}% (Rp {prev.get('income', 0):,})")
    lines.append(f"• Pengeluaran: {comp.get('expense_pct', 0):+.1f}% (Rp {prev.get('expense', 0):,})")
    lines.append(f"• Saldo: {comp.get('saldo_pct', 0):+.1f}% (Rp {prev.get('saldo', 0):,})")

    expense_breakdown = summary.get("category_breakdown", {}).get("expense", {})
    if expense_breakdown:
        lines.append("\n*Pengeluaran per kategori:*")
        for cat, amount in list(expense_breakdown.items())[:5]:
            lines.append(f"• {cat}: Rp {amount:,}")
    return "\n".join(lines)
