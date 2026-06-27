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
    import secrets
    user_id = str(update.effective_user.id)
    login_token = secrets.token_urlsafe(16)
    context.bot_data.setdefault("login_tokens", {})[login_token] = user_id

    settings = get_settings()
    base_url = settings.oauth_redirect_uri.replace('/oauth/callback', '')
    auth_url = f"{base_url}/oauth/authorize?token={login_token}"

    buttons = [
        [InlineKeyboardButton("🔑 Login dengan Google", url=auth_url)],
    ]

    await update.message.reply_text(
        "🔐 *Login Google Sheet*\n\n"
        "Klik tombol di bawah untuk login dengan akun Google kamu.\n"
        "Data keuanganmu akan disimpan di Google Sheet milikmu sendiri — aman dan privat!",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle WebApp data callback after OAuth success (Deprecated)."""
    logger.warning("Deprecated webapp_data_handler called")
    return


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
