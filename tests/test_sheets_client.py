"""Tests for the Google Sheets per-user OAuth client."""

import pytest
from unittest.mock import MagicMock, call, patch

import gspread

from src.auth.oauth import OAuthManager
from src.auth.token_store import TokenStore
from src.sheets.client import (
    SheetsClient,
    SheetNotFoundError,
    SheetAuthError,
    retry_with_backoff,
)


@pytest.fixture
def mock_oauth_manager():
    return MagicMock(spec=OAuthManager)


@pytest.fixture
def mock_token_store():
    return MagicMock(spec=TokenStore)


@pytest.fixture
def sheets_client(mock_oauth_manager, mock_token_store):
    return SheetsClient(mock_oauth_manager, mock_token_store)


@pytest.fixture(autouse=True)
def patch_sleep():
    """Patch time.sleep in the client module so retries don't slow tests."""
    with patch("src.sheets.client.time.sleep") as mock_sleep:
        yield mock_sleep


class TestSheetsClient:
    def test_authenticate_creates_client_with_valid_credentials(
        self, sheets_client, mock_oauth_manager
    ):
        creds = MagicMock()
        mock_oauth_manager.get_valid_credentials.return_value = creds
        mock_client = MagicMock()

        with patch(
            "src.sheets.client.gspread.authorize", return_value=mock_client
        ) as mock_authorize:
            result = sheets_client.authenticate("12345")

            assert result is mock_client
            mock_authorize.assert_called_once_with(creds)

    def test_authenticate_raises_auth_error_when_no_credentials(
        self, sheets_client, mock_oauth_manager
    ):
        mock_oauth_manager.get_valid_credentials.return_value = None

        with pytest.raises(SheetAuthError):
            sheets_client.authenticate("12345")

    def test_authenticate_caches_client(self, sheets_client, mock_oauth_manager):
        creds = MagicMock()
        mock_oauth_manager.get_valid_credentials.return_value = creds
        mock_client = MagicMock()

        with patch(
            "src.sheets.client.gspread.authorize", return_value=mock_client
        ) as mock_authorize:
            client1 = sheets_client.authenticate("12345")
            client2 = sheets_client.authenticate("12345")

            assert client1 is client2
            mock_authorize.assert_called_once()

    def test_read_range_returns_cell_values(self, sheets_client):
        mock_client = MagicMock()
        mock_sheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get.return_value = [["a", "b"], ["c", "d"]]
        mock_sheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_key.return_value = mock_sheet
        sheets_client._clients["12345"] = mock_client

        result = sheets_client.read_range(
            "12345", "spreadsheet_id", "transaksi!A2:G"
        )

        assert result == [["a", "b"], ["c", "d"]]
        mock_client.open_by_key.assert_called_once_with("spreadsheet_id")
        mock_sheet.worksheet.assert_called_once_with("transaksi")
        mock_worksheet.get.assert_called_once_with("A2:G")

    def test_read_range_raises_sheet_not_found(self, sheets_client):
        mock_client = MagicMock()
        mock_client.open_by_key.side_effect = (
            gspread.exceptions.SpreadsheetNotFound
        )
        sheets_client._clients["12345"] = mock_client

        with pytest.raises(SheetNotFoundError):
            sheets_client.read_range(
                "12345", "spreadsheet_id", "transaksi!A2:G"
            )

    def test_read_all_rows_skips_header(self, sheets_client):
        mock_client = MagicMock()
        mock_sheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = [
            ["header1", "header2"],
            ["row1a", "row1b"],
            ["row2a", "row2b"],
        ]
        mock_sheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_key.return_value = mock_sheet
        sheets_client._clients["12345"] = mock_client

        result = sheets_client.read_all_rows(
            "12345", "spreadsheet_id", "transaksi"
        )

        assert result == [["row1a", "row1b"], ["row2a", "row2b"]]

    def test_append_row_adds_data_and_returns_row_count(self, sheets_client):
        mock_client = MagicMock()
        mock_sheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.row_count = 42
        mock_sheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_key.return_value = mock_sheet
        sheets_client._clients["12345"] = mock_client

        result = sheets_client.append_row(
            "12345", "spreadsheet_id", "transaksi", ["data1", "data2"]
        )

        assert result == 42
        mock_worksheet.append_row.assert_called_once_with(
            ["data1", "data2"], value_input_option="USER_ENTERED"
        )

    def test_update_cell_calls_api(self, sheets_client):
        mock_client = MagicMock()
        mock_sheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_sheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_key.return_value = mock_sheet
        sheets_client._clients["12345"] = mock_client

        sheets_client.update_cell(
            "12345", "spreadsheet_id", "transaksi", 5, 3, "value"
        )

        mock_worksheet.update_cell.assert_called_once_with(5, 3, "value")

    def test_clear_client_cache_removes_cached(self, sheets_client, mock_oauth_manager):
        creds = MagicMock()
        mock_oauth_manager.get_valid_credentials.return_value = creds
        mock_client = MagicMock()

        with patch(
            "src.sheets.client.gspread.authorize", return_value=mock_client
        ) as mock_authorize:
            sheets_client.authenticate("12345")
            sheets_client.clear_client_cache("12345")
            sheets_client.authenticate("12345")

            assert mock_authorize.call_count == 2

    def test_batch_update_executes_requests(self, sheets_client, mock_oauth_manager):
        creds = MagicMock()
        mock_oauth_manager.get_valid_credentials.return_value = creds
        mock_client = MagicMock()
        sheets_client._clients["12345"] = mock_client

        mock_service = MagicMock()
        mock_spreadsheets = MagicMock()
        mock_batch_update_call = MagicMock()
        mock_execute = MagicMock()

        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.batchUpdate.return_value = mock_batch_update_call
        mock_batch_update_call.execute = mock_execute

        with patch("googleapiclient.discovery.build", return_value=mock_service) as mock_build:
            sheets_client.batch_update(
                "12345", "spreadsheet_id", [{"request": 1}]
            )

            mock_build.assert_called_once_with("sheets", "v4", credentials=creds)
            mock_spreadsheets.batchUpdate.assert_called_once_with(
                spreadsheetId="spreadsheet_id",
                body={"requests": [{"request": 1}]},
            )
            mock_execute.assert_called_once()


class TestRetryWithBackoff:
    def test_retry_on_429_error(self, patch_sleep):
        class FakeAPIError(gspread.exceptions.APIError):
            def __init__(self, code):
                self.code = code

        call_count = 0

        @retry_with_backoff(max_retries=3)
        def target():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise FakeAPIError(429)
            return "success"

        result = target()

        assert result == "success"
        assert call_count == 3
        patch_sleep.assert_has_calls([call(1.0), call(2.0)])

    def test_retry_gives_up_after_max_retries(self, patch_sleep):
        class FakeAPIError(gspread.exceptions.APIError):
            def __init__(self, code):
                self.code = code

        call_count = 0

        @retry_with_backoff(max_retries=2)
        def target():
            nonlocal call_count
            call_count += 1
            raise FakeAPIError(503)

        with pytest.raises(gspread.exceptions.APIError):
            target()

        assert call_count == 3
        patch_sleep.assert_has_calls([call(1.0), call(2.0)])
