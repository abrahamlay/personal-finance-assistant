"""Tests for ReportService summaries and chart generation."""

import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.sheets.transactions import SheetsTransactions
from src.services.transaction_service import TransactionService
from src.cache.memory_cache import MemoryCache
from src.services.report_service import ReportService


@pytest.fixture
def mock_sheets_transactions():
    return MagicMock(spec=SheetsTransactions)


@pytest.fixture
def tx_service(mock_sheets_transactions):
    return TransactionService(mock_sheets_transactions, MemoryCache())


@pytest.fixture
def report_service(mock_sheets_transactions, tx_service):
    return ReportService(mock_sheets_transactions, tx_service)


class TestReportServiceDailySummary:
    def test_daily_summary_empty(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_today.return_value = []

        summary = report_service.get_daily_summary("123", "SS_ID")

        assert summary["income"] == 0
        assert summary["expense"] == 0
        assert summary["saldo"] == 0
        assert summary["count"] == 0

    def test_daily_summary_aggregates_income_expense(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_today.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 50000, "kategori": "Makanan", "tanggal": "2026-06-21", "deskripsi": "nasi", "created_at": "1"},
            {"id": "2", "tipe": "income", "jumlah": 1000000, "kategori": "Gaji", "tanggal": "2026-06-21", "deskripsi": "gaji", "created_at": "2"},
        ]

        summary = report_service.get_daily_summary("123", "SS_ID")

        assert summary["income"] == 1000000
        assert summary["expense"] == 50000
        assert summary["saldo"] == 950000
        assert summary["count"] == 2

    def test_daily_summary_category_breakdown(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_today.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 50000, "kategori": "Makanan", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "1"},
            {"id": "2", "tipe": "expense", "jumlah": 20000, "kategori": "Transportasi", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "2"},
            {"id": "3", "tipe": "expense", "jumlah": 30000, "kategori": "Makanan", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "3"},
        ]

        summary = report_service.get_daily_summary("123", "SS_ID")
        expense_breakdown = summary["category_breakdown"]["expense"]

        assert expense_breakdown["Makanan"] == 80000
        assert expense_breakdown["Transportasi"] == 20000

    def test_daily_summary_latest_five(self, report_service, mock_sheets_transactions):
        txs = [
            {"id": str(i), "tipe": "expense", "jumlah": i * 1000, "kategori": "A", "tanggal": "2026-06-21", "deskripsi": "", "created_at": str(i)}
            for i in range(1, 8)
        ]
        mock_sheets_transactions.get_today.return_value = txs

        summary = report_service.get_daily_summary("123", "SS_ID")

        assert len(summary["latest"]) == 5
        assert summary["latest"][0]["id"] == "7"


class TestReportServiceWeeklySummary:
    def test_weekly_summary_filters_current_week(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_by_date_range.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 10000, "kategori": "A", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "1"},
            {"id": "2", "tipe": "expense", "jumlah": 20000, "kategori": "B", "tanggal": "2026-06-14", "deskripsi": "", "created_at": "2"},
        ]

        summary = report_service.get_weekly_summary("123", "SS_ID")

        # 2026-06-21 is a Sunday; 2026-06-14 is previous Sunday -> should be excluded
        assert summary["expense"] == 10000

    def test_weekly_summary_includes_monday_to_sunday(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_by_date_range.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 10000, "kategori": "A", "tanggal": "2026-06-15", "deskripsi": "", "created_at": "1"},
            {"id": "2", "tipe": "expense", "jumlah": 20000, "kategori": "B", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "2"},
        ]

        summary = report_service.get_weekly_summary("123", "SS_ID")

        assert summary["expense"] == 30000


