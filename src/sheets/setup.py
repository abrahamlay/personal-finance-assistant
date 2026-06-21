"""Creates and initializes a per-user Google Spreadsheet for the finance bot."""
import time
from datetime import datetime
from typing import Optional

import gspread

from src.sheets.client import SheetsClient
from src.auth.token_store import TokenStore
from src.sheets.dashboard import DashboardGenerator

DEFAULT_CATEGORIES = [
    # (nama, tipe, icon)
    ("Makanan", "expense", "🍔"),
    ("Transportasi", "expense", "🚗"),
    ("Belanja", "expense", "🛒"),
    ("Tagihan", "expense", "📄"),
    ("Kesehatan", "expense", "💊"),
    ("Hiburan", "expense", "🎮"),
    ("Pendidikan", "expense", "📚"),
    ("Gaji", "income", "💰"),
    ("Investasi", "income", "📈"),
    ("Hadiah", "income", "🎁"),
    ("Donasi", "expense", "🤝"),
    ("Liburan", "expense", "✈️"),
    ("Lainnya", "expense", "📌"),
]

TAB_HEADERS = {
    "transaksi": ["id", "tanggal", "tipe", "kategori", "jumlah", "deskripsi", "created_at"],
    "kategori": ["id", "nama", "tipe", "is_default", "icon"],
    "anggaran": ["id", "kategori", "jumlah_bulan", "bulan", "terpakai", "periode"],
    "config": ["key", "value"],
    "Dashboard": [],  # Populated later by Wave 6
}


class SheetSetupService:
    def __init__(
        self,
        sheets_client: SheetsClient,
        token_store: TokenStore,
        dashboard_generator: DashboardGenerator | None = None,
    ):
        self.sheets = sheets_client
        self.token_store = token_store
        self.dashboard_generator = dashboard_generator

    def setup_new_user(self, telegram_id: str, display_name: str) -> str:
        """Full setup: create spreadsheet, tabs, default data, store ID. Returns spreadsheet_id."""
        # 1. Check if user already has a spreadsheet
        user = self.token_store.get_user_token(telegram_id)
        if user and user.get("spreadsheet_id"):
            return user["spreadsheet_id"]  # Already set up

        # 2. Create new spreadsheet
        ss_id = self._create_spreadsheet(telegram_id, display_name)

        # 3. Create all tabs
        self._create_tabs(telegram_id, ss_id)

        # 4. Preload default categories
        self._preload_categories(telegram_id, ss_id)

        # 5. Initialize config
        self._initialize_config(telegram_id, ss_id, display_name)

        # 6. Build Dashboard tab (free tier by default; upgraded on /perbaiki)
        if self.dashboard_generator:
            self.dashboard_generator.build(telegram_id, ss_id, is_premium=False)

        # 7. Store spreadsheet ID
        self.token_store.update_user_token(telegram_id, spreadsheet_id=ss_id)

        return ss_id

    def _create_spreadsheet(self, telegram_id: str, display_name: str) -> str:
        """Create a new Google Spreadsheet titled 'KeuanganBot - {name}'."""
        client = self.sheets.authenticate(telegram_id)
        title = f"KeuanganBot - {display_name}"
        spreadsheet = client.create(title)
        return spreadsheet.id

    def _create_tabs(self, telegram_id: str, spreadsheet_id: str):
        """Create 5 tabs: transaksi, kategori, anggaran, config, Dashboard."""
        client = self.sheets.authenticate(telegram_id)
        sheet = client.open_by_key(spreadsheet_id)

        for tab_name, headers in TAB_HEADERS.items():
            try:
                sheet.worksheet(tab_name)
            except gspread.exceptions.WorksheetNotFound:
                sheet.add_worksheet(title=tab_name, rows=1000, cols=26)

            if headers:
                self.sheets.append_row(
                    telegram_id, spreadsheet_id, tab_name, headers
                )

    def _preload_categories(self, telegram_id: str, spreadsheet_id: str):
        """Preload 13 default categories into the kategori tab."""
        for idx, (nama, tipe, icon) in enumerate(DEFAULT_CATEGORIES, start=1):
            self.sheets.append_row(
                telegram_id,
                spreadsheet_id,
                "kategori",
                [str(idx), nama, tipe, "TRUE", icon],
            )

    def _initialize_config(self, telegram_id: str, spreadsheet_id: str, display_name: str):
        """Set config values: telegram_id, first_name, language, join_date, premium_status."""
        join_date = datetime.now().strftime("%Y-%m-%d")
        config_rows = [
            ["telegram_id", telegram_id],
            ["first_name", display_name],
            ["language", "id"],
            ["join_date", join_date],
            ["premium_status", "free"],
        ]
        for key, value in config_rows:
            self.sheets.append_row(
                telegram_id, spreadsheet_id, "config", [key, value]
            )
