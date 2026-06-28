"""aiohttp web server for OAuth callback, Telegram webhook, and payment webhooks."""
import json
import logging
import secrets
import hmac
import hashlib
from urllib.parse import urlencode, parse_qsl
from aiohttp import web

from src.payments.midtrans import midtrans_webhook_handler

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

@routes.get("/login")
async def login_page(request: web.Request) -> web.Response:
    """Serve the Telegram WebApp login page."""
    try:
        with open("static/login.html", "r", encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Login page not found", status=404)

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram WebApp initData and return user dict if valid."""
    try:
        vals = dict(parse_qsl(init_data))
        if "hash" not in vals:
            return None
        received_hash = vals.pop("hash")
        
        # Sort and join
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
        
        # HMAC-SHA256 signature
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash == received_hash:
            import json
            return json.loads(vals.get("user", "{}"))
    except Exception as e:
        logger.error("Error validating telegram initData: %s", e)
    return None

@routes.get("/oauth/authorize")
async def oauth_authorize(request: web.Request) -> web.Response:
    """Generate Google OAuth URL. Uses the session token or Telegram initData to identify the user."""
    oauth_manager = request.app["oauth_manager"]
    login_tokens = request.app["login_tokens"]
    
    telegram_id = None
    token = request.query.get("token")
    init_data = request.query.get("initData")
    
    if token and token in login_tokens:
        telegram_id = login_tokens.get(token)
    elif init_data:
        from src.config import get_settings
        bot_token = get_settings().telegram_token
        user_info = validate_telegram_init_data(init_data, bot_token)
        if user_info and "id" in user_info:
            telegram_id = str(user_info["id"])
        
    if not telegram_id:
        return web.Response(text="Invalid or expired login session. Please request /login in the bot.", status=400)
        
    # Embed the telegram_id in the state, separated by double colons
    random_str = secrets.token_urlsafe(16)
    state = f"{telegram_id}::{random_str}"
    
    auth_url, _ = oauth_manager.get_authorization_url(state=state)
    raise web.HTTPFound(auth_url)

@routes.get("/oauth/callback")
async def oauth_callback(request: web.Request) -> web.Response:
    """Handle Google OAuth redirect. Exchange code, store tokens, and redirect to Telegram."""
    oauth_manager = request.app["oauth_manager"]
    code = request.query.get("code")
    state = request.query.get("state")
    
    if not code or not state:
        return web.Response(text="Missing code or state parameter", status=400)
        
    if "::" not in state:
        return web.Response(text="Invalid state parameter", status=400)
        
    telegram_id, _ = state.split("::", 1)
    
    try:
        token_data = oauth_manager.exchange_code(code, state)
        oauth_manager.store_credentials(telegram_id, token_data)
    except Exception as e:
        logger.error("OAuth callback error for user %s: %s", telegram_id, e, exc_info=True)
        return web.Response(text=f"OAuth error: {str(e)}", status=500)

    # Redirect user back to Telegram using deep link to notify onboarding/start_onboarding handler
    bot_app = request.app.get("_bot_app")
    bot_username = bot_app.bot.username if (bot_app and bot_app.bot.username) else "BamFinanceBot"
    redirect_url = f"https://t.me/{bot_username}?start=oauth_done"
    raise web.HTTPFound(redirect_url)

@routes.post("/payments/midtrans/webhook")
async def midtrans_webhook(request: web.Request) -> web.Response:
    """Midtrans payment notification webhook."""
    return await midtrans_webhook_handler(request)

@routes.get("/health")
async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "personal-finance-bot"})

def create_app(oauth_manager, token_store, subscription_service=None, midtrans_payment=None, pending_tokens=None, login_tokens=None) -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()
    app["oauth_manager"] = oauth_manager
    app["token_store"] = token_store
    app["subscription_service"] = subscription_service
    app["midtrans_payment"] = midtrans_payment
    app["pending_tokens"] = pending_tokens if pending_tokens is not None else {}
    app["login_tokens"] = login_tokens if login_tokens is not None else {}
    app.add_routes(routes)
    return app
