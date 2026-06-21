"""Category management handler: /kategori command."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from src.auth.token_store import TokenStore
from src.sheets.categories import SheetsCategories
from src.middleware import require_login


# Conversation states
SELECT_ACTION, ADD_NAME, ADD_TYPE, ADD_ICON, EDIT_SELECT, EDIT_NAME, DELETE_SELECT, DELETE_CONFIRM = range(
    200, 208
)


def _user_and_ss_id(context: ContextTypes.DEFAULT_TYPE, user) -> tuple[str, str]:
    token_store: TokenStore = context.bot_data["token_store"]
    user_token = token_store.get_user_token(str(user.id))
    return str(user.id), (user_token or {}).get("spreadsheet_id", "")


async def _show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Render the main /kategori inline menu."""
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]

    categories = sheets_categories.list_all(user_id, ss_id)
    lines = ["📂 *Kategori Kamu*\n"]
    for cat in categories:
        default_badge = " " if not cat.get("is_default") else " (default)"
        lines.append(f"{cat.get('icon', '📌')} {cat.get('nama', '')}{default_badge}")

    keyboard = [
        [InlineKeyboardButton("➕ Tambah Kategori", callback_data="cat:add")],
        [
            InlineKeyboardButton("✏️ Edit Nama", callback_data="cat:edit"),
            InlineKeyboardButton("🗑️ Hapus Kategori", callback_data="cat:delete"),
        ],
    ]

    text = "\n".join(lines)
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    return SELECT_ACTION


@require_login
async def kategori_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /kategori."""
    return await _show_category_menu(update, context)


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Dispatch callback queries from the /kategori menu."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cat:add":
        await query.edit_message_text("📝 Mau buat kategori apa? Ketik nama kategorinya.")
        return ADD_NAME

    if data == "cat:edit":
        return await _show_edit_select(update, context)

    if data == "cat:delete":
        return await _show_delete_select(update, context)

    if data == "cat:menu":
        return await _show_category_menu(update, context)

    if data.startswith("cat:type:"):
        cat_type = data.split(":", 2)[2]
        context.user_data["cat_new_type"] = cat_type
        await query.edit_message_text("🎨 Pilih icon? Ketik emoji (contoh: 🍔).")
        return ADD_ICON

    if data.startswith("cat:pick_edit:"):
        _, _, cat_id = data.split(":", 2)
        context.user_data["cat_edit_id"] = cat_id
        await query.edit_message_text("✏️ Ketik nama baru untuk kategori ini.")
        return EDIT_NAME

    if data.startswith("cat:pick_delete:"):
        _, _, cat_id = data.split(":", 2)
        context.user_data["cat_delete_id"] = cat_id
        user_id, ss_id = _user_and_ss_id(context, update.effective_user)
        sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]
        categories = sheets_categories.list_all(user_id, ss_id)
        cat_name = next(
            (c.get("nama", "") for c in categories if c.get("id") == cat_id), ""
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Ya, hapus", callback_data=f"cat:confirm_delete:{cat_id}"),
                InlineKeyboardButton("❌ Batal", callback_data="cat:menu"),
            ]
        ]
        await query.edit_message_text(
            f"🗑️ Yakin mau hapus kategori *{cat_name}*?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return DELETE_CONFIRM

    if data.startswith("cat:confirm_delete:"):
        _, _, cat_id = data.split(":", 2)
        return await _do_delete(update, context, cat_id)

    if data == "cat:cancel":
        await query.edit_message_text("❌ Dibatalkan.")
        return ConversationHandler.END

    return SELECT_ACTION


async def _show_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]
    query = update.callback_query

    categories = sheets_categories.list_all(user_id, ss_id)
    custom = [c for c in categories if not c.get("is_default")]
    if not custom:
        await query.edit_message_text("Belum ada kategori custom yang bisa diedit.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{c.get('icon', '📌')} {c.get('nama', '')}", callback_data=f"cat:pick_edit:{c['id']}")]
        for c in custom
    ]
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="cat:menu")])
    await query.edit_message_text(
        "✏️ Pilih kategori yang mau diedit:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return EDIT_SELECT


async def _show_delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]
    query = update.callback_query

    categories = sheets_categories.list_all(user_id, ss_id)
    custom = [c for c in categories if not c.get("is_default")]
    if not custom:
        await query.edit_message_text("Belum ada kategori custom yang bisa dihapus.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{c.get('icon', '📌')} {c.get('nama', '')}", callback_data=f"cat:pick_delete:{c['id']}")]
        for c in custom
    ]
    buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="cat:menu")])
    await query.edit_message_text(
        "🗑️ Pilih kategori yang mau dihapus:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return DELETE_SELECT


async def _do_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str) -> int:
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]
    query = update.callback_query

    result = sheets_categories.delete(user_id, ss_id, cat_id)
    if result.get("success"):
        await query.edit_message_text("✅ Kategori berhasil dihapus!")
    elif result.get("error") == "cannot_delete_default":
        await query.edit_message_text("⚠️ Kategori default tidak bisa dihapus.")
    else:
        await query.edit_message_text("⚠️ Kategori tidak ditemukan.")
    return ConversationHandler.END


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive new category name and ask for type."""
    context.user_data["cat_new_name"] = update.message.text.strip()
    keyboard = [
        [
            InlineKeyboardButton("📤 Pengeluaran", callback_data="cat:type:expense"),
            InlineKeyboardButton("💰 Pemasukan", callback_data="cat:type:income"),
        ]
    ]
    await update.message.reply_text(
        "Pilih tipe kategori:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_TYPE


async def add_icon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive icon and create the category."""
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]

    icon = update.message.text.strip() or "📌"
    name = context.user_data.get("cat_new_name", "")
    cat_type = context.user_data.get("cat_new_type", "expense")

    result = sheets_categories.add(user_id, ss_id, name, cat_type, icon)
    if result.get("success"):
        await update.message.reply_text(f"✅ Kategori *{name}* berhasil ditambahkan!", parse_mode="Markdown")
    elif result.get("error") == "free_tier_limit":
        await update.message.reply_text(
            "⚠️ Batas kategori custom gratis sudah tercapai (maksimal 5). Upgrade ke Premium untuk tambah lebih banyak."
        )
    else:
        await update.message.reply_text("⚠️ Gagal menambahkan kategori.")

    context.user_data.pop("cat_new_name", None)
    context.user_data.pop("cat_new_type", None)
    return ConversationHandler.END


async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive new name and rename the category."""
    user = update.effective_user
    user_id, ss_id = _user_and_ss_id(context, user)
    sheets_categories: SheetsCategories = context.bot_data["sheets_categories"]

    cat_id = context.user_data.get("cat_edit_id")
    new_name = update.message.text.strip()
    success = sheets_categories.rename(user_id, ss_id, cat_id, new_name)
    if success:
        await update.message.reply_text(f"✅ Kategori diubah menjadi *{new_name}*!", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Gagal mengubah nama kategori.")

    context.user_data.pop("cat_edit_id", None)
    return ConversationHandler.END


async def category_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the category conversation."""
    await update.message.reply_text("❌ Kelola kategori dibatalkan.")
    context.user_data.pop("cat_new_name", None)
    context.user_data.pop("cat_new_type", None)
    context.user_data.pop("cat_edit_id", None)
    context.user_data.pop("cat_delete_id", None)
    return ConversationHandler.END
