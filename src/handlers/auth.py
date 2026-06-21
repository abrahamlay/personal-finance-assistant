"""Auth command handlers: /login, /logout"""
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from src.config import get_settings
from src.auth.oauth import OAuthManager
from src.auth.token_store import TokenStore

logger = logging.getLogger(__name__)


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send login button for Google OAuth."""
    settings = get_settings()
    oauth_url = f"{settings.oauth_redirect_uri.replace('/oauth/callback', '')}/login"

    buttons = [
        [InlineKeyboardButton("📋 Login Manual", callback_data="auth_manual")],
    ]
    if oauth_url.startswith("https://"):
        buttons.insert(0, [InlineKeyboardButton("🔑 Login dengan Google", web_app=WebAppInfo(url=oauth_url))])

    await update.message.reply_text(
        "🔐 *Login Google Sheet*\n\n"
        "Klik tombol di bawah untuk login dengan akun Google kamu.\n"
        "Data keuanganmu akan disimpan di Google Sheet milikmu sendiri — aman dan privat!",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle WebApp data callback after OAuth success."""
    data_str = update.effective_message.web_app_data.data
    data = json.loads(data_str)
    state = (data.get("state") or "").strip()

    oauth: OAuthManager = context.bot_data["oauth_manager"]
    token_store: TokenStore = context.bot_data["token_store"]
    pending_tokens: dict = context.bot_data.get("pending_tokens", {})

    token_data = pending_tokens.pop(state, None)
    if not token_data:
        logger.warning("WebApp login failed: state %s not found in pending_tokens for user %s", state, update.effective_user.id)
        await update.message.reply_text("❌ Login gagal: token tidak ditemukan. Coba lagi dengan /login")
        return

    oauth.store_credentials(str(update.effective_user.id), token_data,
                            update.effective_user.first_name)

    # Cek apakah user sedang dalam onboarding (AUTH state)
    # Kalau iya, ConversationHandler auth_step yg handle sisanya
    # Kalau gak (login ulang via /login), kasih panduan aja
    user_token = token_store.get_user_token(str(update.effective_user.id))
    if user_token and user_token.get("spreadsheet_id"):
        await update.message.reply_text(
            "✅ *Login berhasil!* Google Sheet kamu sudah terhubung.\n\n"
            "Sekarang kamu bisa:\n"
            "💰 *Catat pengeluaran* — cukup ketik \"makan siang 50rb\"\n"
            "📊 *Lihat laporan* — /bulanan /mingguan /dashboard\n"
            "📋 *Kelola kategori* — /kategori\n"
            "🎯 *Buat anggaran* — /anggaran\n\n"
            "Atau ketik /bantuan buat lihat semua perintah.",
            parse_mode="Markdown",
        )
    else:
        logger.info("User %s has no spreadsheet_id after webapp login — creating sheet now", update.effective_user.id)
        try:
            from src.sheets.setup import SheetSetupService
            setup: SheetSetupService = context.bot_data["sheet_setup"]
            msg = await update.message.reply_text("⏳ Membuat Google Sheet...")
            ss_id = setup.setup_new_user(
                str(update.effective_user.id),
                update.effective_user.first_name,
            )
            await msg.edit_text("✅ Google Sheet berhasil dibuat!")
            await update.message.reply_text(
                "✅ *Login berhasil!* Google Sheet kamu sudah terhubung.\n\n"
                "Sekarang kamu bisa:\n"
                "💰 *Catat pengeluaran* — cukup ketik \"makan siang 50rb\"\n"
                "📊 *Lihat laporan* — /bulanan /mingguan /dashboard\n"
                "📋 *Kelola kategori* — /kategori\n"
                "🎯 *Buat anggaran* — /anggaran\n\n"
                "Atau ketik /bantuan buat lihat semua perintah.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error("Sheet creation failed after webapp login for %s: %s", update.effective_user.id, e, exc_info=True)
            await msg.edit_text(
                "⚠️ Gagal membuat Google Sheet.\n"
                "Coba ketik /start buat setup ulang, atau /status buat cek status.",
            )


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoke Google token and clear user data mapping."""
    token_store: TokenStore = context.bot_data["token_store"]
    user_id = str(update.effective_user.id)

    user = token_store.get_user_token(user_id)
    if not user:
        await update.message.reply_text("Kamu belum login.")
        return

    token_store.delete_user_token(user_id)
    await update.message.reply_text(
        "👋 Kamu sudah logout. Data kamu *tidak dihapus* — masih aman di Google Sheet milikmu.\n"
        "Ketik /login kalau mau menyambungkan lagi.",
        parse_mode="Markdown",
    )
