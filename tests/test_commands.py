"""Tests for general command handlers."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.handlers import commands


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Test"
    update.message = AsyncMock()
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    token_store = MagicMock()
    token_store.get_user_token.return_value = {"spreadsheet_id": "SS1", "access_token": "access_123"}
    token_store.get_active_subscription.return_value = {"plan": "monthly"}

    tx_service = MagicMock()
    tx_service.create.return_value = {
        "row_id": 7,
        "was_duplicate": False,
        "today_total": {"expense": 50000, "income": 0, "count": 1},
    }

    report_service = MagicMock()
    report_service.get_daily_summary.return_value = {
        "income": 0, "expense": 50000, "saldo": -50000, "count": 1,
        "category_breakdown": {"expense": {"Makanan": 50000}},
        "latest": [{"id": "7", "tipe": "expense", "kategori": "Makanan", "jumlah": 50000, "deskripsi": "makan"}],
    }
    report_service.get_weekly_summary.return_value = report_service.get_daily_summary.return_value
    report_service.get_monthly_summary.return_value = {
        **report_service.get_daily_summary.return_value,
        "previous": {"income": 0, "expense": 40000, "saldo": -40000},
        "comparison": {"income_pct": 0, "expense_pct": 25.0, "saldo_pct": -25.0},
    }
    report_service.generate_weekly_chart.return_value = "weekly.png"

    dashboard_generator = MagicMock()
    dashboard_generator.get_dashboard_url.return_value = "https://sheet.example.com/123"

    insight_service = AsyncMock()
    insight_service.analyze.return_value = "💡 Insight"

    context.bot_data = {
        "token_store": token_store,
        "tx_service": tx_service,
        "report_service": report_service,
        "dashboard_generator": dashboard_generator,
        "insight_service": insight_service,
        "subscription_service": MagicMock(),
        "oauth_manager": MagicMock(),
        "sheet_setup": MagicMock(),
        "pending_tokens": {},
    }
    context.user_data = {}
    context.args = []
    return context


@pytest.mark.asyncio
async def test_start_command_existing_user(fake_update, fake_context):
    await commands.start_command(fake_update, fake_context)
    fake_update.message.reply_text.assert_awaited_once()
    assert "siap pakai" in fake_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_start_command_new_user(fake_update, fake_context):
    fake_context.bot_data["token_store"].get_user_token.return_value = None
    await commands.start_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "/login" in text


@pytest.mark.asyncio
async def test_bantuan_command_lists_commands(fake_update, fake_context):
    await commands.bantuan_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "/catat" in text
    assert "/insight" in text


@pytest.mark.asyncio
async def test_export_command_placeholder(fake_update, fake_context):
    await commands.export_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "export" in text.lower()


@pytest.mark.asyncio
async def test_unknown_command(fake_update, fake_context):
    await commands.unknown_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "/bantuan" in text


@pytest.mark.asyncio
async def test_catat_command_asks_amount(fake_update, fake_context):
    state = await commands.catat_command(fake_update, fake_context)
    assert state == commands.AMOUNT
    assert "Berapa" in fake_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_catat_amount_parses_and_shows_categories(fake_update, fake_context):
    fake_update.message.text = "50rb"
    state = await commands.catat_amount(fake_update, fake_context)
    assert state == commands.CATEGORY
    assert fake_update.message.reply_text.call_args.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_catat_amount_invalid_retries(fake_update, fake_context):
    fake_update.message.text = "gratis"
    state = await commands.catat_amount(fake_update, fake_context)
    assert state == commands.AMOUNT


@pytest.mark.asyncio
async def test_catat_category_asks_description(fake_update, fake_context):
    fake_context.user_data["catat_amount"] = 50000
    query = AsyncMock()
    query.data = "1:Makanan:expense"
    fake_update.callback_query = query
    fake_update.message = None

    state = await commands.catat_category(fake_update, fake_context)

    assert state == commands.CONFIRM
    query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_catat_confirm_creates_transaction(fake_update, fake_context):
    fake_context.user_data.update({
        "catat_amount": 50000,
        "catat_category": "Makanan",
        "catat_tipe": "expense",
    })
    fake_update.message.text = "makan siang"

    state = await commands.catat_confirm(fake_update, fake_context)

    assert state == -1
    fake_context.bot_data["tx_service"].create.assert_called_once()


@pytest.mark.asyncio
async def test_catat_cancel_clears_user_data(fake_update, fake_context):
    fake_context.user_data["catat_amount"] = 50000
    state = await commands.catat_cancel(fake_update, fake_context)
    assert state == -1
    assert "catat_amount" not in fake_context.user_data


@pytest.mark.asyncio
async def test_edit_command_success(fake_update, fake_context):
    fake_update.message.text = "/edit 5 kategori Makanan"
    fake_context.bot_data["tx_service"].update.return_value = True

    await commands.edit_command(fake_update, fake_context)

    fake_context.bot_data["tx_service"].update.assert_called_once_with(
        "123", "SS1", 5, kategori="Makanan"
    )


@pytest.mark.asyncio
async def test_edit_command_wrong_format(fake_update, fake_context):
    fake_update.message.text = "/edit 5"
    await commands.edit_command(fake_update, fake_context)
    fake_context.bot_data["tx_service"].update.assert_not_called()


@pytest.mark.asyncio
async def test_hapus_command_success(fake_update, fake_context):
    fake_update.message.text = "/hapus 5"
    fake_context.bot_data["tx_service"].delete.return_value = True

    await commands.hapus_command(fake_update, fake_context)

    fake_context.bot_data["tx_service"].delete.assert_called_once_with("123", "SS1", 5)


@pytest.mark.asyncio
async def test_hariini_command_shows_summary(fake_update, fake_context):
    await commands.hariini_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Laporan Hari Ini" in text


@pytest.mark.asyncio
async def test_mingguan_command_sends_chart(fake_update, fake_context):
    with patch("os.path.exists", return_value=True), \
         patch("os.remove"), \
         patch("builtins.open", MagicMock()):
        fake_update.message.reply_photo = AsyncMock()
        await commands.mingguan_command(fake_update, fake_context)

    fake_update.message.reply_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulanan_command_shows_summary_and_link(fake_update, fake_context):
    await commands.bulanan_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Laporan Bulan Ini" in text
    assert "Dashboard" in text


@pytest.mark.asyncio
async def test_dashboard_command_sends_link(fake_update, fake_context):
    await commands.dashboard_command(fake_update, fake_context)
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Dashboard Keuangan" in text


@pytest.mark.asyncio
async def test_perbaiki_command_success(fake_update, fake_context):
    await commands.perbaiki_command(fake_update, fake_context)
    assert fake_update.message.reply_text.call_count == 2
    assert "berhasil" in fake_update.message.reply_text.call_args_list[1][0][0]


@pytest.mark.asyncio
async def test_insight_command_sends_insight(fake_update, fake_context):
    await commands.insight_command(fake_update, fake_context)
    fake_context.bot_data["insight_service"].analyze.assert_awaited_once()
    assert fake_update.message.reply_text.call_count == 2


@pytest.mark.asyncio
async def test_verify_command_uses_pending_token(fake_update, fake_context):
    """If the OAuth callback stored a pending token, /verify consumes it."""
    fake_update.message.text = "/verify authcode state123"
    fake_context.args = ["authcode", "state123"]
    fake_context.bot_data["pending_tokens"] = {
        "state123": {"access_token": "tok", "refresh_token": "ref", "expiry": 9999999999},
    }
    fake_context.bot_data["sheet_setup"].setup_new_user.return_value = "SS_NEW"

    await commands.verify_command(fake_update, fake_context)

    fake_context.bot_data["oauth_manager"].store_credentials.assert_called_once()
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Login berhasil" in text


@pytest.mark.asyncio
async def test_verify_command_idempotent_when_already_logged_in(fake_update, fake_context):
    """/verify succeeds without re-exchanging an already-used code."""
    fake_update.message.text = "/verify authcode state123"
    fake_context.args = ["authcode", "state123"]
    fake_context.bot_data["pending_tokens"] = {}
    fake_context.bot_data["token_store"].get_user_token.return_value = {
        "access_token": "existing_tok", "spreadsheet_id": "SS1",
    }

    await commands.verify_command(fake_update, fake_context)

    fake_context.bot_data["oauth_manager"].exchange_code.assert_not_called()
    fake_context.bot_data["oauth_manager"].store_credentials.assert_not_called()
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Login berhasil" in text


@pytest.mark.asyncio
async def test_verify_command_falls_back_to_exchange(fake_update, fake_context):
    """Without a pending token and not logged in, /verify exchanges the code."""
    fake_update.message.text = "/verify authcode state123"
    fake_context.args = ["authcode", "state123"]
    fake_context.bot_data["pending_tokens"] = {}
    fake_context.bot_data["token_store"].get_user_token.return_value = None
    fake_context.bot_data["oauth_manager"].exchange_code.return_value = {
        "access_token": "tok", "refresh_token": "ref", "expiry": 9999999999,
    }
    fake_context.bot_data["sheet_setup"].setup_new_user.return_value = "SS_NEW"

    await commands.verify_command(fake_update, fake_context)

    fake_context.bot_data["oauth_manager"].exchange_code.assert_called_once_with("authcode", "state123")
    fake_context.bot_data["oauth_manager"].store_credentials.assert_called_once()
    text = fake_update.message.reply_text.call_args[0][0]
    assert "Login berhasil" in text


@pytest.mark.asyncio
async def test_verify_command_invalid_code(fake_update, fake_context):
    """An invalid/already-used code without a stored token shows expiry error."""
    fake_update.message.text = "/verify badcode state123"
    fake_context.args = ["badcode", "state123"]
    fake_context.bot_data["pending_tokens"] = {}
    fake_context.bot_data["token_store"].get_user_token.return_value = None
    fake_context.bot_data["oauth_manager"].exchange_code.side_effect = Exception("invalid grant")

    await commands.verify_command(fake_update, fake_context)

    text = fake_update.message.reply_text.call_args[0][0]
    assert "kedaluwarsa" in text
