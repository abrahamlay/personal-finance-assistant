"""Test /login and /logout handlers."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.handlers import auth


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
    context.bot_data = {
        "token_store": MagicMock(),
        "oauth_manager": MagicMock(),
    }
    return context


@pytest.mark.asyncio
async def test_login_sends_webapp_button(fake_update, fake_context):
    """/login sends inline keyboard with WebApp button."""
    with patch("src.handlers.auth.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.oauth_redirect_uri = "http://localhost:8080/oauth/callback"
        mock_get_settings.return_value = mock_settings

        await auth.login_command(fake_update, fake_context)

        fake_update.message.reply_text.assert_called_once()
        args, kwargs = fake_update.message.reply_text.call_args
        assert "Login Google Sheet" in args[0]
        assert "reply_markup" in kwargs
        reply_markup = kwargs["reply_markup"]
        assert len(reply_markup.inline_keyboard) == 2


@pytest.mark.asyncio
async def test_logout_deletes_user_token(fake_update, fake_context):
    """/logout calls delete_user_token."""
    token_store = fake_context.bot_data["token_store"]
    token_store.get_user_token.return_value = {"spreadsheet_id": "abc123"}

    await auth.logout_command(fake_update, fake_context)

    token_store.delete_user_token.assert_called_once_with("123")
    fake_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_logout_when_not_logged_in(fake_update, fake_context):
    """/logout when user has no token shows message."""
    token_store = fake_context.bot_data["token_store"]
    token_store.get_user_token.return_value = None

    await auth.logout_command(fake_update, fake_context)

    token_store.delete_user_token.assert_not_called()
    fake_update.message.reply_text.assert_called_once_with("Kamu belum login.")
