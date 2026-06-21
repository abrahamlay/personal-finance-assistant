"""Onboarding wizard: 4-step ConversationHandler for new user setup."""
import time
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from src.config import get_settings
from src.auth.token_store import TokenStore
from src.auth.oauth import OAuthManager
from src.sheets.setup import SheetSetupService

# Conversation states
(NAME, AUTH, DONE, TUTORIAL) = range(4)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point. Check if already onboarded, else start wizard."""
    user = update.effective_user
    token_store: TokenStore = context.bot_data["token_store"]

    # Already onboarded?
    user_token = token_store.get_user_token(str(user.id))
    if user_token and user_token.get("spreadsheet_id"):
        await update.message.reply_text(
            f"Halo {user.first_name}! Kamu sudah siap pakai. 💰\n"
            "Ketik transaksi langsung atau /bantuan untuk lihat menu."
        )
        return ConversationHandler.END

    # Start wizard
    context.user_data["onboarding_started"] = time.time()

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("⏭ Skip / Lewati")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        f"👋 *Halo! Selamat datang di Asisten Keuangan!*\n\n"
        f"Aku bantu kamu catat pengeluaran & pemasukan dengan mudah.\n\n"
        f"Pertama: Siapa nama panggilan kamu?",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return NAME


async def name_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle name input. Skip uses Telegram first_name."""
    if update.message.text and "skip" in update.message.text.lower():
        context.user_data["display_name"] = update.effective_user.first_name
    else:
        context.user_data["display_name"] = update.message.text.strip()

    # Remove reply keyboard
    await update.message.reply_text(
        f"Oke, {context.user_data['display_name']}! 🎉\n\n"
        f"*Sekarang kita sambungkan Google Sheet kamu.*\n"
        f"Data keuanganmu akan disimpan di Google Sheet *milikmu sendiri* — aman, privat, dan bisa kamu lihat kapan aja.\n\n"
        f"Pilih cara login di bawah:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 Login dengan Google", web_app=WebAppInfo(url=f"{get_settings().oauth_redirect_uri.replace('/oauth/callback', '')}/login"))],
            [InlineKeyboardButton("📋 Copy-Paste Kode Manual", callback_data="auth_manual")],
            [InlineKeyboardButton("⏭ Mode Offline (tanpa Google)", callback_data="auth_offline")],
        ]),
    )
    return AUTH


