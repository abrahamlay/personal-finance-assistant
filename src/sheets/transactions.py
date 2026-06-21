"""Google Sheets operations for the transaksi tab."""
import time
from datetime import datetime
from src.sheets.client import SheetsClient


class SheetsTransactions:
    def __init__(self, sheets_client: SheetsClient):
        self.sheets = sheets_client

    def append(self, telegram_id: str, spreadsheet_id: str,
               transaction_type: str, category: str, amount: int,
               description: str, date_str: str) -> int:
        """Append transaction to sheet. Returns new row number."""
        row_id = self._next_id(telegram_id, spreadsheet_id)
        now = datetime.now().isoformat()
        values = [
            str(row_id),           # id
            date_str,              # tanggal
            transaction_type,      # tipe (income/expense)
            category,              # kategori
            str(amount),           # jumlah
            description,           # deskripsi
            now,                   # created_at
        ]
        return self.sheets.append_row(telegram_id, spreadsheet_id, "transaksi", values)

    def get_all(self, telegram_id: str, spreadsheet_id: str) -> list[dict]:
        """Get all transactions."""
        rows = self.sheets.read_all_rows(telegram_id, spreadsheet_id, "transaksi")
        return [self._row_to_dict(r) for r in rows if r and r[0]]

    def get_by_date_range(self, telegram_id: str, spreadsheet_id: str,
                          start_date: str, end_date: str) -> list[dict]:
        """Get transactions within date range."""
        all_rows = self.get_all(telegram_id, spreadsheet_id)
        return [r for r in all_rows if start_date <= r.get("tanggal", "") <= end_date]

    def get_today(self, telegram_id: str, spreadsheet_id: str) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_by_date_range(telegram_id, spreadsheet_id, today, today)

    def update(self, telegram_id: str, spreadsheet_id: str,
               row_id: int, **kwargs) -> bool:
        """Update transaction fields."""
        # Find the row number in sheet (row_id column matches, then update specific columns)
        all_data = self.sheets.read_all_rows(telegram_id, spreadsheet_id, "transaksi")
        sheet_row = None
        for i, row in enumerate(all_data):
            if row and row[0] == str(row_id):
                sheet_row = i + 2  # +1 for 0-indexed, +1 for header
                break
        if not sheet_row:
            return False

        col_map = {"tipe": 3, "kategori": 4, "jumlah": 5, "deskripsi": 6}
        for key, value in kwargs.items():
            if key in col_map:
                self.sheets.update_cell(telegram_id, spreadsheet_id, "transaksi", sheet_row, col_map[key], str(value))
        return True

    def delete(self, telegram_id: str, spreadsheet_id: str, row_id: int) -> bool:
        """Delete transaction by clearing its row."""
        return self.update(telegram_id, spreadsheet_id, row_id,
                          kategori="[dihapus]", jumlah="0", deskripsi="[dihapus]")

    def _next_id(self, telegram_id: str, spreadsheet_id: str) -> int:
        rows = self.get_all(telegram_id, spreadsheet_id)
        if not rows:
            return 1
        ids = [int(r.get("id", 0)) for r in rows if r.get("id")]
        return max(ids) + 1 if ids else 1

    def _row_to_dict(self, row: list[str]) -> dict:
        if len(row) < 7:
            return {}
        return {
            "id": row[0], "tanggal": row[1] if len(row) > 1 else "",
            "tipe": row[2] if len(row) > 2 else "",
            "kategori": row[3] if len(row) > 3 else "",
            "jumlah": int(row[4]) if len(row) > 4 and row[4].lstrip('-').isdigit() else 0,
            "deskripsi": row[5] if len(row) > 5 else "",
            "created_at": row[6] if len(row) > 6 else "",
        }
