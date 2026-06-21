"""Middleware for bot handlers."""
import functools
from telegram import Update
from telegram.ext import ContextTypes
from src.auth.token_store import TokenStore
from src.auth.oauth import OAuthManager
from src.middleware.premium_gate import premium_required


def require_login(func):
    """Decorator that checks if user is logged in. Sends prompt if not."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        token_store: TokenStore = context.bot_data["token_store"]
        user_token = token_store.get_user_token(str(user.id))
        if not user_token or not user_token.get("spreadsheet_id"):
            await update.message.reply_text(
                "🔐 Kamu belum login. Ketik /login dulu ya!"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


__all__ = ["require_login", "premium_required"]
