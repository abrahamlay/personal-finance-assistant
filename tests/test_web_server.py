import hashlib
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from src.web_server import create_app


@pytest.fixture
def mock_oauth_manager():
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_midtrans_payment():
    payment = MagicMock()
    payment.snap.server_key = "server_key_123"
    return payment


@pytest.fixture
async def client(mock_oauth_manager, mock_midtrans_payment):
    token_store = MagicMock()
    subscription_service = MagicMock()
    app = create_app(
        mock_oauth_manager,
        token_store,
        subscription_service=subscription_service,
        midtrans_payment=mock_midtrans_payment,
    )
    server = TestServer(app)
    test_client = TestClient(server)
    await test_client.start_server()
    yield test_client
    await test_client.close()


def _midtrans_payload(order_id, server_key):
    status_code = "200"
    gross_amount = "25000"
    signature = hashlib.sha512((order_id + status_code + gross_amount + server_key).encode()).hexdigest()
    return {
        "order_id": order_id,
        "status_code": status_code,
        "gross_amount": gross_amount,
        "signature_key": signature,
        "transaction_status": "settlement",
        "custom_field1": "user_1",
        "custom_field2": "monthly",
    }


async def test_login_route_returns_html(client):
    resp = await client.get("/login")
    assert resp.status == 200
    text = await resp.text()
    assert "Login dengan Google" in text
    # The page must persist Telegram init params across the OAuth redirect.
    assert "__tg_init_params__" in text


async def test_oauth_callback_missing_code_returns_400(client):
    resp = await client.get("/oauth/callback")
    assert resp.status == 400
    text = await resp.text()
    assert "Missing authorization code" in text


async def test_oauth_callback_success_stores_pending(client, mock_oauth_manager):
    mock_oauth_manager.exchange_code.return_value = {
        "access_token": "access_123",
        "refresh_token": "refresh_456",
        "expiry": 1234567890,
    }

    resp = await client.get("/oauth/callback?code=auth_code&state=state_abc")
    assert resp.status == 200
    text = await resp.text()
    assert "Login Berhasil" in text
    # The success page must restore Telegram WebApp context before calling sendData.
    assert "__tg_init_params__" in text
    assert "sendData" in text

    pending = client.app["pending_tokens"]
    assert "state_abc" in pending
    assert pending["state_abc"]["access_token"] == "access_123"


async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "personal-finance-bot"


async def test_midtrans_webhook_returns_ok(client, mock_midtrans_payment):
    payload = _midtrans_payload("order-123", mock_midtrans_payment.snap.server_key)
    resp = await client.post("/payments/midtrans/webhook", json=payload)
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
