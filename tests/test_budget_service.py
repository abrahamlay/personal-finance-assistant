"""Tests for BudgetService."""

import pytest
from unittest.mock import MagicMock

from src.sheets.budgets import SheetsBudgets
from src.sheets.transactions import SheetsTransactions
from src.services.budget_service import BudgetService
from src.auth.token_store import TokenStore


@pytest.fixture
def mock_sheets_budgets():
    return MagicMock(spec=SheetsBudgets)


@pytest.fixture
def mock_sheets_transactions():
    return MagicMock(spec=SheetsTransactions)


@pytest.fixture
def mock_token_store():
    return MagicMock(spec=TokenStore)


@pytest.fixture
def budget_service(mock_sheets_budgets, mock_sheets_transactions, mock_token_store):
    return BudgetService(mock_sheets_budgets, mock_sheets_transactions, mock_token_store)


class TestBudgetService:
    def test_set_budget_creates_budget(self, budget_service, mock_sheets_budgets, mock_token_store):
        mock_token_store.get_active_subscription.return_value = None
        mock_sheets_budgets.list_all.return_value = []
        mock_sheets_budgets.set.return_value = {"success": True, "id": "1"}

        result = budget_service.set_budget(
            "12345", "SPREADSHEET_ID", "Makanan", 500000, "bulanan", "2026-06"
        )

        assert result["success"] is True
        mock_sheets_budgets.set.assert_called_once_with(
            "12345", "SPREADSHEET_ID", "Makanan", 500000, "bulanan", "2026-06"
        )

    def test_set_budget_free_tier_one_budget(self, budget_service, mock_sheets_budgets, mock_token_store):
        mock_token_store.get_active_subscription.return_value = None
        mock_sheets_budgets.list_all.return_value = [
            {"id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 0}
        ]

        result = budget_service.set_budget(
            "12345", "SPREADSHEET_ID", "Transportasi", 300000, "bulanan", "2026-06"
        )

        assert result["success"] is False
        assert result["error"] == "free_tier_limit"
        mock_sheets_budgets.set.assert_not_called()

    def test_set_budget_premium_unlimited(self, budget_service, mock_sheets_budgets, mock_token_store):
        mock_token_store.get_active_subscription.return_value = {"status": "active"}
        mock_sheets_budgets.list_all.return_value = [
            {"id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 0},
            {"id": "2", "kategori": "Transportasi", "jumlah_bulan": 300000, "bulan": "2026-06", "terpakai": 0},
        ]
        mock_sheets_budgets.set.return_value = {"success": True, "id": "3"}

        result = budget_service.set_budget(
            "12345", "SPREADSHEET_ID", "Belanja", 200000, "bulanan", "2026-06"
        )

        assert result["success"] is True
        mock_sheets_budgets.set.assert_called_once()

    def test_get_usage_percentage(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.get.return_value = {
            "id": "1",
            "kategori": "Makanan",
            "jumlah_bulan": 500000,
            "bulan": "2026-06",
            "terpakai": 400000,
        }

        usage = budget_service.get_usage("12345", "SPREADSHEET_ID", "Makanan", "2026-06")

        assert usage["found"] is True
        assert usage["percentage"] == 80.0

    def test_warning_at_50_percent(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.get.return_value = {
            "id": "1", "kategori": "Makanan", "jumlah_bulan": 1000000, "bulan": "2026-06", "terpakai": 500000
        }

        warning = budget_service.check_budget_warnings(
            "12345", "SPREADSHEET_ID", "Makanan", "2026-06"
        )

        assert "💡" in warning
        assert "50%" in warning

    def test_warning_at_80_percent(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.get.return_value = {
            "id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 400000
        }

        warning = budget_service.check_budget_warnings(
            "12345", "SPREADSHEET_ID", "Makanan", "2026-06"
        )

        assert "⚠️" in warning
        assert "80%" in warning

    def test_warning_at_90_percent(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.get.return_value = {
            "id": "1", "kategori": "Makanan", "jumlah_bulan": 1000000, "bulan": "2026-06", "terpakai": 900000
        }

        warning = budget_service.check_budget_warnings(
            "12345", "SPREADSHEET_ID", "Makanan", "2026-06"
        )

        assert "🔴" in warning
        assert "90%" in warning

    def test_warning_at_100_percent(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.get.return_value = {
            "id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 500000
        }

        warning = budget_service.check_budget_warnings(
            "12345", "SPREADSHEET_ID", "Makanan", "2026-06"
        )

        assert "🚨" in warning
        assert "100%" in warning

    def test_track_transaction_updates_and_warns(self, budget_service, mock_sheets_budgets):
        mock_sheets_budgets.add_usage.return_value = {"found": True, "terpakai": 500000}
        mock_sheets_budgets.get.return_value = {
            "id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 500000
        }

        warning = budget_service.track_transaction(
            "12345", "SPREADSHEET_ID", "Makanan", 100000, "2026-06"
        )

        mock_sheets_budgets.add_usage.assert_called_once_with(
            "12345", "SPREADSHEET_ID", "Makanan", 100000, "2026-06"
        )
        assert "🚨" in warning

    def test_budget_resets_monthly(self, budget_service, mock_sheets_budgets):
        def _get(tid, ss, cat, month):
            budgets = {
                "2026-05": {"id": "1", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-05", "terpakai": 500000},
                "2026-06": {"id": "2", "kategori": "Makanan", "jumlah_bulan": 500000, "bulan": "2026-06", "terpakai": 0},
            }
            return budgets.get(month)

        mock_sheets_budgets.get.side_effect = _get

        usage_may = budget_service.get_usage("12345", "SPREADSHEET_ID", "Makanan", "2026-05")
        usage_june = budget_service.get_usage("12345", "SPREADSHEET_ID", "Makanan", "2026-06")

        assert usage_may["terpakai"] == 500000
        assert usage_june["terpakai"] == 0
