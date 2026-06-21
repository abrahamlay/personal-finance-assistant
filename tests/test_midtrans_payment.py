"""Test Midtrans payment integration and webhook handler."""
import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from src.payments.midtrans import MidtransPayment, midtrans_webhook_handler
from src.services.subscription_service import SubscriptionService


@pytest.fixture
def mock_snap():
    snap = MagicMock()
    snap.server_key = "server_key_123"
    snap.create_transaction.return_value = {
        "token": "token_abc",
        "redirect_url": "https://app.sandbox.midtrans.com/snap/v2/vtweb/token_abc",
    }
    return snap


@pytest.fixture
def midtrans_payment(mock_snap):
    with patch("src.payments.midtrans.Snap", return_value=mock_snap):
        payment = MidtransPayment("server_key_123", "client_key_123")
        payment.snap = mock_snap
        return payment


def test_create_charge(mock_snap, midtrans_payment):
    result = midtrans_payment.create_charge("order_123", 25000, "monthly", "user_1")

    assert result["redirect_url"].startswith("https://")
    call_args = mock_snap.create_transaction.call_args[0][0]
    assert call_args["transaction_details"]["order_id"] == "order_123"
    assert call_args["transaction_details"]["gross_amount"] == 25000
    assert call_args["custom_field1"] == "user_1"
    assert call_args["custom_field2"] == "monthly"


def test_verify_signature_valid():
    order_id = "order_123"
    status_code = "200"
    gross_amount = "25000"
    server_key = "server_key_123"
    expected = hashlib.sha512((order_id + status_code + gross_amount + server_key).encode()).hexdigest()

    assert MidtransPayment.verify_signature(order_id, status_code, gross_amount, server_key, expected) is True


def test_verify_signature_invalid():
    assert MidtransPayment.verify_signature("order", "200", "100", "key", "wrong") is False


@pytest.fixture
async def webhook_client(midtrans_payment):
    token_store = MagicMock()
    subscription_service = MagicMock(spec=SubscriptionService)
    app = MagicMock()
    app["midtrans_payment"] = midtrans_payment
    app["token_store"] = token_store
    app["subscription_service"] = subscription_service

    from aiohttp import web
    aio_app = web.Application()
    aio_app["midtrans_payment"] = midtrans_payment
    aio_app["token_store"] = token_store
    aio_app["subscription_service"] = subscription_service
    aio_app.router.add_post("/payments/midtrans/webhook", midtrans_webhook_handler)
    server = TestServer(aio_app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


def _make_payload(order_id, status, amount, server_key):
    status_code = "200"
    gross_amount = str(amount)
    signature = hashlib.sha512((order_id + status_code + gross_amount + server_key).encode()).hexdigest()
    return {
        "order_id": order_id,
        "status_code": status_code,
        "gross_amount": gross_amount,
        "signature_key": signature,
        "transaction_status": status,
        "custom_field1": "user_1",
        "custom_field2": "monthly",
    }


@pytest.mark.asyncio
async def test_webhook_activates_subscription(webhook_client, midtrans_payment):
    payload = _make_payload("order_123", "settlement", 25000, midtrans_payment.snap.server_key)
    resp = await webhook_client.post("/payments/midtrans/webhook", json=payload)

    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"

    subscription_service = webhook_client.app["subscription_service"]
    subscription_service.create_subscription.assert_called_once_with("user_1", "monthly")
    subscription_service.activate_subscription.assert_called_once_with("user_1", "midtrans_order_123")


@pytest.mark.asyncio
async def test_webhook_idempotent(webhook_client, midtrans_payment):
    token_store = webhook_client.app["token_store"]
    token_store.get_invoices_by_user.return_value = [
        {"payment_ref": "order_123", "status": "paid"}
    ]
    payload = _make_payload("order_123", "settlement", 25000, midtrans_payment.snap.server_key)

    resp = await webhook_client.post("/payments/midtrans/webhook", json=payload)

    assert resp.status == 200
    data = await resp.json()
    assert data["message"] == "already processed"
    webhook_client.app["subscription_service"].activate_subscription.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_invalid_signature(webhook_client, midtrans_payment):
    payload = _make_payload("order_123", "settlement", 25000, midtrans_payment.snap.server_key)
    payload["signature_key"] = "tampered"

    resp = await webhook_client.post("/payments/midtrans/webhook", json=payload)

    assert resp.status == 403


@pytest.mark.asyncio
async def test_webhook_missing_fields(webhook_client):
    resp = await webhook_client.post("/payments/midtrans/webhook", json={})

    assert resp.status == 400
