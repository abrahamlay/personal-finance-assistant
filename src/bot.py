"""Asisten Keuangan — Telegram bot main entry point."""
import asyncio
import sys
import logging
from aiohttp import web
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler

from telegram import Update
from src.config import get_settings
from src.auth.token_store import TokenStore
from src.auth.oauth import OAuthManager
from src.sheets.client import SheetsClient
from src.sheets.setup import SheetSetupService
from src.sheets.transactions import SheetsTransactions
from src.sheets.categories import SheetsCategories
from src.sheets.budgets import SheetsBudgets
from src.services.transaction_service import TransactionService
from src.services.budget_service import BudgetService
from src.services.report_service import ReportService
from src.services.subscription_service import SubscriptionService
from src.services.ocr_service import OCRService
from src.services.recurring_service import RecurringService
from src.services.insight_service import InsightService
from src.cache.memory_cache import MemoryCache
from src.handlers import commands, auth, messages, categories, budgets, premium, payments, recurring
from src.handlers.onboarding import get_onboarding_handler
from src.sheets.dashboard import DashboardGenerator
from src.payments.stars import StarsPayment
from src.payments.midtrans import MidtransPayment
from src.web_server import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_bot() -> Application:
    """Build and configure the PTB Application with all handlers and dependencies."""
    settings = get_settings()

    # Initialize services
    token_store = TokenStore()
    token_store.init_db()

    oauth_manager = OAuthManager(token_store)
    sheets_client = SheetsClient(oauth_manager, token_store)
    dashboard_generator = DashboardGenerator(sheets_client)
    sheet_setup = SheetSetupService(sheets_client, token_store, dashboard_generator)
    sheets_transactions = SheetsTransactions(sheets_client)
    sheets_categories = SheetsCategories(sheets_client, token_store)
    sheets_budgets = SheetsBudgets(sheets_client)
    cache = MemoryCache()
    tx_service = TransactionService(sheets_transactions, cache)
    budget_service = BudgetService(sheets_budgets, sheets_transactions, token_store)
    report_service = ReportService(sheets_transactions, tx_service)
    subscription_service = SubscriptionService(token_store)
    stars_payment = StarsPayment(subscription_service)
    midtrans_payment = MidtransPayment(
        server_key=settings.midtrans_server_key,
        client_key=settings.midtrans_client_key,
    )
    ocr_service = OCRService(api_key=settings.gemini_api_key, token_store=token_store)
    recurring_service = RecurringService(
        transaction_service=tx_service,
        token_store=token_store,
        sheets_categories=sheets_categories,
    )
    insight_service = InsightService(gemini_api_key=settings.gemini_api_key)

    # Build bot
    app = Application.builder().token(settings.telegram_token).build()

    # Store dependencies in bot_data (accessible in all handlers via context.bot_data)
    app.bot_data["token_store"] = token_store
    app.bot_data["oauth_manager"] = oauth_manager
    app.bot_data["sheets_client"] = sheets_client
    app.bot_data["sheet_setup"] = sheet_setup
    app.bot_data["sheets_transactions"] = sheets_transactions
    app.bot_data["sheets_categories"] = sheets_categories
    app.bot_data["sheets_budgets"] = sheets_budgets
    app.bot_data["cache"] = cache
    app.bot_data["tx_service"] = tx_service
    app.bot_data["budget_service"] = budget_service
    app.bot_data["report_service"] = report_service
    app.bot_data["dashboard_generator"] = dashboard_generator
    app.bot_data["settings"] = settings
    app.bot_data["subscription_service"] = subscription_service
    app.bot_data["stars_payment"] = stars_payment
    app.bot_data["midtrans_payment"] = midtrans_payment
    app.bot_data["ocr_service"] = ocr_service
    app.bot_data["recurring_service"] = recurring_service
    app.bot_data["insight_service"] = insight_service
    app.bot_data["pending_tokens"] = {}

    # Register command handlers
    # Onboarding wizard replaces the plain /start handler
    app.add_handler(get_onboarding_handler())
    app.add_handler(CommandHandler("bantuan", commands.bantuan_command))
    app.add_handler(CommandHandler("export", commands.export_command))
    app.add_handler(CommandHandler("login", auth.login_command))
    app.add_handler(CommandHandler("logout", auth.logout_command))
    app.add_handler(CommandHandler("edit", commands.edit_command))
    app.add_handler(CommandHandler("hapus", commands.hapus_command))
    app.add_handler(CommandHandler("hariini", commands.hariini_command))
    app.add_handler(CommandHandler("mingguan", commands.mingguan_command))
    app.add_handler(CommandHandler("bulanan", commands.bulanan_command))
    app.add_handler(CommandHandler("dashboard", commands.dashboard_command))
    app.add_handler(CommandHandler("perbaiki", commands.perbaiki_command))

    # Premium commands and callbacks
    app.add_handler(CommandHandler("premium", premium.premium_command))
    app.add_handler(CommandHandler("statuspremium", premium.statuspremium_command))
    app.add_handler(CommandHandler("cancel", premium.cancel_command))
    app.add_handler(CallbackQueryHandler(premium.premium_callback, pattern="^premium_"))

    # OCR /insight premium commands
    app.add_handler(CommandHandler("ocr", messages.ocr_command))
    app.add_handler(CommandHandler("insight", commands.insight_command))
    app.add_handler(MessageHandler(filters.PHOTO, messages.handle_photo))
    app.add_handler(CallbackQueryHandler(messages.ocr_callback, pattern="^ocr:"))

    # Recurring bills /tagihan /reminder
    tagihan_handler = ConversationHandler(
        entry_points=[CommandHandler("tagihan", recurring.tagihan_command)],
        states={
            recurring.DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, recurring.tagihan_description)],
            recurring.AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recurring.tagihan_amount)],
            recurring.CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recurring.tagihan_category)],
            recurring.INTERVAL: [CallbackQueryHandler(recurring.tagihan_interval, pattern="^recur:interval:")],
            recurring.DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recurring.tagihan_date)],
            recurring.REMINDER: [CallbackQueryHandler(recurring.tagihan_reminder, pattern="^recur:reminder:")],
            recurring.CONFIRM: [CallbackQueryHandler(recurring.tagihan_confirm, pattern="^recur:confirm:")],
        },
        fallbacks=[CommandHandler("batal", recurring.tagihan_cancel)],
        per_message=False,
    )
    app.add_handler(tagihan_handler)
    app.add_handler(CommandHandler("reminder", recurring.reminder_command))

    # Payment handlers (Telegram Stars)
    for handler in payments.get_payment_handlers():
        app.add_handler(handler)

    # /catat ConversationHandler
    catat_handler = ConversationHandler(
        entry_points=[CommandHandler("catat", commands.catat_command)],
        states={
            commands.AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, commands.catat_amount)],
            commands.CATEGORY: [CallbackQueryHandler(commands.catat_category)],
            commands.CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, commands.catat_confirm)],
        },
        fallbacks=[CommandHandler("batal", commands.catat_cancel)],
        per_message=False,
    )
    app.add_handler(catat_handler)

    # /kategori ConversationHandler
    kategori_handler = ConversationHandler(
        entry_points=[CommandHandler("kategori", categories.kategori_command)],
        states={
            categories.SELECT_ACTION: [CallbackQueryHandler(categories.category_callback, pattern="^cat:")],
            categories.ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, categories.add_name)],
            categories.ADD_TYPE: [CallbackQueryHandler(categories.category_callback, pattern="^cat:type:")],
            categories.ADD_ICON: [MessageHandler(filters.TEXT & ~filters.COMMAND, categories.add_icon)],
            categories.EDIT_SELECT: [CallbackQueryHandler(categories.category_callback, pattern="^cat:(pick_edit|menu)")],
            categories.EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, categories.edit_name)],
            categories.DELETE_SELECT: [CallbackQueryHandler(categories.category_callback, pattern="^cat:(pick_delete|menu)")],
            categories.DELETE_CONFIRM: [CallbackQueryHandler(categories.category_callback, pattern="^cat:(confirm_delete|menu)")],
        },
        fallbacks=[CommandHandler("batal", categories.category_cancel)],
        per_message=False,
    )
    app.add_handler(kategori_handler)

    # /anggaran ConversationHandler
    anggaran_handler = ConversationHandler(
        entry_points=[CommandHandler("anggaran", budgets.anggaran_command)],
        states={
            budgets.BUDGET_CATEGORY: [CallbackQueryHandler(budgets.budget_category, pattern="^budget:")],
            budgets.BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, budgets.budget_amount)],
            budgets.BUDGET_PERIOD: [CallbackQueryHandler(budgets.budget_period, pattern="^budget:period:")],
            budgets.BUDGET_CONFIRM: [CallbackQueryHandler(budgets.budget_confirm, pattern="^budget:(confirm|del):")],
        },
        fallbacks=[CommandHandler("batal", budgets.budget_cancel)],
        per_message=False,
    )
    app.add_handler(anggaran_handler)

    # Natural language message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_natural_message))

    # WebApp data handler
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, auth.webapp_data_handler))

    # Unknown command handler (must be last)
    app.add_handler(MessageHandler(filters.COMMAND, commands.unknown_command))

    # Register recurring job queue to check due bills every hour
    app.job_queue.run_repeating(
        recurring_service.process_due,
        interval=3600,
        first=10,
        name="recurring_bills",
    )

    return app


