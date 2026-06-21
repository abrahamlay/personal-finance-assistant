"""Centralized exception-to-user-message mapper for all bot handlers."""
import functools
import logging
import traceback

import gspread
from google.auth.exceptions import RefreshError

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# Friendly Indonesian messages for common error classes.
ERROR_MESSAGES = {
    "SheetNotFoundError": (
        "📂 Google Sheet kamu gak ketemu. Coba /login ulang ya."
    ),
    "SheetAuthError": (
        "🔐 Login kamu expired. Ketik /login ya."
    ),
    "RefreshError": (
        "🔐 Login kamu expired. Ketik /login ya."
    ),
    "gspread.exceptions.SpreadsheetNotFound": (
        "📂 Google Sheet kamu gak ketemu. Coba /login ulang ya."
    ),
    "gspread.exceptions.APIError": (
        "⚠️ Google Sheets lagi bermasalah. Coba lagi beberapa saat ya, "
        "atau ketik /perbaiki kalau sheet-nya bermasalah."
    ),
    "ConnectionError": (
        "📡 Gagal koneksi. Coba lagi ya."
    ),
    "TimeoutError": (
        "⏱️ Koneksi lambat. Coba lagi ya."
    ),
}


def _get_user_message(exc: Exception) -> str:
    """Map exception to a friendly Bahasa Indonesia message."""
    exc_type = type(exc).__name__

    # Direct mapping by exception class name
    if exc_type in ERROR_MESSAGES:
        return ERROR_MESSAGES[exc_type]

    # Module-qualified names
    module_name = f"{type(exc).__module__}.{exc_type}"
    if module_name in ERROR_MESSAGES:
        return ERROR_MESSAGES[module_name]

    # Specific gspread checks
    if isinstance(exc, gspread.exceptions.SpreadsheetNotFound):
        return ERROR_MESSAGES["gspread.exceptions.SpreadsheetNotFound"]
    if isinstance(exc, gspread.exceptions.APIError):
        code = getattr(exc, "code", 0) or _extract_api_error_code(exc)
        if code == 429:
            return (
                "🐢 Sistem sibuk (quota terbatas). Coba lagi beberapa saat ya."
            )
        return ERROR_MESSAGES["gspread.exceptions.APIError"]
    if isinstance(exc, RefreshError):
        return ERROR_MESSAGES["RefreshError"]

    # Network-related errors
    message = str(exc).lower()
    if "connection" in message or "network" in message or "name resolution" in message:
        return ERROR_MESSAGES["ConnectionError"]
    if "timeout" in message:
        return ERROR_MESSAGES["TimeoutError"]
    if "not found" in message or "404" in message:
        return ERROR_MESSAGES["SheetNotFoundError"]
    if "auth" in message or "credential" in message or "expired" in message:
        return ERROR_MESSAGES["SheetAuthError"]
    if "quota" in message or "rate limit" in message or "too many" in message:
        return (
            "🐢 Sistem sibuk. Coba lagi beberapa saat ya."
        )

    # Default fallback
    return (
        "😅 Ada kendala teknis. Tim kami sudah mencatatnya. "
        "Coba lagi beberapa saat ya."
    )


def _extract_api_error_code(exc: gspread.exceptions.APIError) -> int:
    try:
        response = getattr(exc, "response", None)
        if response is not None:
            return int(getattr(response, "status_code", 0))
    except Exception:
        pass
    return 0


def handle_exception(update: Update | None, context: ContextTypes.DEFAULT_TYPE | None,
                     exc: Exception, reply_target: str = "message") -> str:
    """Log exception and return friendly message. Optionally send to user.

    reply_target: 'message' (default) or 'callback_query'.
    """
    logger.exception("Unhandled exception in handler: %s", exc)
    user_message = _get_user_message(exc)

    if update is None:
        return user_message

    try:
        if reply_target == "callback_query" and update.callback_query:
            awaitable = update.callback_query.edit_message_text(user_message)
        elif update.message:
            awaitable = update.message.reply_text(user_message)
        elif update.callback_query:
            awaitable = update.callback_query.edit_message_text(user_message)
        else:
            return user_message

        # We need to await the coroutine outside the sync helper.
        # The decorator below handles the async path.
        return user_message, awaitable  # type: ignore[return-value]
    except Exception:
        logger.exception("Failed to send error message to user")
        return user_message


def bot_error_handler(func=None, *, reply_target: str = "message"):
    """Decorator that catches all exceptions and maps them to friendly messages.

    Usage:
        @bot_error_handler
        async def my_handler(update, context): ...

        @bot_error_handler(reply_target="callback_query")
        async def my_callback(update, context): ...
    """
    if func is None:
        def wrapper(f):
            return bot_error_handler(f, reply_target=reply_target)
        return wrapper

    @functools.wraps(func)
    async def async_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as exc:
            user_message = _get_user_message(exc)
            logger.error(
                "Error in %s: %s\n%s",
                func.__name__, exc, traceback.format_exc()
            )
            try:
                if reply_target == "callback_query" and update.callback_query:
                    await update.callback_query.edit_message_text(user_message)
                elif update.message:
                    await update.message.reply_text(user_message)
                elif update.callback_query:
                    await update.callback_query.edit_message_text(user_message)
            except Exception:
                logger.exception("Failed to send error message to user")

    return async_wrapper


def safe_handler(func=None, *, reply_target: str = "message"):
    """Alias for bot_error_handler."""
    return bot_error_handler(func, reply_target=reply_target)
