"""Test onboarding wizard ConversationHandler."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram.ext import ConversationHandler

from src.handlers import onboarding


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("src.handlers.onboarding.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.oauth_redirect_uri = "http://localhost:8080/oauth/callback"
        mock_get_settings.return_value = mock_settings
        yield


@pytest.fixture
def fake_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    update.effective_user.first_name = "Toni"
    update.message = AsyncMock()
    update.message.text = None
    update.callback_query = None
    return update


@pytest.fixture
def fake_context():
    context = MagicMock()
    context.bot_data = {
        "token_store": MagicMock(),
        "oauth_manager": MagicMock(),
        "sheet_setup": MagicMock(),
        "subscription_service": MagicMock(),
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_start_onboarding_new_user_asks_name(fake_update, fake_context):
    """/start from new user returns name prompt in step NAME."""
    fake_context.bot_data["token_store"].get_user_token.return_value = None

    state = await onboarding.start_onboarding(fake_update, fake_context)

    assert state == onboarding.NAME
    fake_update.message.reply_text.assert_called_once()
    args, _ = fake_update.message.reply_text.call_args
    assert "nama panggilan" in args[0].lower()


@pytest.mark.asyncio
async def test_start_onboarding_existing_user_shows_welcome_back(fake_update, fake_context):
    """Already onboarded user sees welcome back, not wizard."""
    fake_context.bot_data["token_store"].get_user_token.return_value = {
        "spreadsheet_id": "abc123"
    }

    state = await onboarding.start_onboarding(fake_update, fake_context)

    assert state == ConversationHandler.END
    args, _ = fake_update.message.reply_text.call_args
    assert "sudah siap pakai" in args[0]


@pytest.mark.asyncio
async def test_name_step_skip_uses_telegram_first_name(fake_update, fake_context):
    """Clicking Skip in NAME step uses Telegram first_name."""
    fake_update.message.text = "⏭ Skip / Lewati"

    state = await onboarding.name_step(fake_update, fake_context)

    assert fake_context.user_data["display_name"] == "Toni"
    assert state == onboarding.AUTH


@pytest.mark.asyncio
async def test_name_step_accepts_text_input(fake_update, fake_context):
    """Text input in NAME step stores display_name."""
    fake_update.message.text = "Budi"

    state = await onboarding.name_step(fake_update, fake_context)

    assert fake_context.user_data["display_name"] == "Budi"
    assert state == onboarding.AUTH


@pytest.mark.asyncio
async def test_name_step_sends_auth_options(fake_update, fake_context):
    """AUTH step entry shows Google Login WebApp button + manual + offline options."""
    fake_update.message.text = "Budi"

    with patch("src.handlers.onboarding.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"
        mock_get_settings.return_value = mock_settings

        await onboarding.name_step(fake_update, fake_context)

        args, kwargs = fake_update.message.reply_text.call_args
        assert "sambungkan Google Sheet" in args[0]
        assert "reply_markup" in kwargs
        inline_keyboard = kwargs["reply_markup"].inline_keyboard
        assert len(inline_keyboard) == 3
        labels = [btn.text for row in inline_keyboard for btn in row]
        assert any("Login dengan Google" in label for label in labels)
        assert any("Login Manual" in label for label in labels)
        assert any("Mode Offline" in label for label in labels)


@pytest.mark.asyncio
async def test_auth_step_offline_mode_skips_sheet_creation(fake_update, fake_context):
    """Choosing offline mode skips sheet setup."""
    query = AsyncMock()
    query.data = "auth_offline"
    fake_update.callback_query = query
    fake_update.message = None

    state = await onboarding.auth_step(fake_update, fake_context)

    assert state == onboarding.TUTORIAL
    query.edit_message_text.assert_called_once()
    fake_context.bot_data["sheet_setup"].setup_new_user.assert_not_called()


@pytest.mark.asyncio
async def test_auth_step_manual_mode_shows_instructions(fake_update, fake_context):
    """Choosing manual mode shows authorization URL instructions."""
    query = AsyncMock()
    query.data = "auth_manual"
    fake_update.callback_query = query
    fake_update.message = None

    fake_context.bot_data["oauth_manager"].get_authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?test=1",
        "state123",
    )

    state = await onboarding.auth_step(fake_update, fake_context)

    assert state == onboarding.AUTH
    query.edit_message_text.assert_called_once()
    args, _ = query.edit_message_text.call_args
    assert "Login Manual" in args[0]


@pytest.mark.asyncio
async def test_auth_step_google_mode_creates_sheet(fake_update, fake_context):
    """Valid auth code triggers sheet creation and moves to trial step."""
    fake_context.user_data["display_name"] = "Budi"
    fake_update.message.text = "authcode123"

    oauth_manager = fake_context.bot_data["oauth_manager"]
    oauth_manager.exchange_code.return_value = {
        "access_token": "token123",
        "refresh_token": "refresh123",
        "expiry": 9999999999,
    }

    token_store = fake_context.bot_data["token_store"]
    token_store.get_user_token.return_value = {"access_token": "token123"}

    sheet_setup = fake_context.bot_data["sheet_setup"]
    sheet_setup.setup_new_user.return_value = "sheet_id_123"

    state = await onboarding.auth_step(fake_update, fake_context)

    assert state == onboarding.DONE
    oauth_manager.exchange_code.assert_called_once_with("authcode123")
    sheet_setup.setup_new_user.assert_called_once_with("123", "Budi")
    assert fake_context.user_data["spreadsheet_id"] == "sheet_id_123"


@pytest.mark.asyncio
async def test_done_step_trial_start_creates_subscription(fake_update, fake_context):
    """Clicking trial creates 7-day trial subscription in SQLite."""
    query = AsyncMock()
    query.data = "trial_start"
    query.message = AsyncMock()
    fake_update.callback_query = query
    fake_update.message = None

    subscription_service = fake_context.bot_data["subscription_service"]
    subscription_service.start_free_trial.return_value = {"id": 1}

    state = await onboarding.done_step(fake_update, fake_context)

    assert state == onboarding.TUTORIAL
    subscription_service.start_free_trial.assert_called_once_with("123")


@pytest.mark.asyncio
async def test_done_step_trial_skip_shows_upgrade_message(fake_update, fake_context):
    """Skipping trial shows upgrade prompt."""
    query = AsyncMock()
    query.data = "trial_skip"
    query.message = AsyncMock()
    fake_update.callback_query = query
    fake_update.message = None

    subscription_service = fake_context.bot_data["subscription_service"]

    state = await onboarding.done_step(fake_update, fake_context)

    assert state == onboarding.TUTORIAL
    subscription_service.start_free_trial.assert_not_called()
    query.edit_message_text.assert_called_once()
    args, _ = query.edit_message_text.call_args
    assert "/premium" in args[0]


@pytest.mark.asyncio
async def test_tutorial_step_ends_conversation(fake_update, fake_context):
    """TUTORIAL step ends conversation and shows final message."""
    query = AsyncMock()
    query.data = "tutorial_try"
    fake_update.callback_query = query
    fake_update.message = None

    state = await onboarding.tutorial_step(fake_update, fake_context)

    assert state == ConversationHandler.END
    query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_command_ends_wizard(fake_update, fake_context):
    """/cancel during wizard ends conversation and clears user_data."""
    fake_update.message.text = "/cancel"
    fake_context.user_data["foo"] = "bar"

    state = await onboarding.cancel_onboarding(fake_update, fake_context)

    assert state == ConversationHandler.END
    assert fake_context.user_data == {}


def test_conversation_timeout():
    """Test timeout handling (10 min)."""
    handler = onboarding.get_onboarding_handler()
    assert handler.conversation_timeout == 600
