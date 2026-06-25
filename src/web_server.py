"""aiohttp web server for OAuth callback, Telegram webhook, and payment webhooks."""
import json
import logging
from aiohttp import web

from src.config import get_settings
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
        
        # Return success page that calls Telegram.WebApp.sendData()
        bot_user = get_settings().bot_username
        deep_link = f"https://t.me/{bot_user}?start=login_{state}" if bot_user and state else ""
        success_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login Berhasil</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0fdf4}}
.card{{text-align:center;padding:24px;max-width:380px}}
h2{{color:#059669}}
.fallback{{display:none;margin-top:16px;padding:16px;background:#fef3c7;border-radius:10px;font-size:13px;color:#92400e;text-align:center}}
.btn-telegram{{display:inline-block;margin-top:12px;padding:12px 24px;background:#059669;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px}}
code{{display:block;margin-top:8px;padding:8px;background:#fffbeb;border:1px dashed #f59e0b;border-radius:6px;word-break:break-all;font-size:12px}}
</style>
</head><body>
<div class="card"><h2>✅ Login Berhasil!</h2>
<p id="autoMsg">Jendela akan menutup otomatis...</p>
<div id="fallback" class="fallback">
<p style="margin:0 0 4px"><strong>Klik tombol di bawah</strong> untuk kembali ke Telegram:</p>
<a class="btn-telegram" href="{deep_link}" target="_blank">↗️ Buka Telegram</a>
<p style="margin:12px 0 4px;font-size:12px">Atau kirim kode ini manual:</p>
<code>/verify {code} {state or ''}</code>
</div></div>
<script>
try {{
    Telegram.WebApp.sendData(JSON.stringify({{code: "{code}", state: "{state or ''}"}}));
    setTimeout(() => {{ Telegram.WebApp.close(); }}, 1500);
}} catch(e) {{
    document.getElementById('autoMsg').style.display = 'none';
    document.getElementById('fallback').style.display = 'block';
}}
</script></body></html>"""
        return web.Response(text=success_html, content_type="text/html")
    except Exception as e:
        logger.error("OAuth callback error (state=%s): %s", state, e, exc_info=True)
        return web.Response(text=f"OAuth error: {str(e)}", status=500)

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
