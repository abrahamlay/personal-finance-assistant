"""Budget business logic: limits, usage percentages, and warnings."""
from src.sheets.budgets import SheetsBudgets
from src.sheets.transactions import SheetsTransactions
from src.auth.token_store import TokenStore


WARNING_THRESHOLDS = [
    (1.0, "🚨"),
    (0.9, "🔴"),
    (0.8, "⚠️"),
    (0.5, "💡"),
]

FREE_BUDGET_LIMIT = 1


class BudgetService:
    """High-level budget operations and alert generation."""

    def __init__(
        self,
        sheets_budgets: SheetsBudgets,
        sheets_transactions: SheetsTransactions,
        token_store: TokenStore,
    ):
        self.budgets = sheets_budgets
        self.transactions = sheets_transactions
        self.token_store = token_store

    def _is_premium(self, telegram_id: str) -> bool:
        return self.token_store.get_active_subscription(telegram_id) is not None

    def set_budget(
        self,
        telegram_id: str,
        ss_id: str,
        category: str,
        amount: int,
        period: str,
        month_str: str,
    ) -> dict:
        """Create or update a budget. Free users are limited to 1 total budget."""
        if not self._is_premium(telegram_id):
            existing = self.budgets.list_all(telegram_id, ss_id)
            # Free tier allows 1 total budget.
            if len(existing) >= FREE_BUDGET_LIMIT:
                return {"success": False, "error": "free_tier_limit"}

        return self.budgets.set(telegram_id, ss_id, category, amount, period, month_str)

    def get_usage(
        self, telegram_id: str, ss_id: str, category: str, month_str: str
    ) -> dict:
        """Return usage percentage: terpakai / jumlah_bulan * 100."""
        budget = self.budgets.get(telegram_id, ss_id, category, month_str)
        if not budget:
            return {"found": False}

        jumlah_bulan = budget["jumlah_bulan"]
        percentage = (
            (budget["terpakai"] / jumlah_bulan * 100) if jumlah_bulan else 0
        )
        return {
            "found": True,
            "kategori": category,
            "jumlah_bulan": jumlah_bulan,
            "terpakai": budget["terpakai"],
            "percentage": percentage,
        }

    def check_budget_warnings(
        self, telegram_id: str, ss_id: str, category: str, month_str: str
    ) -> str | None:
        """Return a warning message if a usage threshold is crossed."""
        usage = self.get_usage(telegram_id, ss_id, category, month_str)
        if not usage["found"]:
            return None

        pct = usage["percentage"]
        for threshold, emoji in WARNING_THRESHOLDS:
            if pct >= threshold * 100:
                return f"{emoji} Budget {category} sudah {pct:.0f}% terpakai!"
        return None

    def track_transaction(
        self,
        telegram_id: str,
        ss_id: str,
        category: str,
        amount: int,
        month_str: str,
    ) -> str | None:
        """Update budget usage after a transaction and return any warning."""
        result = self.budgets.add_usage(telegram_id, ss_id, category, amount, month_str)
        if not result.get("found"):
            return None
        return self.check_budget_warnings(telegram_id, ss_id, category, month_str)
