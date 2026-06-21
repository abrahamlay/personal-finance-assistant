"""Premium feature gate decorator."""
import functools

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def premium_required(feature_name: str):
    """Decorator that blocks free tier users from premium features."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = str(update.effective_user.id)
            sub_service = context.bot_data.get("subscription_service")
            if sub_service and sub_service.is_premium(user_id):
                return await func(update, context, *args, **kwargs)

            # Block free user
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Upgrade ke Premium", callback_data="premium_upgrade")],
                [InlineKeyboardButton("ℹ️ Lihat Paket", callback_data="premium_plans")],
            ])
            text = (
                f"🔒 *{feature_name}*\n\n"
                "Fitur ini khusus Premium. Upgrade sekarang buat akses semua fitur!"
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return None

        return wrapper

    return decorator
