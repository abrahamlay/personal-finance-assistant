"""Tests for AI insight service (Gemini mocked)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.insight_service import InsightService


@pytest.fixture
def insight_service():
    return InsightService(gemini_api_key="fake-key")


@pytest.mark.asyncio
async def test_analyze_returns_gemini_text(insight_service):
    transactions = [
        {"tipe": "expense", "jumlah": 100000, "kategori": "Makanan", "tanggal": "2026-06-01"},
        {"tipe": "expense", "jumlah": 50000, "kategori": "Transportasi", "tanggal": "2026-06-02"},
        {"tipe": "income", "jumlah": 5000000, "kategori": "Gaji", "tanggal": "2026-06-01"},
    ]

    response = MagicMock()
    response.text = "Kamu hemat bulan ini!"

    with patch.object(
        insight_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        return_value=response,
    ):
        result = await insight_service.analyze(transactions, [])

    assert "Insight Keuangan" in result
    assert "Kamu hemat bulan ini!" in result


@pytest.mark.asyncio
async def test_analyze_empty_transactions(insight_service):
    result = await insight_service.analyze([], [])
    assert "Belum ada transaksi" in result


@pytest.mark.asyncio
async def test_analyze_gemini_failure_uses_fallback(insight_service):
    transactions = [
        {"tipe": "expense", "jumlah": 100000, "kategori": "Makanan", "tanggal": "2026-06-01"},
    ]

    with patch.object(
        insight_service.client.aio.models,
        "generate_content",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API error"),
    ):
        result = await insight_service.analyze(transactions, [])

    assert "Insight Keuangan" in result
    assert "Makanan" in result


@pytest.mark.asyncio
async def test_analyze_no_api_key_uses_fallback():
    service = InsightService(gemini_api_key="")
    transactions = [
        {"tipe": "expense", "jumlah": 100000, "kategori": "Makanan", "tanggal": "2026-06-01"},
        {"tipe": "expense", "jumlah": 50000, "kategori": "Makanan", "tanggal": "2026-05-01"},
    ]

    result = await service.analyze(transactions, [])
    assert "Insight Keuangan" in result
    assert "Makanan" in result
    assert "bulan lalu" in result
