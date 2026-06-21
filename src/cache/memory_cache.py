"""In-memory cache for deduplication and daily transaction totals."""
import time
from collections import defaultdict


class MemoryCache:
    def __init__(self):
        self._dedup: dict[str, set] = defaultdict(set)
        self._daily_totals: dict[str, dict] = {}
        self._last_cleanup = time.time()

    def is_duplicate(self, key: str, value: str) -> bool:
        """Check if a transaction was recently processed (within 5 min window)."""
        # Cleanup entries older than 5 minutes
        now = time.time()
        if now - self._last_cleanup > 300:  # 5 minutes
            self._dedup.clear()
            self._last_cleanup = now
        return value in self._dedup[key]

    def mark_processed(self, key: str, value: str):
        """Record that a transaction was processed."""
        self._dedup[key].add(value)

    def get_daily_total(self, user_id: str, date_str: str) -> dict:
        """Get cached daily totals: {'income': 0, 'expense': 0}"""
        return self._daily_totals.get(f"{user_id}:{date_str}", {"income": 0, "expense": 0})

    def update_daily_total(self, user_id: str, date_str: str, amount: int, tipe: str):
        key = f"{user_id}:{date_str}"
        if key not in self._daily_totals:
            self._daily_totals[key] = {"income": 0, "expense": 0}
        self._daily_totals[key][tipe] += amount

    def clear_daily_total(self, user_id: str, date_str: str):
        self._daily_totals.pop(f"{user_id}:{date_str}", None)
