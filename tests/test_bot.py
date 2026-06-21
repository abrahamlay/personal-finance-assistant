"""Test bot startup and handler registration."""
from unittest.mock import MagicMock, patch, ANY
import pytest
from telegram.ext import Application, ConversationHandler, CommandHandler

from src.bot import build_bot


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.telegram_token = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234"
    settings.oauth_redirect_uri = "http://localhost:8080/oauth/callback"
    return settings


def test_bot_builds_without_errors(mock_settings):
    """Application builder creates app without crashing."""
    with patch("src.bot.get_settings", return_value=mock_settings), \
         patch("src.bot.TokenStore") as MockTokenStore, \
         patch("src.bot.OAuthManager"), \
         patch("src.bot.SheetsClient"), \
         patch("src.bot.SheetSetupService"), \
         patch("src.bot.DashboardGenerator"), \
         patch("src.bot.ReportService"), \
         patch("src.bot.MemoryCache"), \
         patch("src.bot.OCRService"), \
         patch("src.bot.RecurringService"), \
         patch("src.bot.InsightService"), \
         patch("src.bot.create_app"):

        MockTokenStore.return_value.init_db = MagicMock()
        app = build_bot()
        assert isinstance(app, Application)


def test_command_handlers_registered(mock_settings):
    """Verify key commands are registered, including onboarding ConversationHandler."""
    with patch("src.bot.get_settings", return_value=mock_settings), \
         patch("src.bot.TokenStore") as MockTokenStore, \
         patch("src.bot.OAuthManager"), \
         patch("src.bot.SheetsClient"), \
         patch("src.bot.SheetSetupService"), \
         patch("src.bot.DashboardGenerator"), \
         patch("src.bot.ReportService"), \
         patch("src.bot.MemoryCache"), \
         patch("src.bot.OCRService"), \
         patch("src.bot.RecurringService"), \
         patch("src.bot.InsightService"), \
         patch("src.bot.create_app"):

        MockTokenStore.return_value.init_db = MagicMock()
        app = build_bot()

        registered_commands = set()
        conversation_handlers = []
        for handler in app.handlers[0]:
            if isinstance(handler, ConversationHandler):
                conversation_handlers.append(handler)
                for entry in handler.entry_points:
                    if isinstance(entry, CommandHandler):
                        registered_commands.update(entry.commands)
            elif hasattr(handler, "commands"):
                registered_commands.update(handler.commands)

        assert len(conversation_handlers) >= 4, "expected onboarding, /catat, /kategori, /anggaran, /tagihan ConversationHandlers"
        assert "start" in registered_commands
        assert "login" in registered_commands
        assert "logout" in registered_commands
        assert "bantuan" in registered_commands
        assert "export" in registered_commands
        assert "catat" in registered_commands
        assert "kategori" in registered_commands
        assert "anggaran" in registered_commands
        assert "edit" in registered_commands
        assert "hapus" in registered_commands
        assert "hariini" in registered_commands
        assert "mingguan" in registered_commands
        assert "bulanan" in registered_commands
        assert "dashboard" in registered_commands
        assert "perbaiki" in registered_commands
        assert "premium" in registered_commands
        assert "statuspremium" in registered_commands
        assert "cancel" in registered_commands
        assert "insight" in registered_commands
        assert "ocr" in registered_commands
        assert "tagihan" in registered_commands
        assert "reminder" in registered_commands
