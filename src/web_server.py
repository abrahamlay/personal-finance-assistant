"""aiohttp web server for OAuth callback, Telegram webhook, and payment webhooks."""
import json
import logging
from urllib.parse import urlencode
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

@routes.get("/oauth/authorize")
async def oauth_authorize(request: web.Request) -> web.Response:
    """Generate Google OAuth URL for the WebApp login page."""
    oauth_manager = request.app["oauth_manager"]
    start_param = request.query.get("start_param")
    auth_url, state = oauth_manager.get_authorization_url()
    return web.json_response({"url": auth_url, "state": state})

@routes.get("/oauth/callback")
async def oauth_callback(request: web.Request) -> web.Response:
    """Handle Google OAuth redirect. Exchange code, store tokens."""
    oauth_manager = request.app["oauth_manager"]
    code = request.query.get("code")
    state = request.query.get("state")
    
    if not code:
        return web.Response(text="Missing authorization code", status=400)
    
    try:
        token_data = oauth_manager.exchange_code(code, state)
        # Store temporarily keyed by state; bot will link to telegram_id
        request.app["pending_tokens"][state] = token_data
    except Exception as e:
        logger.error("OAuth callback error (state=%s): %s", state, e, exc_info=True)
        return web.Response(text=f"OAuth error: {str(e)}", status=500)

    # Redirect back to the WebApp login page with code+state params.
    # login.html (the WebApp origin) will detect these params and call
    # Telegram.WebApp.sendData() from the correct origin — ensuring the
    # Telegram WebApp bridge accepts the call.
    redirect_url = f"/login?{urlencode({'code': code, 'state': state})}"
    raise web.HTTPFound(redirect_url)

@routes.post("/payments/midtrans/webhook")
async def midtrans_webhook(request: web.Request) -> web.Response:
    """Midtrans payment notification webhook."""
    return await midtrans_webhook_handler(request)

@routes.get("/health")
async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "personal-finance-bot"})

def create_app(oauth_manager, token_store, subscription_service=None, midtrans_payment=None, pending_tokens=None) -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()
    app["oauth_manager"] = oauth_manager
    app["token_store"] = token_store
    app["subscription_service"] = subscription_service
    app["midtrans_payment"] = midtrans_payment
    app["pending_tokens"] = pending_tokens or {}
    app.add_routes(routes)
    return app
