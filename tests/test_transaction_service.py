"""Tests for TransactionService."""

import pytest
from unittest.mock import MagicMock, patch

from src.sheets.transactions import SheetsTransactions
from src.cache.memory_cache import MemoryCache
from src.services.transaction_service import TransactionService


@pytest.fixture
def mock_sheets_transactions():
    return MagicMock(spec=SheetsTransactions)


@pytest.fixture
def cache():
    return MemoryCache()


@pytest.fixture
def tx_service(mock_sheets_transactions, cache):
    return TransactionService(mock_sheets_transactions, cache)


class TestTransactionService:
    def test_create_appends_transaction(self, tx_service, mock_sheets_transactions, cache):
        mock_sheets_transactions.append.return_value = 5
        mock_sheets_transactions.get_today.return_value = []

        result = tx_service.create(
            "12345", "SPREADSHEET_ID", "expense", "Makanan", 50000, "nasi padang", "2026-06-21"
        )

        assert result["row_id"] == 5
        assert result["was_duplicate"] is False
        mock_sheets_transactions.append.assert_called_once_with(
            "12345", "SPREADSHEET_ID", "expense", "Makanan", 50000, "nasi padang", "2026-06-21"
        )

    def test_dedup_blocks_duplicate_within_5min(self, tx_service, mock_sheets_transactions):
        mock_sheets_transactions.append.return_value = 1
        mock_sheets_transactions.get_today.return_value = []

        tx_service.create(
            "12345", "SPREADSHEET_ID", "expense", "Makanan", 50000, "nasi padang", "2026-06-21"
        )
        result = tx_service.create(
            "12345", "SPREADSHEET_ID", "expense", "Makanan", 50000, "nasi padang", "2026-06-21"
        )

        assert result["was_duplicate"] is True
        assert result["row_id"] is None
        assert mock_sheets_transactions.append.call_count == 1

    def test_get_today_aggregates(self, tx_service, mock_sheets_transactions):
        mock_sheets_transactions.get_today.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 50000, "kategori": "Makanan"},
            {"id": "2", "tipe": "expense", "jumlah": 20000, "kategori": "Transportasi"},
            {"id": "3", "tipe": "income", "jumlah": 1000000, "kategori": "Gaji"},
        ]

        total = tx_service._get_today_total("12345", "SPREADSHEET_ID")

        assert total["expense"] == 70000
        assert total["income"] == 1000000
        assert total["count"] == 3

    def test_update_propagates_to_sheets(self, tx_service, mock_sheets_transactions):
        mock_sheets_transactions.update.return_value = True

        result = tx_service.update("12345", "SPREADSHEET_ID", 5, kategori="Transportasi")

        assert result is True
        mock_sheets_transactions.update.assert_called_once_with(
            "12345", "SPREADSHEET_ID", 5, kategori="Transportasi"
        )

    def test_delete_marks_as_deleted(self, tx_service, mock_sheets_transactions):
        mock_sheets_transactions.delete.return_value = True

        result = tx_service.delete("12345", "SPREADSHEET_ID", 5)

        assert result is True
        mock_sheets_transactions.delete.assert_called_once_with("12345", "SPREADSHEET_ID", 5)
