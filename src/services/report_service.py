"""Report business logic: aggregation, summaries, and chart generation."""
import os
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.sheets.transactions import SheetsTransactions
from src.services.transaction_service import TransactionService


class ReportService:
    """Generate financial summaries and matplotlib charts."""

    def __init__(
        self,
        sheets_transactions: SheetsTransactions,
        transaction_service: TransactionService,
    ):
        self.sheets = sheets_transactions
        self.tx_service = transaction_service

    # ------------------------------------------------------------------
    # Public summaries
    # ------------------------------------------------------------------
    def get_daily_summary(self, telegram_id: str, ss_id: str) -> dict:
        """Return today's income, expense, saldo, category breakdown, latest 5."""
        transactions = self.tx_service.get_today(telegram_id, ss_id)
        return self._build_summary(transactions)

    def get_weekly_summary(self, telegram_id: str, ss_id: str) -> dict:
        """Return current week (Mon-Sun) summary."""
        today = datetime.now()
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)  # Sunday
        transactions = self.tx_service.get_by_month(
            telegram_id, ss_id, today.year, today.month
        )
        # Filter by actual date range
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        week_transactions = [t for t in transactions if start_str <= t.get("tanggal", "") <= end_str]
        return self._build_summary(week_transactions)

    def get_monthly_summary(self, telegram_id: str, ss_id: str) -> dict:
        """Return current month summary + comparison with last month."""
        now = datetime.now()
        current_transactions = self.tx_service.get_by_month(
            telegram_id, ss_id, now.year, now.month
        )
        current = self._build_summary(current_transactions)

        # Previous month
        if now.month == 1:
            prev_year = now.year - 1
            prev_month = 12
        else:
            prev_year = now.year
            prev_month = now.month - 1
        prev_transactions = self.tx_service.get_by_month(
            telegram_id, ss_id, prev_year, prev_month
        )
        previous = self._build_summary(prev_transactions)

        current["previous"] = previous
        current["comparison"] = self._compare(current, previous)
        return current

    def generate_category_breakdown(self, transactions: list[dict]) -> dict:
        """Return expense/income breakdown per category."""
        breakdown = {"expense": defaultdict(int), "income": defaultdict(int)}
        for t in transactions:
            tipe = t.get("tipe")
            kategori = t.get("kategori") or "Lainnya"
            amount = t.get("jumlah", 0)
            if tipe in breakdown:
                breakdown[tipe][kategori] += amount
        return {
            "expense": dict(sorted(breakdown["expense"].items(), key=lambda x: -x[1])),
            "income": dict(sorted(breakdown["income"].items(), key=lambda x: -x[1])),
        }

    # ------------------------------------------------------------------
    # Chart generation
    # ------------------------------------------------------------------
    def generate_weekly_chart(self, telegram_id: str, ss_id: str) -> str:
        """Create a matplotlib bar chart of daily expenses for current week.

        Returns the path to a temporary PNG file.
        """
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        days = [(start + timedelta(days=i)) for i in range(7)]
        day_labels = [d.strftime("%a") for d in days]
        day_keys = [d.strftime("%Y-%m-%d") for d in days]

        # Fetch current month then filter by week
        month_transactions = self.tx_service.get_by_month(
            telegram_id, ss_id, today.year, today.month
        )
        expenses_by_day = defaultdict(int)
        for t in month_transactions:
            if t.get("tipe") == "expense":
                expenses_by_day[t.get("tanggal", "")] += t.get("jumlah", 0)

        values = [expenses_by_day.get(k, 0) for k in day_keys]

        fig, ax = plt.subplots(figsize=(7, 4))
        bars = ax.bar(day_labels, values, color="#4A90D9")
        ax.set_title("Pengeluaran Minggu Ini")
        ax.set_ylabel("Rp")
        ax.set_xlabel("Hari")
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"Rp {int(height):,}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        plt.tight_layout()

        fd, path = tempfile.mkstemp(suffix=".png", prefix="weekly_report_")
        os.close(fd)
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_summary(self, transactions: list[dict]) -> dict:
        income = sum(t.get("jumlah", 0) for t in transactions if t.get("tipe") == "income")
        expense = sum(t.get("jumlah", 0) for t in transactions if t.get("tipe") == "expense")
        breakdown = self.generate_category_breakdown(transactions)
        latest = sorted(
            transactions,
            key=lambda t: t.get("created_at", "") or t.get("tanggal", ""),
            reverse=True,
        )[:5]
        return {
            "income": income,
            "expense": expense,
            "saldo": income - expense,
            "count": len(transactions),
            "category_breakdown": breakdown,
            "latest": latest,
        }

    def _compare(self, current: dict, previous: dict) -> dict:
        def diff_pct(cur, prev):
            if prev == 0:
                return 100.0 if cur else 0.0
            return round(((cur - prev) / prev) * 100, 1)

        return {
            "income_pct": diff_pct(current["income"], previous["income"]),
            "expense_pct": diff_pct(current["expense"], previous["expense"]),
            "saldo_pct": diff_pct(current["saldo"], previous["saldo"]),
        }