class TestReportServiceMonthlySummary:
    def test_monthly_summary_includes_previous_month(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_by_date_range.side_effect = [
            [
                {"id": "1", "tipe": "expense", "jumlah": 200000, "kategori": "A", "tanggal": "2026-06-01", "deskripsi": "", "created_at": "1"},
            ],
            [
                {"id": "2", "tipe": "expense", "jumlah": 100000, "kategori": "A", "tanggal": "2026-05-01", "deskripsi": "", "created_at": "2"},
            ],
        ]

        summary = report_service.get_monthly_summary("123", "SS_ID")

        assert summary["expense"] == 200000
        assert summary["previous"]["expense"] == 100000
        assert summary["comparison"]["expense_pct"] == 100.0

    def test_monthly_summary_handles_zero_previous(self, report_service, mock_sheets_transactions):
        mock_sheets_transactions.get_by_date_range.side_effect = [
            [
                {"id": "1", "tipe": "income", "jumlah": 500000, "kategori": "Gaji", "tanggal": "2026-06-01", "deskripsi": "", "created_at": "1"},
            ],
            [],
        ]

        summary = report_service.get_monthly_summary("123", "SS_ID")

        assert summary["income"] == 500000
        assert summary["previous"]["income"] == 0
        assert summary["comparison"]["income_pct"] == 100.0


class TestReportServiceCategoryBreakdown:
    def test_generate_category_breakdown_groups_by_type(self, report_service):
        transactions = [
            {"tipe": "expense", "jumlah": 10000, "kategori": "Makanan"},
            {"tipe": "expense", "jumlah": 20000, "kategori": "Makanan"},
            {"tipe": "income", "jumlah": 50000, "kategori": "Gaji"},
        ]

        breakdown = report_service.generate_category_breakdown(transactions)

        assert breakdown["expense"]["Makanan"] == 30000
        assert breakdown["income"]["Gaji"] == 50000

    def test_generate_category_breakdown_defaults_category(self, report_service):
        transactions = [
            {"tipe": "expense", "jumlah": 10000, "kategori": ""},
        ]

        breakdown = report_service.generate_category_breakdown(transactions)

        assert breakdown["expense"]["Lainnya"] == 10000


class TestReportServiceChartGeneration:
    @patch("src.services.report_service.plt")
    @patch("src.services.report_service.tempfile.mkstemp")
    def test_generate_weekly_chart_creates_png(self, mock_mkstemp, mock_plt, report_service, mock_sheets_transactions):
        mock_mkstemp.return_value = (3, "/tmp/weekly_report_abc.png")
        mock_plt.subplots.return_value = (MagicMock(), MagicMock())
        mock_sheets_transactions.get_by_date_range.return_value = []

        path = report_service.generate_weekly_chart("123", "SS_ID")

        assert path == "/tmp/weekly_report_abc.png"
        mock_plt.subplots.assert_called_once()
        mock_plt.close.assert_called_once()

    @patch("src.services.report_service.os.close")
    @patch("src.services.report_service.plt")
    @patch("src.services.report_service.tempfile.mkstemp")
    def test_generate_weekly_chart_aggregates_by_day(self, mock_mkstemp, mock_plt, mock_os_close, report_service, mock_sheets_transactions):
        mock_mkstemp.return_value = (3, "/tmp/weekly_report_def.png")
        mock_plt.subplots.return_value = (MagicMock(), MagicMock())
        # 2026-06-21 is Sunday; Monday is 2026-06-15
        mock_sheets_transactions.get_by_date_range.return_value = [
            {"id": "1", "tipe": "expense", "jumlah": 10000, "kategori": "A", "tanggal": "2026-06-15", "deskripsi": "", "created_at": "1"},
            {"id": "2", "tipe": "expense", "jumlah": 20000, "kategori": "A", "tanggal": "2026-06-15", "deskripsi": "", "created_at": "2"},
            {"id": "3", "tipe": "expense", "jumlah": 5000, "kategori": "A", "tanggal": "2026-06-21", "deskripsi": "", "created_at": "3"},
        ]

        report_service.generate_weekly_chart("123", "SS_ID")

        _, ax = mock_plt.subplots.return_value
        assert ax.bar.called

    def test_report_service_has_services(self, report_service, mock_sheets_transactions, tx_service):
        assert report_service.sheets is mock_sheets_transactions
        assert report_service.tx_service is tx_service
