"""Tests for OCR receipt scanner service (Gemini mocked)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.ocr_service import OCRService, OCRQuotaExceededError, OCRParseError


@pytest.fixture
def token_store():
    store = MagicMock()
    store.get_user_token.return_value = {"ocr_usage": "{}"}
    store.update_user_token = MagicMock()
    return store


@pytest.fixture
def ocr_service(token_store):
    return OCRService(api_key="fake-key", token_store=token_store)


@pytest.mark.asyncio
async def test_scan_parses_gemini_response(ocr_service, token_store):
    response = MagicMock()
    response.text = json.dumps({
        "merchant": "Indomaret",
        "total_amount": 50000,
        "items": [{"name": "Mineral", "qty": 1, "price": 5000}],
        "category_suggestion": "Belanja",
        "confidence": 0.95,
    })

    with patch.object(
        ocr_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=response,
    ):
        result = await ocr_service.scan("123", b"fake-photo-bytes")

    assert result["merchant"] == "Indomaret"
    assert result["total_amount"] == 50000
    assert result["category_suggestion"] == "Belanja"
    assert result["confidence"] == 0.95
    assert result["items"][0]["name"] == "Mineral"
    token_store.update_user_token.assert_called_once()


@pytest.mark.asyncio
async def test_scan_low_confidence_returns_lainnya(ocr_service, token_store):
    response = MagicMock()
    response.text = json.dumps({
        "merchant": "Unknown",
        "total_amount": 10000,
        "items": [],
        "category_suggestion": "Random",
        "confidence": 0.3,
    })

    with patch.object(
        ocr_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=response,
    ):
        result = await ocr_service.scan("123", b"fake")

    assert result["category_suggestion"] == "Lainnya"


@pytest.mark.asyncio
async def test_scan_respects_monthly_limit(ocr_service, token_store):
    month = "2026-06"
    token_store.get_user_token.return_value = {
        "ocr_usage": json.dumps({f"ocr:123:{month}": 30})
    }

    with pytest.raises(OCRQuotaExceededError):
        await ocr_service.scan("123", b"fake")


@pytest.mark.asyncio
async def test_scan_raises_on_invalid_json(ocr_service):
    response = MagicMock()
    response.text = "not valid json"

    with patch.object(
        ocr_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=response,
    ):
        with pytest.raises(OCRParseError):
            await ocr_service.scan("123", b"fake")


@pytest.mark.asyncio
async def test_scan_api_error_raises_parse_error(ocr_service):
    with patch.object(
        ocr_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API down"),
    ):
        with pytest.raises(OCRParseError):
            await ocr_service.scan("123", b"fake")
