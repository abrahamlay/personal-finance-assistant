"""aiohttp web server for OAuth callback, Telegram webhook, and payment webhooks."""
import json
from aiohttp import web

from src.payments.midtrans import midtrans_webhook_handler

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
        success_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login Berhasil</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
</head><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0fdf4">
<div style="text-align:center;padding:24px"><h2>✅ Login Berhasil!</h2>
<p>Jendela ini akan menutup otomatis...</p>
<p id="fallback" style="display:none;font-size:14px">Kalau tidak menutup, kembali ke Telegram dan ketik /login</p></div>
<script>
try {{
    const code = "{code}";
    Telegram.WebApp.sendData(JSON.stringify({{code: code, state: "{state or ''}"}}));
    setTimeout(() => {{ Telegram.WebApp.close(); }}, 1500);
}} catch(e) {{
    document.getElementById('fallback').style.display = 'block';
}}
</script></body></html>"""
        return web.Response(text=success_html, content_type="text/html")
    except Exception as e:
        return web.Response(text=f"OAuth error: {str(e)}", status=500)

@routes.post("/payments/midtrans/webhook")
async def midtrans_webhook(request: web.Request) -> web.Response:
    """Midtrans payment notification webhook."""
    return await midtrans_webhook_handler(request)

@routes.get("/health")
async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "personal-finance-bot"})

def create_app(oauth_manager, token_store, subscription_service=None, midtrans_payment=None) -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()
    app["oauth_manager"] = oauth_manager
    app["token_store"] = token_store
    app["subscription_service"] = subscription_service
    app["midtrans_payment"] = midtrans_payment
    app["pending_tokens"] = {}  # state → token_data mapping
    app.add_routes(routes)
    return app
