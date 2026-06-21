"""Recurring transaction manager using PTB JobQueue."""
import json
import logging
import time
from datetime import datetime, timedelta

from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class RecurringService:
    """Store and process recurring transactions and bill reminders."""

    FREE_RECURRING_LIMIT = 3

    def __init__(self, transaction_service, token_store, sheets_categories=None):
        self.tx_service = transaction_service
        self.token_store = token_store
        self.sheets_categories = sheets_categories

    def _is_premium(self, telegram_id: str) -> bool:
        return self.token_store.get_active_subscription(telegram_id) is not None

    def _get_config(self, telegram_id: str) -> list[dict]:
        user = self.token_store.get_user_token(telegram_id) or {}
        raw = user.get("recurring_config")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _set_config(self, telegram_id: str, config: list[dict]) -> None:
        self.token_store.update_user_token(telegram_id, recurring_config=json.dumps(config))

    def list_recurring(self, telegram_id: str) -> list[dict]:
        """Return user's recurring configs with computed next-run info."""
        now = time.time()
        items = []
        for cfg in self._get_config(telegram_id):
            next_run = cfg.get("next_run")
            hours_until = (
                round((next_run - now) / 3600, 1)
                if isinstance(next_run, (int, float))
                else None
            )
            items.append({**cfg, "hours_until": hours_until})
        return items

    def add_recurring(
        self,
        telegram_id: str,
        ss_id: str,
        description: str,
        amount: int,
        category: str,
        interval_days: int,
        next_run: float,
        reminder_hours: int = 24,
    ) -> dict:
        """Store recurring transaction config in SQLite via token_store."""
        if not self._is_premium(telegram_id):
            existing = self._get_config(telegram_id)
            if len(existing) >= self.FREE_RECURRING_LIMIT:
                return {"success": False, "error": "free_tier_limit"}

        config = self._get_config(telegram_id)
        cfg_id = max([c.get("id", 0) for c in config] or [0]) + 1
        config.append(
            {
                "id": cfg_id,
                "spreadsheet_id": ss_id,
                "description": description,
                "amount": amount,
                "category": category,
                "interval_days": interval_days,
                "next_run": next_run,
                "reminder_hours": reminder_hours,
                "reminder_sent": False,
                "enabled": True,
                "created_at": time.time(),
            }
        )
        self._set_config(telegram_id, config)
        return {"success": True, "id": cfg_id}

    def update_recurring(self, telegram_id: str, cfg_id: int, **kwargs) -> dict:
        """Update fields of an existing recurring config."""
        config = self._get_config(telegram_id)
        for cfg in config:
            if cfg.get("id") == cfg_id:
                for key, value in kwargs.items():
                    if key in cfg:
                        cfg[key] = value
                self._set_config(telegram_id, config)
                return {"success": True}
        return {"success": False, "error": "not_found"}

    def delete_recurring(self, telegram_id: str, cfg_id: int) -> dict:
        """Remove a recurring config."""
        config = self._get_config(telegram_id)
        new_config = [c for c in config if c.get("id") != cfg_id]
        if len(new_config) == len(config):
            return {"success": False, "error": "not_found"}
        self._set_config(telegram_id, new_config)
        return {"success": True}

    async def process_due(self, context: ContextTypes.DEFAULT_TYPE):
        """JobQueue callback: create transactions for due reminders and re-schedule."""
        now = time.time()
        token_store = context.bot_data.get("token_store")
        if not token_store:
            return

        # Iterate over all known users. Simplest is to scan for users with recurring_config.
        # Since token_store has no list method, we do it via direct DB access if available.
        users = self._list_users_with_recurring(token_store)
        for telegram_id, ss_id in users:
            config = self._get_config(telegram_id)
            updated = False
            for cfg in config:
                if not cfg.get("enabled"):
                    continue
                next_run = cfg.get("next_run")
                reminder_hours = cfg.get("reminder_hours", 24)
                if not isinstance(next_run, (int, float)):
                    continue

                # Send reminder before due
                if not cfg.get("reminder_sent") and now >= next_run - reminder_hours * 3600:
                    await self.send_reminder(context, telegram_id, cfg)
                    cfg["reminder_sent"] = True
                    updated = True

                # Create transaction when due
                if now >= next_run:
                    try:
                        today = datetime.fromtimestamp(next_run).strftime("%Y-%m-%d")
                        self.tx_service.create(
                            telegram_id,
                            ss_id,
                            "expense",
                            cfg.get("category", "Lainnya"),
                            cfg.get("amount", 0),
                            cfg.get("description", ""),
                            today,
                        )
                    except Exception:
                        logger.exception("Failed to create recurring tx for %s", telegram_id)
                        continue

                    interval = cfg.get("interval_days", 30)
                    cfg["next_run"] = next_run + interval * 86400
                    cfg["reminder_sent"] = False
                    updated = True

            if updated:
                self._set_config(telegram_id, config)

    def _list_users_with_recurring(self, token_store) -> list[tuple[str, str]]:
        """Return (telegram_id, spreadsheet_id) for users with recurring config."""
        try:
            conn = token_store._connect()
            rows = conn.execute(
                "SELECT telegram_id, spreadsheet_id, recurring_config FROM user_tokens "
                "WHERE recurring_config IS NOT NULL AND recurring_config != ''"
            ).fetchall()
            conn.close()
            return [(r["telegram_id"], r["spreadsheet_id"] or "") for r in rows]
        except Exception:
            logger.exception("Failed to list recurring users")
            return []

    async def send_reminder(self, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, cfg: dict):
        """Send Telegram reminder message: 'Besok bayar wifi 350rb'"""
        bot = context.bot
        amount = cfg.get("amount", 0)
        description = cfg.get("description", "tagihan")
        try:
            await bot.send_message(
                chat_id=int(telegram_id),
                text=(
                    f"⏰ *Pengingat Tagihan*\n\n"
                    f"Besok bayar *{description}* Rp {amount:,}.\n"
                    f"Kategori: {cfg.get('category', 'Lainnya')}\n\n"
                    f"Aku akan otomatis mencatat transaksi ini saat jatuh tempo."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Failed to send reminder to %s", telegram_id)

    def parse_interval(self, text: str) -> int | None:
        """Parse 'mingguan'/'bulanan' or numeric days."""
        text = text.strip().lower()
        if text in ("mingguan", "minggu"):
            return 7
        if text in ("bulanan", "bulan"):
            return 30
        if text.isdigit():
            return int(text)
        return None

    def parse_date(self, text: str) -> datetime | None:
        """Parse 'besok', 'hari ini', or YYYY-MM-DD / DD-MM-YYYY."""
        text = text.strip().lower()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if text in ("besok", "tomorrow"):
            return today + timedelta(days=1)
        if text in ("hari ini", "today"):
            return today
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            except ValueError:
                continue
        return None
