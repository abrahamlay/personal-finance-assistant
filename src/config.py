from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Telegram
    telegram_token: str = Field(alias="TELEGRAM_TOKEN")
    bot_username: str = Field(default="", alias="BOT_USERNAME")
    webhook_url: str = Field(default="", alias="WEBHOOK_URL")

    # Google OAuth
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    oauth_redirect_uri: str = Field(
        default="http://localhost:8765/oauth/callback", alias="OAUTH_REDIRECT_URI"
    )

    # Encryption
    fernet_key: str = Field(alias="FERNET_KEY")

    # Midtrans
    midtrans_server_key: str = Field(default="", alias="MIDTRANS_SERVER_KEY")
    midtrans_client_key: str = Field(default="", alias="MIDTRANS_CLIENT_KEY")

    # Gemini AI
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Port (Railway/Layanan cloud akan set PORT via env)
    port: int = Field(default=8765, alias="PORT")
    # Dev / local config
    dev_host: str = Field(default="127.0.0.1", alias="DEV_HOST")

    # Bot config
    bot_language: str = Field(default="id")
    max_history_months_free: int = Field(default=3)
    premium_monthly_price_idr: int = Field(default=25000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Module-level singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