async def main():
    """Start bot polling and web server."""
    settings = get_settings()
    app = build_bot()

    # Start web server for OAuth callbacks + Telegram webhook
    web_app = create_app(
        app.bot_data["oauth_manager"],
        app.bot_data["token_store"],
        subscription_service=app.bot_data["subscription_service"],
        midtrans_payment=app.bot_data["midtrans_payment"],
        pending_tokens=app.bot_data["pending_tokens"],
    )

    host = settings.dev_host
    port = settings.port

    if settings.webhook_url:
        web_app["_bot_app"] = app
        web_app.router.add_post("/webhook", _telegram_webhook)
        host = "0.0.0.0"

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Web server started on {host}:{port}")

    await app.initialize()
    await app.start()

    if settings.webhook_url:
        url = f"{settings.webhook_url}/webhook"
        await app.bot.set_webhook(url=url)
        logger.info(f"Webhook set to {url}")
    else:
        await app.updater.start_polling()

    logger.info("Bot started. Press Ctrl+C to stop.")

    stop = asyncio.Event()
    try:
        await stop.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        if settings.webhook_url:
            await app.bot.delete_webhook()
        else:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def _telegram_webhook(request: web.Request) -> web.Response:
    """Handle incoming Telegram webhook update."""
    app: Application = request.app["_bot_app"]
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return web.Response(text="ok")


if __name__ == "__main__":
    try:
        asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
    except RuntimeError:
        pass
    asyncio.run(main())
