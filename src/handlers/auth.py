"""Auth command handlers: /login, /logout"""
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from src.config import get_settings
from src.auth.oauth import OAuthManager
from src.auth.token_store import TokenStore


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send WebApp login button for Google OAuth."""
    settings = get_settings()
    oauth_url = f"{settings.oauth_redirect_uri.replace('/oauth/callback', '')}/login"

    keyboard = [
        [InlineKeyboardButton("🔑 Login dengan Google", web_app=WebAppInfo(url=oauth_url))],
        [InlineKeyboardButton("📋 Copy-Paste Kode (Manual)", callback_data="auth_manual")],
    ]
    await update.message.reply_text(
        "🔐 *Login Google Sheet*\n\n"
        "Klik tombol di bawah untuk login dengan akun Google kamu.\n"
        "Data keuanganmu akan disimpan di Google Sheet milikmu sendiri — aman dan privat!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle WebApp data callback after OAuth success."""
    data_str = update.effective_message.web_app_data.data
    data = json.loads(data_str)
    code = data.get("code")

    oauth: OAuthManager = context.bot_data["oauth_manager"]
    token_store: TokenStore = context.bot_data["token_store"]

    try:
        token_data = oauth.exchange_code(code)
        oauth.store_credentials(str(update.effective_user.id), token_data,
                                update.effective_user.first_name)
        await update.message.reply_text("✅ Login berhasil! Ketik /start untuk melanjutkan.")
    except Exception as e:
        await update.message.reply_text(f"❌ Login gagal: {str(e)}. Coba lagi dengan /login")


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
