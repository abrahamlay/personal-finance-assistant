"""Tests for SheetSetupService."""

import pytest
from unittest.mock import MagicMock, patch

import gspread

from src.sheets.client import SheetsClient
from src.auth.token_store import TokenStore
from src.sheets.setup import SheetSetupService, DEFAULT_CATEGORIES, TAB_HEADERS


@pytest.fixture
def mock_sheets_client():
    return MagicMock(spec=SheetsClient)


@pytest.fixture
def mock_token_store():
    return MagicMock(spec=TokenStore)


@pytest.fixture
def setup_service(mock_sheets_client, mock_token_store):
    return SheetSetupService(mock_sheets_client, mock_token_store)


@pytest.fixture
def mock_gspread_client():
    return MagicMock()


class TestSheetSetupService:
    def test_setup_new_user_creates_spreadsheet_and_stores_id(
        self, setup_service, mock_sheets_client, mock_token_store, mock_gspread_client
    ):
        mock_token_store.get_user_token.return_value = None
        mock_sheets_client.authenticate.return_value = mock_gspread_client
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "SPREADSHEET_ID_123"
        mock_gspread_client.create.return_value = mock_spreadsheet

        result = setup_service.setup_new_user("12345", "Alice")

        assert result == "SPREADSHEET_ID_123"
        mock_gspread_client.create.assert_called_once_with("KeuanganBot - Alice")

    def test_setup_returns_existing_id_when_already_setup(
        self, setup_service, mock_sheets_client, mock_token_store
    ):
        mock_token_store.get_user_token.return_value = {
            "telegram_id": "12345",
            "spreadsheet_id": "EXISTING_ID",
        }

        result = setup_service.setup_new_user("12345", "Alice")

        assert result == "EXISTING_ID"
        mock_sheets_client.authenticate.assert_not_called()

    def test_create_spreadsheet_returns_non_empty_id(
        self, setup_service, mock_sheets_client, mock_gspread_client
    ):
        mock_sheets_client.authenticate.return_value = mock_gspread_client
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "NEW_SPREADSHEET_ID"
        mock_gspread_client.create.return_value = mock_spreadsheet

        result = setup_service._create_spreadsheet("12345", "Bob")

        assert result == "NEW_SPREADSHEET_ID"
        assert result != ""
        mock_gspread_client.create.assert_called_once_with("KeuanganBot - Bob")

    def test_create_tabs_creates_5_tabs(
        self, setup_service, mock_sheets_client, mock_gspread_client
    ):
        mock_sheets_client.authenticate.return_value = mock_gspread_client
        mock_sheet = MagicMock()
        mock_gspread_client.open_by_key.return_value = mock_sheet
        mock_sheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("missing")

        setup_service._create_tabs("12345", "SPREADSHEET_ID")

        assert mock_sheet.add_worksheet.call_count == 5
        expected_header_calls = [
            ("12345", "SPREADSHEET_ID", tab, headers)
            for tab, headers in TAB_HEADERS.items()
            if headers
        ]
        assert len(expected_header_calls) == 4
        for expected_call in expected_header_calls:
            mock_sheets_client.append_row.assert_any_call(*expected_call)

    def test_preload_categories_writes_13_rows(
        self, setup_service, mock_sheets_client
    ):
        setup_service._preload_categories("12345", "SPREADSHEET_ID")

        assert mock_sheets_client.append_row.call_count == len(DEFAULT_CATEGORIES)
        for idx, (nama, tipe, icon) in enumerate(DEFAULT_CATEGORIES, start=1):
            mock_sheets_client.append_row.assert_any_call(
                "12345", "SPREADSHEET_ID", "kategori", [str(idx), nama, tipe, "TRUE", icon]
            )

    def test_initialize_config_writes_key_value_pairs(
        self, setup_service, mock_sheets_client
    ):
        with patch("src.sheets.setup.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2026-06-21"
            setup_service._initialize_config("12345", "SPREADSHEET_ID", "Alice")

        expected_config = [
            ["telegram_id", "12345"],
            ["first_name", "Alice"],
            ["language", "id"],
            ["join_date", "2026-06-21"],
            ["premium_status", "free"],
        ]
        for key, value in expected_config:
            mock_sheets_client.append_row.assert_any_call(
                "12345", "SPREADSHEET_ID", "config", [key, value]
            )

    def test_setup_stores_spreadsheet_id_in_token_store(
        self, setup_service, mock_sheets_client, mock_token_store, mock_gspread_client
    ):
        mock_token_store.get_user_token.return_value = None
        mock_sheets_client.authenticate.return_value = mock_gspread_client
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "STORED_ID"
        mock_gspread_client.create.return_value = mock_spreadsheet

        setup_service.setup_new_user("12345", "Alice")

        mock_token_store.update_user_token.assert_called_with(
            "12345", spreadsheet_id="STORED_ID"
        )

    def test_setup_builds_dashboard_when_generator_provided(
        self, setup_service, mock_sheets_client, mock_token_store, mock_gspread_client
    ):
        mock_dashboard_generator = MagicMock()
        setup_service.dashboard_generator = mock_dashboard_generator
        mock_token_store.get_user_token.return_value = None
        mock_sheets_client.authenticate.return_value = mock_gspread_client
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "SHEET_WITH_DASHBOARD"
        mock_gspread_client.create.return_value = mock_spreadsheet

        setup_service.setup_new_user("12345", "Alice")

        mock_dashboard_generator.build.assert_called_once_with(
            "12345", "SHEET_WITH_DASHBOARD", is_premium=False
        )
