"""Midtrans payment integration for QRIS, e-wallet, bank transfer."""
import hashlib
import json
import time

from aiohttp import web
from midtransclient import Snap


class MidtransPayment:
    def __init__(self, server_key: str, client_key: str):
        self.snap = Snap(
            is_production=False,
            server_key=server_key,
            client_key=client_key,
        )

    def create_charge(self, order_id: str, amount: int, plan: str, user_id: str) -> dict:
        """Create Midtrans payment charge. Returns payment URL/token."""
        param = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": amount,
            },
            "item_details": [{
                "id": plan,
                "price": amount,
                "quantity": 1,
                "name": f"Premium {plan.capitalize()}",
            }],
            "customer_details": {"user_id": user_id},
            "custom_field1": user_id,
            "custom_field2": plan,
        }
        return self.snap.create_transaction(param)

    @staticmethod
    def verify_signature(order_id: str, status_code: str, gross_amount: str, server_key: str, raw_signature: str) -> bool:
        """Verify Midtrans webhook SHA512 signature."""
        data = order_id + status_code + gross_amount + server_key
        computed = hashlib.sha512(data.encode()).hexdigest()
        return computed == raw_signature


async def midtrans_webhook_handler(request):
    """Handle Midtrans webhook POST (used in web_server.py)."""
    try:
        payload = await request.json()
    except Exception:
        return web.Response(text='{"status":"error","message":"invalid json"}', status=400, content_type="application/json")

    order_id = payload.get("order_id")
    status_code = str(payload.get("status_code", ""))
    gross_amount = str(payload.get("gross_amount", ""))
    signature_key = payload.get("signature_key")
    transaction_status = payload.get("transaction_status")
    user_id = payload.get("custom_field1")
    plan = payload.get("custom_field2")

    if not order_id or not signature_key:
        return web.Response(text='{"status":"error","message":"missing fields"}', status=400, content_type="application/json")

    midtrans_payment = request.app.get("midtrans_payment")
    token_store = request.app.get("token_store")
    subscription_service = request.app.get("subscription_service")

    if not midtrans_payment or not token_store or not subscription_service:
        return web.Response(text='{"status":"error","message":"service unavailable"}', status=503, content_type="application/json")

    server_key = midtrans_payment.snap.server_key
    if not MidtransPayment.verify_signature(order_id, status_code, gross_amount, server_key, signature_key):
        return web.Response(text='{"status":"error","message":"invalid signature"}', status=403, content_type="application/json")

    # Idempotency: ignore if already recorded as paid.
    invoices = token_store.get_invoices_by_user(user_id)
    already_paid = any(
        inv.get("payment_ref") == order_id and inv.get("status") == "paid"
        for inv in invoices
    )
    if already_paid:
        return web.Response(text='{"status":"ok","message":"already processed"}', content_type="application/json")

    if transaction_status in ("capture", "settlement"):
        # Ensure a pending subscription exists for the user/plan before activating.
        try:
            subscription_service.create_subscription(user_id, plan)
        except Exception:
            # Subscription may already exist; ignore.
            pass
        subscription_service.activate_subscription(user_id, f"midtrans_{order_id}")

    return web.Response(text='{"status":"ok"}', content_type="application/json")
