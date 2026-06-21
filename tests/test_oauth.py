import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from src.auth.oauth import OAuthManager
from src.auth.token_store import TokenStore


@pytest.fixture
def valid_key(monkeypatch):
    key = Fernet.generate_key().decode()
    for env_name, value in {
        "TELEGRAM_TOKEN": "token",
        "GOOGLE_CLIENT_ID": "google-client-id",
        "GOOGLE_CLIENT_SECRET": "google-client-secret",
        "OAUTH_REDIRECT_URI": "http://localhost:8080/oauth/callback",
        "FERNET_KEY": key,
    }.items():
        monkeypatch.setenv(env_name, value)
    monkeypatch.setattr("src.config._settings", None)
    return key


@pytest.fixture
def token_store(valid_key, tmp_path):
    db_path = tmp_path / "test_oauth.db"
    store = TokenStore(str(db_path))
    store.init_db()
    return store


@pytest.fixture
def oauth_manager(token_store):
    return OAuthManager(token_store)


def test_generate_auth_url_contains_drive_file_scope(oauth_manager):
    with patch("src.auth.oauth.Flow") as MockFlow:
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?scope=drive.file", "state123")
        MockFlow.from_client_config.return_value = mock_flow

        url, state = oauth_manager.get_authorization_url()

        assert "drive.file" in url or "https://www.googleapis.com/auth/drive.file" in " ".join(oauth_manager.SCOPES)
        MockFlow.from_client_config.assert_called_once()


def test_generate_auth_url_has_offline_access_type(oauth_manager):
    with patch("src.auth.oauth.Flow") as MockFlow:
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?access_type=offline", "state123")
        MockFlow.from_client_config.return_value = mock_flow

        url, state = oauth_manager.get_authorization_url()

        _, kwargs = mock_flow.authorization_url.call_args
        assert kwargs.get("access_type") == "offline"


def test_exchange_code_returns_tokens(oauth_manager):
    with patch("src.auth.oauth.Flow") as MockFlow:
        mock_credentials = MagicMock()
        mock_credentials.token = "access_token_123"
        mock_credentials.refresh_token = "refresh_token_456"
        mock_credentials.expiry = datetime(2099, 1, 1, tzinfo=timezone.utc)

        mock_flow = MagicMock()
        mock_flow.credentials = mock_credentials
        MockFlow.from_client_config.return_value = mock_flow

        result = oauth_manager.exchange_code("auth_code", "state123")

        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_456"
        assert result["expiry"] == datetime(2099, 1, 1, tzinfo=timezone.utc).timestamp()
        mock_flow.fetch_token.assert_called_once_with(code="auth_code")


def test_refresh_token_returns_new_access(oauth_manager):
    with patch("src.auth.oauth.Credentials") as MockCredentials:
        mock_creds = MagicMock()
        mock_creds.token = "new_access_token"
        MockCredentials.return_value = mock_creds

        result = oauth_manager.refresh_access_token("refresh_token_456")

        mock_creds.refresh.assert_called_once()
        assert result is mock_creds


def test_store_credentials_encrypts_refresh_token(oauth_manager, token_store):
    token_data = {
        "access_token": "access_token_123",
        "refresh_token": "refresh_token_456",
        "expiry": time.time() + 3600,
    }

    oauth_manager.store_credentials("telegram_123", token_data, display_name="Test User")

    user = token_store.get_user_token("telegram_123")
    assert user is not None
    assert user["telegram_id"] == "telegram_123"
    assert user["access_token"] == "access_token_123"
    assert user["refresh_token"] == "refresh_token_456"
    assert user["display_name"] == "Test User"


def test_get_valid_credentials_returns_none_for_unknown_user(oauth_manager):
    result = oauth_manager.get_valid_credentials("unknown_user")
    assert result is None
