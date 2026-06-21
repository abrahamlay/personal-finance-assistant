"""Transaction business logic: CRUD, deduplication, aggregation."""
import time
from datetime import datetime
from src.sheets.transactions import SheetsTransactions
from src.cache.memory_cache import MemoryCache


class TransactionService:
    def __init__(self, sheets_transactions: SheetsTransactions, cache: MemoryCache):
        self.sheets = sheets_transactions
        self.cache = cache

    def create(self, telegram_id: str, spreadsheet_id: str,
               transaction_type: str, category: str, amount: int,
               description: str, date_str: str) -> dict:
        """Create transaction with dedup check. Returns {row_id, was_duplicate, today_total}."""
        # Dedup check
        dedup_key = f"{telegram_id}:{spreadsheet_id}"
        dedup_value = f"{amount}:{category}:{date_str}"
        if self.cache.is_duplicate(dedup_key, dedup_value):
            return {"row_id": None, "was_duplicate": True, "today_total": self._get_today_total(telegram_id, spreadsheet_id)}

        row_id = self.sheets.append(telegram_id, spreadsheet_id, transaction_type, category, amount, description, date_str)
        self.cache.mark_processed(dedup_key, dedup_value)
        self.cache.update_daily_total(dedup_key, date_str, amount, transaction_type)

        return {"row_id": row_id, "was_duplicate": False, "today_total": self._get_today_total(telegram_id, spreadsheet_id)}

    def get_today(self, telegram_id: str, spreadsheet_id: str) -> list[dict]:
        return self.sheets.get_today(telegram_id, spreadsheet_id)

    def get_by_month(self, telegram_id: str, spreadsheet_id: str, year: int, month: int) -> list[dict]:
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"
        return self.sheets.get_by_date_range(telegram_id, spreadsheet_id, start, end)

    def update(self, telegram_id: str, spreadsheet_id: str, row_id: int, **kwargs) -> bool:
        return self.sheets.update(telegram_id, spreadsheet_id, row_id, **kwargs)

    def delete(self, telegram_id: str, spreadsheet_id: str, row_id: int) -> bool:
        return self.sheets.delete(telegram_id, spreadsheet_id, row_id)

    def _get_today_total(self, telegram_id: str, spreadsheet_id: str) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"{telegram_id}:{spreadsheet_id}"
        cached = self.cache.get_daily_total(key, today)
        # Also compute from sheets for accuracy
        expenses = sum(t["jumlah"] for t in self.get_today(telegram_id, spreadsheet_id) if t.get("tipe") == "expense")
        income = sum(t["jumlah"] for t in self.get_today(telegram_id, spreadsheet_id) if t.get("tipe") == "income")
        count = len(self.get_today(telegram_id, spreadsheet_id))
        return {"expense": expenses, "income": income, "count": count}
