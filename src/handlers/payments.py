"""Payment update handlers wiring."""
from telegram.ext import MessageHandler, PreCheckoutQueryHandler, filters

from src.payments.stars import pre_checkout_handler, successful_payment_handler


def get_payment_handlers():
    """Return PTB handlers for Telegram Stars payments."""
    return [
        PreCheckoutQueryHandler(pre_checkout_handler),
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler),
    ]
