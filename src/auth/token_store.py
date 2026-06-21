import sqlite3
import time
from typing import Any

from src.auth.encryption import decrypt_token, encrypt_token


_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_tokens (
    telegram_id TEXT PRIMARY KEY,
    spreadsheet_id TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expiry REAL,
    display_name TEXT,
    language TEXT DEFAULT 'id',
    ocr_usage TEXT,
    recurring_config TEXT,
    categories TEXT,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT,
    plan TEXT CHECK(plan IN ('monthly','yearly','lifetime')),
    status TEXT CHECK(status IN ('trial','pending','active','grace','expired','cancelled')),
    start_date REAL,
    end_date REAL,
    trial_end REAL,
    payment_method TEXT,
    payment_ref TEXT,
    auto_renew INTEGER DEFAULT 1,
    created_at REAL,
    updated_at REAL,
    FOREIGN KEY(telegram_id) REFERENCES user_tokens(telegram_id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT,
    subscription_id INTEGER,
    amount INTEGER,
    method TEXT,
    status TEXT,
    payment_ref TEXT,
    raw_response TEXT,
    created_at REAL,
    FOREIGN KEY(telegram_id) REFERENCES user_tokens(telegram_id)
);
"""


class TokenStore:
    """SQLite-backed store for OAuth tokens, subscriptions, and invoices."""

    def __init__(self, db_path: str = "token_store.db") -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        """Create tables if they do not already exist."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
        self._migrate_user_tokens()

    # ------------------------------------------------------------------
    # user_tokens
    # ------------------------------------------------------------------
    def create_user_token(
        self,
        telegram_id: str,
        access_token: str,
        refresh_token: str,
        token_expiry: float,
        spreadsheet_id: str | None = None,
        display_name: str | None = None,
        language: str = "id",
        created_at: float | None = None,
        updated_at: float | None = None,
    ) -> dict[str, Any] | None:
        now = time.time()
        created_at = created_at or now
        updated_at = updated_at or now
        encrypted_refresh = encrypt_token(refresh_token)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_tokens
                (telegram_id, spreadsheet_id, access_token, refresh_token,
                 token_expiry, display_name, language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_id,
                    spreadsheet_id,
                    access_token,
                    encrypted_refresh,
                    token_expiry,
                    display_name,
                    language,
                    created_at,
                    updated_at,
                ),
            )
            conn.commit()
        return self.get_user_token(telegram_id)

    def get_user_token(self, telegram_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_tokens WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode_user_token_row(row)

    def update_user_token(
        self,
        telegram_id: str,
        spreadsheet_id: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: float | None = None,
        display_name: str | None = None,
        language: str | None = None,
        ocr_usage: str | None = None,
        recurring_config: str | None = None,
        categories: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {"updated_at": time.time()}
        if spreadsheet_id is not None:
            updates["spreadsheet_id"] = spreadsheet_id
        if access_token is not None:
            updates["access_token"] = access_token
        if refresh_token is not None:
            updates["refresh_token"] = encrypt_token(refresh_token)
        if token_expiry is not None:
            updates["token_expiry"] = token_expiry
        if display_name is not None:
            updates["display_name"] = display_name
        if language is not None:
            updates["language"] = language
        if ocr_usage is not None:
            updates["ocr_usage"] = ocr_usage
        if recurring_config is not None:
            updates["recurring_config"] = recurring_config
        if categories is not None:
            updates["categories"] = categories

        columns = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [telegram_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE user_tokens SET {columns} WHERE telegram_id = ?",
                values,
            )
            conn.commit()
        return self.get_user_token(telegram_id)

    def delete_user_token(self, telegram_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_tokens WHERE telegram_id = ?",
                (telegram_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # subscriptions
    # ------------------------------------------------------------------
    def create_subscription(
        self,
        telegram_id: str,
        plan: str,
        status: str,
        start_date: float,
        end_date: float,
        trial_end: float | None = None,
        payment_method: str | None = None,
        payment_ref: str | None = None,
        auto_renew: bool = True,
        created_at: float | None = None,
        updated_at: float | None = None,
    ) -> dict[str, Any] | None:
        now = time.time()
        created_at = created_at or now
        updated_at = updated_at or now
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO subscriptions
                (telegram_id, plan, status, start_date, end_date, trial_end,
                 payment_method, payment_ref, auto_renew, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_id,
                    plan,
                    status,
                    start_date,
                    end_date,
                    trial_end,
                    payment_method,
                    payment_ref,
                    1 if auto_renew else 0,
                    created_at,
                    updated_at,
                ),
            )
            conn.commit()
            subscription_id = cursor.lastrowid
        return self.get_subscription_by_id(subscription_id)

    def get_subscription(self, telegram_id: str) -> dict[str, Any] | None:
        """Return the most recent subscription for a user."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 1",
                (telegram_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_subscription_by_id(self, subscription_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_subscription_status(
        self,
        subscription_id: int,
        status: str,
        end_date: float | None = None,
    ) -> dict[str, Any] | None:
        return self.update_subscription(
            subscription_id,
            status=status,
            end_date=end_date,
        )

    def update_subscription(
        self,
        subscription_id: int,
        status: str | None = None,
        end_date: float | None = None,
        trial_end: float | None = None,
        auto_renew: bool | None = None,
        payment_ref: str | None = None,
        payment_method: str | None = None,
    ) -> dict[str, Any] | None:
        updates: dict[str, Any] = {"updated_at": time.time()}
        if status is not None:
            updates["status"] = status
        if end_date is not None:
            updates["end_date"] = end_date
        if trial_end is not None:
            updates["trial_end"] = trial_end
        if auto_renew is not None:
            updates["auto_renew"] = 1 if auto_renew else 0
        if payment_ref is not None:
            updates["payment_ref"] = payment_ref
        if payment_method is not None:
            updates["payment_method"] = payment_method

        columns = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [subscription_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE subscriptions SET {columns} WHERE id = ?",
                values,
            )
            conn.commit()
        return self.get_subscription_by_id(subscription_id)

    def get_active_subscription(self, telegram_id: str) -> dict[str, Any] | None:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE telegram_id = ?
                  AND status = 'active'
                  AND end_date > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (telegram_id, now),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # invoices
    # ------------------------------------------------------------------
    def create_invoice(
        self,
        telegram_id: str,
        subscription_id: int,
        amount: int,
        method: str,
        status: str,
        payment_ref: str | None = None,
        raw_response: str | None = None,
        created_at: float | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        created_at = created_at or now
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO invoices
                (telegram_id, subscription_id, amount, method, status,
                 payment_ref, raw_response, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_id,
                    subscription_id,
                    amount,
                    method,
                    status,
                    payment_ref,
                    raw_response,
                    created_at,
                ),
            )
            conn.commit()
            invoice_id = cursor.lastrowid
        return self.get_invoice_by_id(invoice_id)

    def get_invoice_by_id(self, invoice_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()
        return dict(row)

    def get_invoices_by_user(self, telegram_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE telegram_id = ? ORDER BY created_at DESC",
                (telegram_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _migrate_user_tokens(self) -> None:
        """Add columns introduced after initial schema creation."""
        new_columns = [
            ("ocr_usage", "TEXT"),
            ("recurring_config", "TEXT"),
            ("categories", "TEXT"),
        ]
        with self._connect() as conn:
            for column, dtype in new_columns:
                try:
                    conn.execute(
                        f"ALTER TABLE user_tokens ADD COLUMN {column} {dtype}"
                    )
                    conn.commit()
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise

    def _decode_user_token_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        encrypted_refresh = data.get("refresh_token")
        if encrypted_refresh:
            data["refresh_token"] = decrypt_token(encrypted_refresh)
        return data
