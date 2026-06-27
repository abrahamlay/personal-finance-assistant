"""Onboarding wizard: 4-step ConversationHandler for new user setup."""
import logging
import secrets
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

logger = logging.getLogger(__name__)

# Conversation states
(NAME, AUTH, DONE, TUTORIAL) = range(4)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point. Check if already onboarded, else start wizard."""
    user = update.effective_user
    token_store: TokenStore = context.bot_data["token_store"]

    # Handle deep link from oauth redirect: /start oauth_done
    if context.args and context.args[0] == "oauth_done":
        user_token = token_store.get_user_token(str(user.id))
        if user_token and user_token.get("access_token"):
            if "display_name" in context.user_data:
                # They were in onboarding! Continue onboarding.
                context.user_data["mode"] = "google_sheets"
                return await _continue_onboarding(update, context)
            else:
                # Standalone login!
                msg = await update.message.reply_text("⏳ Menghubungkan Google Sheet...")
                try:
                    setup: SheetSetupService = context.bot_data["sheet_setup"]
                    ss_id = setup.setup_new_user(str(user.id), user.first_name)
                    await msg.edit_text(
                        "✅ *Login berhasil!* Google Sheet kamu sudah terhubung.\n\n"
                        "Sekarang kamu bisa:\n"
                        "💰 *Catat pengeluaran* — cukup ketik \"makan siang 50rb\"\n"
                        "📊 *Lihat laporan* — /bulanan /mingguan /dashboard\n\n"
                        "Atau ketik /bantuan buat lihat semua perintah.",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error("Sheet creation failed in standalone login: %s", e)
                    await msg.edit_text(
                        "⚠️ Login berhasil, tapi gagal membuat Google Sheet.\n"
                        "Coba ketik /start buat setup ulang, atau /status buat cek status.",
                    )
                return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Otorisasi Google tidak ditemukan. Silakan ketik /login untuk mencoba lagi.")
            return ConversationHandler.END

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
        f"Klik tombol di bawah untuk login:",
        parse_mode="Markdown",
        reply_markup=_auth_keyboard(context, str(update.effective_user.id)),
    )
    return AUTH


async def auth_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wait for OAuth completion or handle manual/offline choice."""
    query = update.callback_query

    # Handle WebApp data (user clicked login button in AUTH state)
    if not query and update.effective_message and update.effective_message.web_app_data:
        import json
        data = json.loads(update.effective_message.web_app_data.data)
        state = (data.get("state") or "").strip()
        pending_tokens: dict = context.bot_data.get("pending_tokens", {})
        token_data = pending_tokens.pop(state, None)
        if token_data:
            oauth: OAuthManager = context.bot_data["oauth_manager"]
            oauth.store_credentials(
                str(update.effective_user.id), token_data,
                context.user_data.get("display_name", update.effective_user.first_name),
            )
            context.user_data["mode"] = "google_sheets"
            return await _continue_onboarding(update, context)
        else:
            await update.message.reply_text("❌ Login gagal. Coba lagi dengan /login.")
            return AUTH

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
            return await _continue_onboarding(update, context)
        elif query.data == "auth_manual":
            await query.edit_message_text(
                "📋 *Login Manual*\n\n"
                "1. Buka link ini di browser:\n"
                f"`{_get_auth_url(context)}`\n\n"
                "2. Login & izinkan akses\n"
                "3. Copy kode yang muncul\n"
                "4. Paste di sini ya!\n\n"
                "Atau ketik /skip untuk lewati.",
                parse_mode="Markdown",
            )
            return AUTH

    # Check if user completed OAuth via WebApp (stored in pending_tokens)
    if update.message and update.message.text:
        text = update.message.text.strip()
        if text.startswith("/skip"):
            context.user_data["mode"] = "offline"
            await update.message.reply_text("Baik, lanjut tanpa Google Sheet dulu ya.")
            return await _continue_onboarding(update, context)
        try:
            oauth: OAuthManager = context.bot_data["oauth_manager"]
            token_data = oauth.exchange_code(text)
            oauth.store_credentials(
                str(update.effective_user.id), token_data,
                context.user_data.get("display_name", update.effective_user.first_name),
            )
            context.user_data["mode"] = "google_sheets"
            return await _continue_onboarding(update, context)
        except Exception:
            await update.message.reply_text("❌ Kode tidak valid. Coba lagi atau ketik /skip")
            return AUTH

    # Check if OAuth was completed already (token stored by global handler)
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(update.effective_user.id))
    if user_token and user_token.get("access_token"):
        context.user_data["mode"] = "google_sheets"
        return await _continue_onboarding(update, context)

    # If still no auth, wait
    if context.user_data.get("mode") != "google_sheets" and context.user_data.get("mode") != "offline":
        return AUTH  # Keep waiting

    return await _continue_onboarding(update, context)


async def _continue_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Post-auth: create sheet, offer trial, show tutorial."""

    # Create sheet if using Google
    if context.user_data.get("mode") == "google_sheets":
        msg = await update.effective_message.reply_text("⏳ Membuat Google Sheet kamu...")
        try:
            setup: SheetSetupService = context.bot_data["sheet_setup"]
            ss_id = setup.setup_new_user(
                str(update.effective_user.id),
                context.user_data.get("display_name", update.effective_user.first_name),
            )
            context.user_data["spreadsheet_id"] = ss_id
            await msg.edit_text(
                f"✅ Google Sheet berhasil dibuat!\n"
                f"Nama: *KeuanganBot - {context.user_data.get('display_name', '')}*\n\n"
                f"Semua transaksi kamu akan otomatis tersimpan di sana.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error("Sheet creation failed for user %s: %s", update.effective_user.id, e, exc_info=True)
            await msg.edit_text(
                "⚠️ Gagal membuat Google Sheet.\n"
                f"Error: {e}\n\n"
                "Coba:\n"
                "1. Pastikan Google Drive API & Sheets API sudah di-enable\n"
                "2. Cek https://console.cloud.google.com/apis/library\n"
                "3. Ketik /start buat coba lagi nanti.\n\n"
                "Sementara pake *Mode Offline* dulu ya.",
                parse_mode="Markdown",
            )
            context.user_data["mode"] = "offline"

    # Offer premium trial
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Coba Premium Gratis 7 Hari", callback_data="trial_start")],
        [InlineKeyboardButton("Nanti aja", callback_data="trial_skip")],
    ])
    await update.effective_message.reply_text(
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


def _auth_keyboard(context: ContextTypes.DEFAULT_TYPE, user_id: str) -> InlineKeyboardMarkup:
    import secrets
    login_token = secrets.token_urlsafe(16)
    context.bot_data.setdefault("login_tokens", {})[login_token] = user_id
    
    settings = get_settings()
    base_url = settings.oauth_redirect_uri.replace('/oauth/callback', '')
    auth_url = f"{base_url}/oauth/authorize?token={login_token}"
    
    buttons = [
        [InlineKeyboardButton("🔑 Login dengan Google", url=auth_url)],
        [InlineKeyboardButton("⏭ Mode Offline (tanpa Google)", callback_data="auth_offline")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_onboarding_handler() -> ConversationHandler:
    """Build the onboarding ConversationHandler."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
            AUTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auth_step),
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, auth_step),
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
        per_message=False,
    )
