"""Google Sheets operations for the anggaran tab."""
from src.sheets.client import SheetsClient


class SheetsBudgets:
    """Low-level CRUD for budget rows."""

    TAB = "anggaran"

    def __init__(self, sheets_client: SheetsClient):
        self.sheets = sheets_client

    def _read_rows(self, telegram_id: str, ss_id: str) -> list[list[str]]:
        return self.sheets.read_all_rows(telegram_id, ss_id, self.TAB)

    def _row_to_dict(self, row: list[str]) -> dict:
        return {
            "id": row[0],
            "kategori": row[1] if len(row) > 1 else "",
            "jumlah_bulan": int(row[2]) if len(row) > 2 and row[2].isdigit() else 0,
            "bulan": row[3] if len(row) > 3 else "",
            "terpakai": int(row[4]) if len(row) > 4 and row[4].lstrip("-").isdigit() else 0,
            "periode": row[5] if len(row) > 5 else "bulanan",
        }

    def list_all(self, telegram_id: str, ss_id: str, month_str: str | None = None) -> list[dict]:
        """Return all budgets, optionally filtered by month."""
        rows = self._read_rows(telegram_id, ss_id)
        budgets = []
        for row in rows:
            if not row or not row[0]:
                continue
            budget = self._row_to_dict(row)
            if month_str is None or budget["bulan"] == month_str:
                budgets.append(budget)
        return budgets

    def get(self, telegram_id: str, ss_id: str, category: str, month_str: str) -> dict | None:
        """Get a single budget by category and month."""
        for budget in self.list_all(telegram_id, ss_id, month_str):
            if budget["kategori"] == category:
                return budget
        return None

    def set(
        self,
        telegram_id: str,
        ss_id: str,
        category: str,
        amount: int,
        period: str,
        month_str: str,
    ) -> dict:
        """Create or update a budget for a category + month."""
        rows = self._read_rows(telegram_id, ss_id)
        for i, row in enumerate(rows):
            if len(row) > 3 and row[1] == category and row[3] == month_str:
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 3, str(amount)
                )
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 4, month_str
                )
                # Reset usage for the new month/period.
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 5, "0"
                )
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 6, period
                )
                return {"success": True, "id": row[0]}

        new_id = max([int(r[0]) for r in rows if r and r[0].isdigit()] or [0]) + 1
        self.sheets.append_row(
            telegram_id,
            ss_id,
            self.TAB,
            [str(new_id), category, str(amount), month_str, "0", period],
        )
        return {"success": True, "id": new_id}

    def delete(self, telegram_id: str, ss_id: str, category: str, month_str: str) -> bool:
        """Soft-delete a budget by clearing its row."""
        rows = self._read_rows(telegram_id, ss_id)
        for i, row in enumerate(rows):
            if len(row) > 3 and row[1] == category and row[3] == month_str:
                for col in range(2, 7):
                    self.sheets.update_cell(
                        telegram_id, ss_id, self.TAB, i + 2, col, ""
                    )
                return True
        return False

    def add_usage(
        self, telegram_id: str, ss_id: str, category: str, amount: int, month_str: str
    ) -> dict:
        """Increment terpakai for a category budget."""
        budget = self.get(telegram_id, ss_id, category, month_str)
        if not budget:
            return {"found": False}

        new_used = budget["terpakai"] + amount
        rows = self._read_rows(telegram_id, ss_id)
        for i, row in enumerate(rows):
            if len(row) > 3 and row[1] == category and row[3] == month_str:
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 5, str(new_used)
                )
                return {"found": True, "terpakai": new_used}
        return {"found": False}
