"""Tests for DashboardGenerator using mocked Google Sheets API v4."""

import pytest
from unittest.mock import MagicMock, patch

from src.sheets.client import SheetsClient
from src.sheets.dashboard import DashboardGenerator


@pytest.fixture
def mock_sheets_client():
    client = MagicMock(spec=SheetsClient)
    client.oauth_manager = MagicMock()
    client.batch_update = MagicMock()
    return client


@pytest.fixture
def dashboard(mock_sheets_client):
    gen = DashboardGenerator(mock_sheets_client)
    # Avoid real Google API calls
    gen._get_sheet_id = lambda *args, **kwargs: 12345
    return gen


class TestDashboardGeneratorBuild:
    def test_build_calls_batch_update(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=False)

        mock_sheets_client.batch_update.assert_called_once()
        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        assert len(requests) > 0

    def test_build_free_includes_summary_formulas(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=False)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        formulas = [r for r in requests if "updateCells" in r]
        values = [
            r["updateCells"]["rows"][0]["values"][0].get("userEnteredValue", {})
            for r in formulas
        ]
        formula_strings = [v.get("formulaValue", "") for v in values]
        assert '=SUMIF(transaksi!C:C,"income",transaksi!E:E)' in formula_strings
        assert '=SUMIF(transaksi!C:C,"expense",transaksi!E:E)' in formula_strings

    def test_build_free_has_no_charts(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=False)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        charts = [r for r in requests if "addChart" in r]
        assert len(charts) == 0

    def test_build_premium_includes_pie_chart(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        charts = [r for r in requests if "addChart" in r]
        chart_specs = [c["addChart"]["chart"]["spec"] for c in charts]
        assert any("pieChart" in s for s in chart_specs)

    def test_build_premium_includes_bar_chart(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        charts = [r for r in requests if "addChart" in r]
        chart_specs = [c["addChart"]["chart"]["spec"] for c in charts]
        assert any("basicChart" in s for s in chart_specs)

    def test_build_premium_includes_sparklines(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        formulas = [r for r in requests if "updateCells" in r]
        values = [
            r["updateCells"]["rows"][0]["values"][0].get("userEnteredValue", {})
            for r in formulas
        ]
        formula_strings = [v.get("formulaValue", "") for v in values]
        assert any("SPARKLINE" in f for f in formula_strings)

    def test_build_premium_includes_query(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        formulas = [r for r in requests if "updateCells" in r]
        values = [
            r["updateCells"]["rows"][0]["values"][0].get("userEnteredValue", {})
            for r in formulas
        ]
        formula_strings = [v.get("formulaValue", "") for v in values]
        assert any("QUERY(transaksi!A:G" in f for f in formula_strings)

    def test_build_premium_has_conditional_formatting(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        rules = [r for r in requests if "addConditionalFormatRule" in r]
        assert len(rules) == 1

    def test_build_protects_formula_cells(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=False)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        protections = [r for r in requests if "addProtectedRange" in r]
        assert len(protections) >= 1
        for p in protections:
            assert p["addProtectedRange"]["protectedRange"]["warningOnly"] is True

    def test_build_premium_protects_more_ranges(self, dashboard, mock_sheets_client):
        dashboard.build("123", "SS_ID", is_premium=True)

        _, _, requests = mock_sheets_client.batch_update.call_args[0]
        protections = [r for r in requests if "addProtectedRange" in r]
        assert len(protections) > 1

    def test_build_returns_metadata(self, dashboard, mock_sheets_client):
        result = dashboard.build("123", "SS_ID", is_premium=False)

        assert result["sheet_id"] == 12345
        assert result["requests_count"] > 0


class TestDashboardGeneratorRegenerate:
    def test_regenerate_clears_then_builds(self, dashboard, mock_sheets_client):
        dashboard.regenerate("123", "SS_ID", is_premium=False)

        assert mock_sheets_client.batch_update.call_count == 2
        first_call = mock_sheets_client.batch_update.call_args_list[0]
        _, _, first_requests = first_call[0]
        assert first_requests[0]["updateCells"]["fields"] == "userEnteredValue,userEnteredFormat"

    def test_regenerate_returns_metadata(self, dashboard, mock_sheets_client):
        result = dashboard.regenerate("123", "SS_ID", is_premium=True)

        assert result["sheet_id"] == 12345
        assert result["requests_count"] > 0


class TestDashboardGeneratorUrl:
    def test_get_dashboard_url_uses_sheet_id(self, dashboard):
        url = dashboard.get_dashboard_url("123", "SS_ID")
        assert url == "https://docs.google.com/spreadsheets/d/SS_ID/edit#gid=12345"


class TestDashboardGeneratorA1Conversion:
    def test_a1_to_grid_range_single_column(self, dashboard):
        grid = dashboard._a1_to_grid_range(123, "B5")
        assert grid == {
            "sheetId": 123,
            "startRowIndex": 4,
            "endRowIndex": 5,
            "startColumnIndex": 1,
            "endColumnIndex": 2,
        }

    def test_a1_to_grid_range_double_letters(self, dashboard):
        grid = dashboard._a1_to_grid_range(1, "AA1")
        assert grid["startColumnIndex"] == 26
        assert grid["endColumnIndex"] == 27

    def test_a1_to_grid_range_rejects_invalid(self, dashboard):
        with pytest.raises(ValueError):
            dashboard._a1_to_grid_range(1, "INVALID")


class TestDashboardGeneratorSheetId:
    def test_get_sheet_id_queries_api(self, mock_sheets_client):
        mock_service = MagicMock()
        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "sheets": [
                {"properties": {"sheetId": 999, "title": "Dashboard"}},
            ]
        }
        mock_credentials = MagicMock()
        mock_credentials.universe_domain = "googleapis.com"
        mock_sheets_client.oauth_manager.get_valid_credentials.return_value = mock_credentials

        with patch("src.sheets.dashboard.build", return_value=mock_service):
            dashboard = DashboardGenerator(mock_sheets_client)
            sheet_id = dashboard._get_sheet_id("123", "SS_ID", "Dashboard")

        assert sheet_id == 999
        mock_service.spreadsheets.return_value.get.assert_called_once_with(spreadsheetId="SS_ID")
