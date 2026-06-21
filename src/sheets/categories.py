"""Google Sheets operations for the kategori tab."""
from src.sheets.client import SheetsClient
from src.auth.token_store import TokenStore


DEFAULT_CATEGORY_IDS = set(range(1, 14))
FREE_CUSTOM_CATEGORY_LIMIT = 5


class SheetsCategories:
    """CRUD operations for user-defined and default categories."""

    TAB = "kategori"

    def __init__(self, sheets_client: SheetsClient, token_store: TokenStore):
        self.sheets = sheets_client
        self.token_store = token_store

    def _is_premium(self, telegram_id: str) -> bool:
        """Premium users have an active subscription."""
        return self.token_store.get_active_subscription(telegram_id) is not None

    def _read_categories(self, telegram_id: str, ss_id: str) -> list[dict]:
        """Read and normalize all category rows from the sheet."""
        rows = self.sheets.read_all_rows(telegram_id, ss_id, self.TAB)
        categories = []
        for row in rows:
            if not row or not row[0]:
                continue
            categories.append(
                {
                    "id": row[0],
                    "nama": row[1] if len(row) > 1 else "",
                    "tipe": row[2] if len(row) > 2 else "",
                    "is_default": (row[3] if len(row) > 3 else "").upper() == "TRUE",
                    "icon": row[4] if len(row) > 4 else "📌",
                }
            )
        return categories

    def list_all(self, telegram_id: str, ss_id: str) -> list[dict]:
        """Return all categories (default + custom) with icons."""
        return self._read_categories(telegram_id, ss_id)

    def add(self, telegram_id: str, ss_id: str, name: str, cat_type: str, icon: str) -> dict:
        """Append a custom category. Free users are limited to 5 custom categories."""
        categories = self._read_categories(telegram_id, ss_id)
        custom = [c for c in categories if not c.get("is_default")]
        if not self._is_premium(telegram_id) and len(custom) >= FREE_CUSTOM_CATEGORY_LIMIT:
            return {"success": False, "error": "free_tier_limit"}

        new_id = max([int(c["id"]) for c in categories if c["id"].isdigit()] or [0]) + 1
        self.sheets.append_row(
            telegram_id, ss_id, self.TAB, [str(new_id), name, cat_type, "FALSE", icon]
        )
        return {"success": True, "id": new_id}

    def rename(self, telegram_id: str, ss_id: str, cat_id: str | int, new_name: str) -> bool:
        """Update the name of a category."""
        categories = self._read_categories(telegram_id, ss_id)
        for i, cat in enumerate(categories):
            if cat["id"] == str(cat_id):
                self.sheets.update_cell(
                    telegram_id, ss_id, self.TAB, i + 2, 2, new_name
                )
                return True
        return False

    def delete(self, telegram_id: str, ss_id: str, cat_id: str | int) -> dict:
        """Delete a custom category. Default categories cannot be deleted."""
        categories = self._read_categories(telegram_id, ss_id)
        for i, cat in enumerate(categories):
            if cat["id"] == str(cat_id):
                if cat.get("is_default"):
                    return {"success": False, "error": "cannot_delete_default"}
                # Clear the row to preserve IDs of later rows.
                for col in range(2, 6):
                    self.sheets.update_cell(
                        telegram_id, ss_id, self.TAB, i + 2, col, ""
                    )
                return {"success": True}
        return {"success": False, "error": "not_found"}
