"""Tests for SheetsTransactions."""

import pytest
from unittest.mock import MagicMock, patch

from src.sheets.client import SheetsClient
from src.sheets.transactions import SheetsTransactions


@pytest.fixture
def mock_sheets_client():
    return MagicMock(spec=SheetsClient)


@pytest.fixture
def sheets_transactions(mock_sheets_client):
    return SheetsTransactions(mock_sheets_client)


class TestSheetsTransactions:
    def test_append_returns_row_id(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = []
        mock_sheets_client.append_row.return_value = 2

        row_id = sheets_transactions.append(
            "12345", "SPREADSHEET_ID", "expense", "Makanan", 50000, "nasi padang", "2026-06-21"
        )

        assert row_id == 2
        mock_sheets_client.append_row.assert_called_once()
        call_args = mock_sheets_client.append_row.call_args[0]
        assert call_args[0] == "12345"
        assert call_args[1] == "SPREADSHEET_ID"
        assert call_args[2] == "transaksi"
        assert call_args[3][:6] == ["1", "2026-06-21", "expense", "Makanan", "50000", "nasi padang"]
        assert len(call_args[3]) == 7

    def test_get_all_returns_list_of_dicts(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "2026-06-21", "expense", "Makanan", "50000", "nasi padang", "2026-06-21T10:00:00"],
            ["2", "2026-06-21", "income", "Gaji", "1000000", "gaji bulanan", "2026-06-21T11:00:00"],
        ]

        result = sheets_transactions.get_all("12345", "SPREADSHEET_ID")

        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[0]["kategori"] == "Makanan"
        assert result[0]["jumlah"] == 50000
        assert result[1]["tipe"] == "income"
        assert result[1]["jumlah"] == 1000000

    def test_get_today_filters_by_date(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "2026-06-21", "expense", "Makanan", "50000", "nasi padang", "2026-06-21T10:00:00"],
            ["2", "2026-06-20", "expense", "Transportasi", "20000", "bensin", "2026-06-20T10:00:00"],
        ]

        with patch("src.sheets.transactions.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2026-06-21"
            result = sheets_transactions.get_today("12345", "SPREADSHEET_ID")

        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_update_modifies_row(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "2026-06-21", "expense", "Makanan", "50000", "nasi padang", "2026-06-21T10:00:00"],
        ]

        success = sheets_transactions.update(
            "12345", "SPREADSHEET_ID", 1, kategori="Transportasi", jumlah="75000"
        )

        assert success is True
        assert mock_sheets_client.update_cell.call_count == 2
        mock_sheets_client.update_cell.assert_any_call(
            "12345", "SPREADSHEET_ID", "transaksi", 2, 4, "Transportasi"
        )
        mock_sheets_client.update_cell.assert_any_call(
            "12345", "SPREADSHEET_ID", "transaksi", 2, 5, "75000"
        )

    def test_delete_clears_row(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "2026-06-21", "expense", "Makanan", "50000", "nasi padang", "2026-06-21T10:00:00"],
        ]

        success = sheets_transactions.delete("12345", "SPREADSHEET_ID", 1)

        assert success is True
        mock_sheets_client.update_cell.assert_any_call(
            "12345", "SPREADSHEET_ID", "transaksi", 2, 4, "[dihapus]"
        )
        mock_sheets_client.update_cell.assert_any_call(
            "12345", "SPREADSHEET_ID", "transaksi", 2, 5, "0"
        )
        mock_sheets_client.update_cell.assert_any_call(
            "12345", "SPREADSHEET_ID", "transaksi", 2, 6, "[dihapus]"
        )

    def test_next_id_returns_1_for_empty(self, sheets_transactions, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = []
        assert sheets_transactions._next_id("12345", "SPREADSHEET_ID") == 1
