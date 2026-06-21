"""
Google OAuth 2.0 Manager for per-user Google Sheets access.
Uses google-auth-oauthlib for OAuth flow and google.oauth2.credentials for token management.
"""
import secrets
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from src.config import get_settings
from src.auth.token_store import TokenStore
from src.auth.encryption import decrypt_token


class OAuthManager:
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    
    def __init__(self, token_store: TokenStore):
        self.settings = get_settings()
        self.token_store = token_store
    
    def _build_client_config(self) -> dict:
        return {
            "web": {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.oauth_redirect_uri],
            }
        }
    
    def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Generate Google OAuth consent URL. Returns (url, state)."""
        if state is None:
            state = secrets.token_urlsafe(32)
        flow = Flow.from_client_config(
            self._build_client_config(),
            scopes=self.SCOPES,
            state=state,
        )
        flow.redirect_uri = self.settings.oauth_redirect_uri
        flow.code_verifier = None
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            code_challenge_method=None,
        )
        return auth_url, state
    
    def exchange_code(self, code: str, state: str | None = None) -> dict:
        """Exchange authorization code for tokens. Returns dict with keys: access_token, refresh_token, expiry."""
        flow = Flow.from_client_config(
            self._build_client_config(),
            scopes=self.SCOPES,
            state=state,
        )
        flow.redirect_uri = self.settings.oauth_redirect_uri
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expiry": credentials.expiry.timestamp() if credentials.expiry else None,
        }
    
    def refresh_access_token(self, refresh_token_str: str) -> Credentials:
        """Use stored refresh token to get new access token."""
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token_str,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        )
        credentials.refresh(Request())
        return credentials
    
    def store_credentials(self, telegram_id: str, token_data: dict, display_name: str = ""):
        """Store (or update) encrypted credentials in SQLite."""
        refresh_token = token_data.get("refresh_token", "")
        existing = self.token_store.get_user_token(telegram_id)
        if existing:
            self.token_store.update_user_token(
                telegram_id,
                access_token=token_data["access_token"],
                refresh_token=refresh_token,
                token_expiry=token_data.get("expiry", 0),
            )
        else:
            self.token_store.create_user_token(
                telegram_id=telegram_id,
                access_token=token_data["access_token"],
                refresh_token=refresh_token,
                token_expiry=token_data.get("expiry", 0),
                display_name=display_name,
            )
    
    def get_valid_credentials(self, telegram_id: str) -> Credentials | None:
        """Get valid Google credentials for a user. Auto-refreshes if expired."""
        import time
        user = self.token_store.get_user_token(telegram_id)
        if not user:
            return None
        refresh_token_str = decrypt_token(user["refresh_token"])
        credentials = Credentials(
            token=user["access_token"],
            refresh_token=refresh_token_str,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        )
        if user["token_expiry"] and user["token_expiry"] < time.time():
            credentials.refresh(Request())
            self.token_store.update_user_token(
                telegram_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=credentials.expiry.timestamp() if credentials.expiry else 0,
            )
        return credentials
