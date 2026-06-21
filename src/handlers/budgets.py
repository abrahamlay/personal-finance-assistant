"""Budget management handler: /anggaran command."""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from src.auth.token_store import TokenStore
from src.sheets.categories import SheetsCategories
from src.services.budget_service import BudgetService
from src.services.parser_service import normalize_amount
from src.middleware import require_login


# Conversation states
BUDGET_CATEGORY, BUDGET_AMOUNT, BUDGET_PERIOD, BUDGET_CONFIRM = range(300, 304)


def _user_and_ss_id(context: ContextTypes.DEFAULT_TYPE, user) -> tuple[str, str]:
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(user.id))
    return str(user.id), (user_token or {}).get("spreadsheet_id", "")


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def _format_rupiah(amount: int) -> str:
    if amount >= 1_000_000:
        return f"Rp {amount/1_000_000:.1f}jt".replace(".0", "")
    if amount >= 1_000:
        return f"Rp {amount//1_000}k"
    return f"Rp {amount:,}"


@require_login
async def anggaran_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /anggaran: show current budgets and action buttons."""
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    budget_service: BudgetService = context.bot_data["budget_service"]
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]

    month_str = _current_month()
    categories = sheets_categories.list_all(user_id, ss_id)
    budgets = budget_service.budgets.list_all(user_id, ss_id, month_str)

    lines = [f"📊 *Budget Bulan Ini ({month_str})*\n"]
    for budget in budgets:
        usage = budget_service.get_usage(user_id, ss_id, budget["kategori"], month_str)
        pct = usage.get("percentage", 0)
        emoji = ""
        for threshold, e in [(100, "🚨"), (90, "🔴"), (80, "⚠️"), (50, "💡")]:
            if pct >= threshold:
                emoji = e
                break
        lines.append(
            f"• {budget['kategori']}: {_format_rupiah(budget['terpakai'])} / "
            f"{_format_rupiah(budget['jumlah_bulan'])} ({pct:.0f}%) {emoji}"
        )

    if not budgets:
        lines.append("Belum ada budget untuk bulan ini.")

    keyboard = [
        [
            InlineKeyboardButton("➕ Set Budget Baru", callback_data="budget:set"),
            InlineKeyboardButton("🗑️ Hapus Budget", callback_data="budget:delete"),
        ]
    ]

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return BUDGET_CATEGORY


async def budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category selection when setting or deleting a budget."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]

    categories = sheets_categories.list_all(user_id, ss_id)

    if data == "budget:set":
        context.user_data["budget_action"] = "set"
        buttons = [
            [InlineKeyboardButton(f"{c.get('icon', '📌')} {c.get('nama', '')}", callback_data=f"budget:cat:{c['id']}:{c['nama']}")]
            for c in categories
        ]
        await query.edit_message_text(
            "Pilih kategori untuk budget:", reply_markup=InlineKeyboardMarkup(buttons)
        )
        return BUDGET_AMOUNT

    if data == "budget:delete":
        context.user_data["budget_action"] = "delete"
        budget_service: BudgetService = context.bot_data["budget_service"]
        month_str = _current_month()
        budgets = budget_service.budgets.list_all(user_id, ss_id, month_str)
        if not budgets:
            await query.edit_message_text("Belum ada budget yang bisa dihapus.")
            return ConversationHandler.END
        buttons = [
            [InlineKeyboardButton(b["kategori"], callback_data=f"budget:del:{b['kategori']}")]
            for b in budgets
        ]
        await query.edit_message_text(
            "Pilih budget yang mau dihapus:", reply_markup=InlineKeyboardMarkup(buttons)
        )
        return BUDGET_CONFIRM

    if data.startswith("budget:cat:"):
        _, _, _, cat_name = data.split(":", 3)
        context.user_data["budget_category"] = cat_name
        await query.edit_message_text(
            f"💰 Budget untuk *{cat_name}* berapa?\nContoh: `500rb` atau `500000`",
            parse_mode="Markdown",
        )
        return BUDGET_AMOUNT

    if data.startswith("budget:del:"):
        _, _, cat_name = data.split(":", 2)
        budget_service: BudgetService = context.bot_data["budget_service"]
        month_str = _current_month()
        budget_service.budgets.delete(user_id, ss_id, cat_name, month_str)
        await query.edit_message_text(f"✅ Budget *{cat_name}* dihapus.", parse_mode="Markdown")
        return ConversationHandler.END

    return BUDGET_CATEGORY


async def budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse amount input and ask for period."""
    text = update.message.text.strip()
    amount, _ = normalize_amount(text)
    if amount == 0:
        await update.message.reply_text(
            "⚠️ Gak bisa baca jumlah. Coba lagi ya. Contoh: `500rb` atau `500000`",
            parse_mode="Markdown",
        )
        return BUDGET_AMOUNT

    context.user_data["budget_amount"] = amount
    keyboard = [
        [
            InlineKeyboardButton("📅 Bulanan", callback_data="budget:period:bulanan"),
            InlineKeyboardButton("📆 Mingguan", callback_data="budget:period:mingguan"),
        ]
    ]
    await update.message.reply_text(
        "Pilih periode budget:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUDGET_PERIOD


async def budget_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture period and show confirmation."""
    query = update.callback_query
    await query.answer()
    data = query.data

    period = data.split(":", 2)[2] if data.startswith("budget:period:") else "bulanan"
    context.user_data["budget_period"] = period

    category = context.user_data.get("budget_category", "")
    amount = context.user_data.get("budget_amount", 0)

    keyboard = [
        [
            InlineKeyboardButton("✅ Ya", callback_data="budget:confirm:yes"),
            InlineKeyboardButton("❌ Batal", callback_data="budget:confirm:no"),
        ]
    ]
    await query.edit_message_text(
        f"Konfirmasi: Budget *{category}* {_format_rupiah(amount)}/{period}?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return BUDGET_CONFIRM


async def budget_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save, cancel, or delete a budget."""
    query = update.callback_query
    await query.answer()
    data = query.data

    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    budget_service: BudgetService = context.bot_data["budget_service"]
    month_str = _current_month()

    # Handle delete confirmation callbacks.
    if data.startswith("budget:del:"):
        _, _, category = data.split(":", 2)
        budget_service.budgets.delete(user_id, ss_id, category, month_str)
        await query.edit_message_text(f"✅ Budget *{category}* dihapus.", parse_mode="Markdown")
        _clear_budget_context(context)
        return ConversationHandler.END

    if data != "budget:confirm:yes":
        await query.edit_message_text("❌ Penyimpanan budget dibatalkan.")
        _clear_budget_context(context)
        return ConversationHandler.END

    category = context.user_data.get("budget_category", "")
    amount = context.user_data.get("budget_amount", 0)
    period = context.user_data.get("budget_period", "bulanan")

    result = budget_service.set_budget(
        user_id, ss_id, category, amount, period, month_str
    )
    if result.get("success"):
        await query.edit_message_text(
            f"✅ Budget *{category}* {_format_rupiah(amount)}/{period} disimpan!",
            parse_mode="Markdown",
        )
    elif result.get("error") == "free_tier_limit":
        await query.edit_message_text(
            "⚠️ Versi gratis hanya bisa punya 1 budget. Upgrade ke Premium untuk budget tak terbatas."
        )
    else:
        await query.edit_message_text("⚠️ Gagal menyimpan budget.")

    _clear_budget_context(context)
    return ConversationHandler.END


async def budget_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel /anggaran conversation."""
    await update.message.reply_text("❌ Pengaturan budget dibatalkan.")
    _clear_budget_context(context)
    return ConversationHandler.END


def _clear_budget_context(context: ContextTypes.DEFAULT_TYPE):
    for key in ["budget_category", "budget_amount", "budget_period", "budget_action"]:
        context.user_data.pop(key, None)