async def auth_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wait for OAuth completion or handle manual/offline choice."""
    query = update.callback_query
    if query:
        await query.answer()
        if query.data == "auth_offline":
            context.user_data["mode"] = "offline"
            await query.edit_message_text(
                "📝 *Mode Offline*\n\n"
                "Kamu bisa catat transaksi dulu tanpa Google Sheet.\n"
                "Tapi data *tidak akan tersimpan permanen* ya.\n\n"
                "Ketik /login kalau nanti mau sambungin Google Sheet.",
                parse_mode="Markdown",
            )
            return TUTORIAL
        elif query.data == "auth_manual":
            await query.edit_message_text(
                "📋 *Login Manual*\n\n"
                "1. Buka link ini di browser:\n"
                f"{_get_auth_url(context)}\n\n"
                "2. Login & izinkan akses\n"
                "3. Copy kode yang muncul\n"
                "4. Paste di sini ya!\n\n"
                "Atau ketik /skip untuk lewati.",
                parse_mode="Markdown",
            )
            return AUTH  # Stay in AUTH state, wait for code

    # Check if user completed OAuth via WebApp (stored in pending_tokens)
    # This is handled by webapp_data_handler in auth.py — we check token_store
    if update.message and update.message.text:
        text = update.message.text.strip()
        if text.startswith("/skip"):
            context.user_data["mode"] = "offline"
            await update.message.reply_text("Baik, lanjut tanpa Google Sheet dulu ya.")
            return TUTORIAL
        # Assume it's an auth code
        # Try to exchange it
        try:
            oauth: OAuthManager = context.bot_data["oauth_manager"]
            token_data = oauth.exchange_code(text)
            oauth.store_credentials(str(update.effective_user.id), token_data, context.user_data["display_name"])
            context.user_data["mode"] = "google_sheets"
        except Exception:
            await update.message.reply_text("❌ Kode tidak valid. Coba lagi atau ketik /skip")
            return AUTH

    # Check if OAuth was completed (via WebApp handler in auth.py)
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(update.effective_user.id))
    if user_token and user_token.get("access_token"):
        context.user_data["mode"] = "google_sheets"

    # If still no auth, wait (WebApp may be in progress)
    if context.user_data.get("mode") != "google_sheets" and context.user_data.get("mode") != "offline":
        return AUTH  # Keep waiting

    # Auth complete — create sheet if using Google
    if context.user_data.get("mode") == "google_sheets":
        await update.message.reply_text("⏳ Membuat Google Sheet kamu...")
        try:
            setup: SheetSetupService = context.bot_data["sheet_setup"]
            ss_id = setup.setup_new_user(str(update.effective_user.id), context.user_data["display_name"])
            context.user_data["spreadsheet_id"] = ss_id
            await update.message.reply_text(
                f"✅ Google Sheet berhasil dibuat!\n"
                f"Nama: *KeuanganBot - {context.user_data['display_name']}*\n\n"
                f"Semua transaksi kamu akan otomatis tersimpan di sana.",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Gagal membuat sheet: {e}\nLanjut tanpa sheet dulu ya.")
            context.user_data["mode"] = "offline"

    # Offer premium trial
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Coba Premium Gratis 7 Hari", callback_data="trial_start")],
        [InlineKeyboardButton("Nanti aja", callback_data="trial_skip")],
    ])
    await update.message.reply_text(
        "🎉 *Setup selesai!*\n\n"
        "Mau coba *Premium gratis 7 hari*? Kamu bisa:\n"
        "📸 Scan struk pakai foto\n"
        "📊 Dashboard keuangan lengkap\n"
        "🤖 Analisis AI pengeluaran\n"
        "🔔 Reminder tagihan\n\n"
        "Gratis, bisa cancel kapan aja!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return DONE


async def done_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trial choice, then show tutorial."""
    query = update.callback_query
    await query.answer()

    if query.data == "trial_start":
        subscription_service = context.bot_data["subscription_service"]
        user_id = str(update.effective_user.id)
        trial_sub = subscription_service.start_free_trial(user_id)
        if trial_sub is None:
            await query.edit_message_text(
                "⚠️ Kamu sudah pernah coba trial sebelumnya.\n"
                "Ketik /premium kalau mau upgrade.",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                "🎁 *Premium Trial Aktif!*\n"
                "Kamu bisa nikmatin semua fitur Premium gratis selama 7 hari.\n"
                "Ketik /statuspremium buat cek status.",
                parse_mode="Markdown",
            )
    else:
        await query.edit_message_text("Oke, kapan aja bisa upgrade ya! Ketik /premium.")

    # Quick tutorial
    await query.message.reply_text(
        "📝 *Cara Pakai*\n\n"
        "Ketik aja pengeluaran kamu langsung:\n"
        "Contoh:\n"
        "• `makan siang 50rb`\n"
        "• `gajian 8jt`\n"
        "• `bensin 100rb`\n\n"
        "Atau pakai command:\n"
        "• /masuk — catat pemasukan\n"
        "• /keluar — catat pengeluaran\n"
        "• /laporan — lihat laporan\n\n"
        "_Yuk coba catat transaksi pertama kamu sekarang!_ 🚀",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Coba Catat Transaksi", callback_data="tutorial_try")]
        ]),
    )
    return TUTORIAL


async def tutorial_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle tutorial button — just end conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "Silakan ketik transaksi pertama kamu! Contoh: `makan siang 50rb`\n\n"
            "Ketik /bantuan kalau butuh panduan lengkap.",
            parse_mode="Markdown",
        )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel or timeout."""
    await update.message.reply_text(
        "Setup dibatalkan. Ketik /start kapan aja buat mulai lagi.",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def timeout_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle wizard timeout (10 min inactivity)."""
    await update.message.reply_text(
        "⏰ Waktu setup habis. Ketik /start buat mulai lagi ya.",
    )
    context.user_data.clear()
    return ConversationHandler.END


def _get_auth_url(context) -> str:
    oauth: OAuthManager = context.bot_data["oauth_manager"]
    url, _ = oauth.get_authorization_url()
    return url


def get_onboarding_handler() -> ConversationHandler:
    """Build the onboarding ConversationHandler."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
            AUTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auth_step),
                CallbackQueryHandler(auth_step, pattern="^(auth_manual|auth_offline)$"),
            ],
            DONE: [CallbackQueryHandler(done_step, pattern="^(trial_start|trial_skip)$")],
            TUTORIAL: [CallbackQueryHandler(tutorial_step, pattern="^tutorial_try$")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_onboarding),
            CommandHandler("skip", cancel_onboarding),
        ],
        conversation_timeout=600,  # 10 minutes
    )
