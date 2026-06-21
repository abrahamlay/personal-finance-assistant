"""Tests for SheetsCategories."""

import pytest
from unittest.mock import MagicMock

from src.sheets.client import SheetsClient
from src.sheets.categories import SheetsCategories, FREE_CUSTOM_CATEGORY_LIMIT
from src.auth.token_store import TokenStore


@pytest.fixture
def mock_sheets_client():
    return MagicMock(spec=SheetsClient)


@pytest.fixture
def mock_token_store():
    return MagicMock(spec=TokenStore)


@pytest.fixture
def sheets_categories(mock_sheets_client, mock_token_store):
    return SheetsCategories(mock_sheets_client, mock_token_store)


class TestSheetsCategories:
    def test_list_all_returns_default_and_custom_categories(
        self, sheets_categories, mock_sheets_client
    ):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
            ["2", "Transportasi", "expense", "TRUE", "🚗"],
            ["14", "Custom", "expense", "FALSE", "🎯"],
        ]

        result = sheets_categories.list_all("12345", "SPREADSHEET_ID")

        assert len(result) == 3
        assert result[0]["id"] == "1"
        assert result[0]["is_default"] is True
        assert result[0]["icon"] == "🍔"
        assert result[-1]["id"] == "14"
        assert result[-1]["is_default"] is False
        assert result[-1]["icon"] == "🎯"

    def test_add_appends_custom_category(self, sheets_categories, mock_sheets_client, mock_token_store):
        mock_token_store.get_active_subscription.return_value = None
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
        ]

        result = sheets_categories.add("12345", "SPREADSHEET_ID", "Hobi", "expense", "🎨")

        assert result["success"] is True
        assert result["id"] == 2
        mock_sheets_client.append_row.assert_called_once_with(
            "12345", "SPREADSHEET_ID", "kategori", ["2", "Hobi", "expense", "FALSE", "🎨"]
        )

    def test_add_blocks_free_tier_limit(self, sheets_categories, mock_sheets_client, mock_token_store):
        mock_token_store.get_active_subscription.return_value = None
        custom_rows = [
            [str(13 + i), f"Custom{i}", "expense", "FALSE", "📌"]
            for i in range(1, FREE_CUSTOM_CATEGORY_LIMIT + 1)
        ]
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
        ] + custom_rows

        result = sheets_categories.add("12345", "SPREADSHEET_ID", "Hobi", "expense", "🎨")

        assert result["success"] is False
        assert result["error"] == "free_tier_limit"
        mock_sheets_client.append_row.assert_not_called()

    def test_add_allows_premium_unlimited(self, sheets_categories, mock_sheets_client, mock_token_store):
        mock_token_store.get_active_subscription.return_value = {"status": "active"}
        custom_rows = [
            [str(13 + i), f"Custom{i}", "expense", "FALSE", "📌"]
            for i in range(1, FREE_CUSTOM_CATEGORY_LIMIT + 1)
        ]
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
        ] + custom_rows

        result = sheets_categories.add("12345", "SPREADSHEET_ID", "Hobi", "expense", "🎨")

        assert result["success"] is True
        assert result["id"] == 19

    def test_rename_updates_category_name(self, sheets_categories, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
            ["14", "Custom", "expense", "FALSE", "🎯"],
        ]

        success = sheets_categories.rename("12345", "SPREADSHEET_ID", "14", "Custom Baru")

        assert success is True
        mock_sheets_client.update_cell.assert_called_once_with(
            "12345", "SPREADSHEET_ID", "kategori", 3, 2, "Custom Baru"
        )

    def test_delete_default_blocked(self, sheets_categories, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
        ]

        result = sheets_categories.delete("12345", "SPREADSHEET_ID", "1")

        assert result["success"] is False
        assert result["error"] == "cannot_delete_default"
        mock_sheets_client.update_cell.assert_not_called()

    def test_delete_custom_succeeds(self, sheets_categories, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
            ["14", "Custom", "expense", "FALSE", "🎯"],
        ]

        result = sheets_categories.delete("12345", "SPREADSHEET_ID", "14")

        assert result["success"] is True
        assert mock_sheets_client.update_cell.call_count == 4

    def test_list_includes_icons(self, sheets_categories, mock_sheets_client):
        mock_sheets_client.read_all_rows.return_value = [
            ["1", "Makanan", "expense", "TRUE", "🍔"],
            ["8", "Gaji", "income", "TRUE", "💰"],
        ]

        result = sheets_categories.list_all("12345", "SPREADSHEET_ID")

        icons = {c["nama"]: c["icon"] for c in result}
        assert icons["Makanan"] == "🍔"
        assert icons["Gaji"] == "💰"
