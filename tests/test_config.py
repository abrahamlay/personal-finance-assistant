import pytest
from pydantic import ValidationError

from src.config import Settings, get_settings, _settings


@pytest.fixture
def reset_settings(monkeypatch):
    """Reset the cached settings singleton before each test."""
    monkeypatch.setattr("src.config._settings", None)


def test_settings_loads_from_env(reset_settings, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "test_telegram_token")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_google_id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_google_secret")
    monkeypatch.setenv("FERNET_KEY", "test_fernet_key")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://example.com/oauth/callback")
    monkeypatch.setenv("MIDTRANS_SERVER_KEY", "test_server_key")
    monkeypatch.setenv("MIDTRANS_CLIENT_KEY", "test_client_key")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")

    settings = get_settings()

    assert settings.telegram_token == "test_telegram_token"
    assert settings.google_client_id == "test_google_id"
    assert settings.google_client_secret == "test_google_secret"
    assert settings.fernet_key == "test_fernet_key"
    assert settings.webhook_url == "https://example.com/webhook"
    assert settings.oauth_redirect_uri == "https://example.com/oauth/callback"
    assert settings.midtrans_server_key == "test_server_key"
    assert settings.midtrans_client_key == "test_client_key"
    assert settings.gemini_api_key == "test_gemini_key"


def test_settings_default_values(reset_settings, monkeypatch):
    for name in [
        "WEBHOOK_URL",
        "OAUTH_REDIRECT_URI",
        "MIDTRANS_SERVER_KEY",
        "MIDTRANS_CLIENT_KEY",
        "GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FERNET_KEY", "key")

    settings = Settings(_env_file=None)

    assert settings.webhook_url == ""
    assert settings.oauth_redirect_uri == "http://localhost:8765/oauth/callback"
    assert settings.midtrans_server_key == ""
    assert settings.midtrans_client_key == ""
    assert settings.gemini_api_key == ""
    assert settings.dev_host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.bot_language == "id"
    assert settings.max_history_months_free == 3
    assert settings.premium_monthly_price_idr == 25000


def test_settings_missing_required_raises(reset_settings, monkeypatch):
    for name in ["TELEGRAM_TOKEN", "FERNET_KEY"]:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
