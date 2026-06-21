"""Tests for /kategori handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import InlineKeyboardMarkup

from src.handlers.categories import (
    kategori_command,
    category_callback,
    add_name,
    add_icon,
    edit_name,
    SELECT_ACTION,
    ADD_NAME,
    ADD_TYPE,
    ADD_ICON,
    EDIT_SELECT,
    EDIT_NAME,
    DELETE_CONFIRM,
    ConversationHandler,
)
from src.sheets.categories import SheetsCategories
from src.auth.token_store import TokenStore


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Test"
    update.message = AsyncMock()
    update.message.text = "/kategori"
    update.callback_query = AsyncMock()
    update.callback_query.data = "cat:menu"
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock(spec=TokenStore)
    token_store.get_user_token.return_value = {"spreadsheet_id": "SPREADSHEET_ID"}

    sheets_categories = MagicMock(spec=SheetsCategories)
    sheets_categories.list_all.return_value = [
        {"id": "1", "nama": "Makanan", "tipe": "expense", "is_default": True, "icon": "🍔"},
        {"id": "14", "nama": "Custom", "tipe": "expense", "is_default": False, "icon": "🎯"},
    ]
    sheets_categories.add.return_value = {"success": True, "id": 15}
    sheets_categories.rename.return_value = True
    sheets_categories.delete.return_value = {"success": True}

    context.bot_data = {
        "token_store": token_store,
        "sheets_categories": sheets_categories,
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_kategori_command_shows_menu(fake_update, fake_context):
    fake_update.callback_query = None
    state = await kategori_command(fake_update, fake_context)

    assert state == SELECT_ACTION
    fake_update.message.reply_text.assert_called_once()
    text, kwargs = fake_update.message.reply_text.call_args
    assert "Makanan" in text[0]
    assert "Custom" in text[0]
    assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_callback_add_asks_name(fake_update, fake_context):
    fake_update.callback_query.data = "cat:add"
    state = await category_callback(fake_update, fake_context)

    assert state == ADD_NAME
    fake_update.callback_query.edit_message_text.assert_called_once()
    assert "kategori" in fake_update.callback_query.edit_message_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_add_name_asks_type(fake_update, fake_context):
    fake_update.message.text = "Hobi"
    state = await add_name(fake_update, fake_context)

    assert state == ADD_TYPE
    fake_update.message.reply_text.assert_called_once()
    text, kwargs = fake_update.message.reply_text.call_args
    assert "tipe" in text[0].lower()


@pytest.mark.asyncio
async def test_callback_type_asks_icon(fake_update, fake_context):
    fake_update.callback_query.data = "cat:type:expense"
    state = await category_callback(fake_update, fake_context)

    assert state == ADD_ICON
    fake_update.callback_query.edit_message_text.assert_called_once()
    assert "icon" in fake_update.callback_query.edit_message_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_add_icon_creates_category(fake_update, fake_context):
    fake_context.user_data["cat_new_name"] = "Hobi"
    fake_context.user_data["cat_new_type"] = "expense"
    fake_update.message.text = "🎨"

    state = await add_icon(fake_update, fake_context)

    assert state == ConversationHandler.END
    sheets_categories = fake_context.bot_data["sheets_categories"]
    sheets_categories.add.assert_called_once_with("123", "SPREADSHEET_ID", "Hobi", "expense", "🎨")
    fake_update.message.reply_text.assert_called_once()
    assert "ditambahkan" in fake_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_edit_shows_custom_only(fake_update, fake_context):
    fake_update.callback_query.data = "cat:edit"
    state = await category_callback(fake_update, fake_context)

    assert state == EDIT_SELECT
    fake_update.callback_query.edit_message_text.assert_called_once()
    args, kwargs = fake_update.callback_query.edit_message_text.call_args
    reply_markup = kwargs["reply_markup"]
    button_texts = [
        btn.text for row in reply_markup.inline_keyboard for btn in row
    ]
    assert any("Custom" in t for t in button_texts)
    assert not any("Makanan" in t for t in button_texts)


@pytest.mark.asyncio
async def test_edit_name_renames_category(fake_update, fake_context):
    fake_context.user_data["cat_edit_id"] = "14"
    fake_update.message.text = "Custom Baru"

    state = await edit_name(fake_update, fake_context)

    assert state == ConversationHandler.END
    sheets_categories = fake_context.bot_data["sheets_categories"]
    sheets_categories.rename.assert_called_once_with("123", "SPREADSHEET_ID", "14", "Custom Baru")


@pytest.mark.asyncio
async def test_callback_delete_confirms_custom(fake_update, fake_context):
    fake_update.callback_query.data = "cat:pick_delete:14"
    state = await category_callback(fake_update, fake_context)

    assert state == DELETE_CONFIRM
    fake_update.callback_query.edit_message_text.assert_called_once()
    text = fake_update.callback_query.edit_message_text.call_args[0][0]
    assert "hapus" in text.lower()
