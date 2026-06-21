"""Dashboard tab generator using Google Sheets API v4 batchUpdate."""
import re
from datetime import datetime, timedelta

from googleapiclient.discovery import build

from src.sheets.client import SheetsClient


class DashboardGenerator:
    """Generate and regenerate the Dashboard tab in a user's spreadsheet."""

    def __init__(self, sheets_client: SheetsClient):
        self.sheets = sheets_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build(self, telegram_id: str, ss_id: str, is_premium: bool = False) -> dict:
        """Generate all dashboard content in one batchUpdate call."""
        sheet_id = self._get_sheet_id(telegram_id, ss_id, "Dashboard")
        requests = []
        requests.extend(self._title_cells(sheet_id))
        requests.extend(self._summary_formulas(sheet_id))
        if is_premium:
            requests.extend(self._category_query_table(sheet_id))
            requests.extend(self._pie_chart_request(sheet_id))
            requests.extend(self._bar_chart_request(sheet_id))
            requests.extend(self._sparkline_formulas(sheet_id))
            requests.extend(self._top_expenses_table(sheet_id))
            requests.extend(self._conditional_formatting(sheet_id))
        requests.extend(self._protect_ranges(sheet_id, is_premium))

        self.sheets.batch_update(telegram_id, ss_id, requests)
        return {"sheet_id": sheet_id, "requests_count": len(requests)}

    def get_dashboard_url(self, telegram_id: str, ss_id: str) -> str:
        """Return a direct URL to the Dashboard tab."""
        sheet_id = self._get_sheet_id(telegram_id, ss_id, "Dashboard")
        return f"https://docs.google.com/spreadsheets/d/{ss_id}/edit#gid={sheet_id}"

    def regenerate(self, telegram_id: str, ss_id: str, is_premium: bool = False) -> dict:
        """Clear and rebuild the entire Dashboard tab."""
        sheet_id = self._get_sheet_id(telegram_id, ss_id, "Dashboard")
        clear_request = {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1000,
                    "startColumnIndex": 0,
                    "endColumnIndex": 26,
                },
                "fields": "userEnteredValue,userEnteredFormat",
            }
        }
        self.sheets.batch_update(telegram_id, ss_id, [clear_request])
        return self.build(telegram_id, ss_id, is_premium)

    # ------------------------------------------------------------------
    # Sheet metadata
    # ------------------------------------------------------------------
    def _get_sheet_id(self, telegram_id: str, ss_id: str, title: str) -> int:
        """Fetch numeric sheetId for the given tab title."""
        credentials = self.sheets.oauth_manager.get_valid_credentials(telegram_id)
        service = build("sheets", "v4", credentials=credentials)
        spreadsheet = service.spreadsheets().get(spreadsheetId=ss_id).execute()
        for sheet in spreadsheet.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("title") == title:
                return props.get("sheetId", 0)
        return 0

    # ------------------------------------------------------------------
    # Title & summary
    # ------------------------------------------------------------------
    def _title_cells(self, sheet_id: int) -> list[dict]:
        month_label = datetime.now().strftime("%B %Y")
        return [
            self._cell_value(sheet_id, "A1", "DASHBOARD KEUANGAN", bold=True, font_size=16),
            self._cell_value(sheet_id, "A2", f"Bulan: {month_label}", bold=True),
        ]

    def _summary_formulas(self, sheet_id: int) -> list[dict]:
        return [
            self._cell_value(sheet_id, "A4", "RINGKASAN", bold=True, font_size=12),
            self._cell_value(sheet_id, "A5", "Total Pemasukan:"),
            self._cell_formula(sheet_id, "B5", '=SUMIF(transaksi!C:C,"income",transaksi!E:E)'),
            self._cell_value(sheet_id, "A6", "Total Pengeluaran:"),
            self._cell_formula(sheet_id, "B6", '=SUMIF(transaksi!C:C,"expense",transaksi!E:E)'),
            self._cell_value(sheet_id, "A7", "Saldo:"),
            self._cell_formula(sheet_id, "B7", "=B5-B6"),
            self._cell_value(sheet_id, "A8", "Jumlah Transaksi:"),
            self._cell_formula(sheet_id, "B8", "=COUNTA(transaksi!A:A)-1"),
        ]

    # ------------------------------------------------------------------
    # Premium: category breakdown query + pie chart
    # ------------------------------------------------------------------
    def _category_query_table(self, sheet_id: int) -> list[dict]:
        return [
            self._cell_value(sheet_id, "A10", "PENGELUARAN PER KATEGORI", bold=True, font_size=12),
            self._cell_value(sheet_id, "A11", "Kategori"),
            self._cell_value(sheet_id, "B11", "Jumlah"),
            self._cell_formula(
                sheet_id,
                "A12",
                "=QUERY(transaksi!A:G,\"SELECT D, SUM(E) WHERE C='expense' GROUP BY D LABEL SUM(E) ''\",1)",
            ),
        ]

    def _pie_chart_request(self, sheet_id: int) -> list[dict]:
        chart = {
            "addChart": {
                "chart": {
                    "spec": {
                        "title": "Pengeluaran per Kategori",
                        "pieChart": {
                            "legendPosition": "RIGHT_LEGEND",
                            "domain": {
                                "sourceRange": {
                                    "sources": [
                                        {
                                            "sheetId": sheet_id,
                                            "startRowIndex": 11,
                                            "endRowIndex": 21,
                                            "startColumnIndex": 0,
                                            "endColumnIndex": 1,
                                        }
                                    ]
                                }
                            },
                            "series": {
                                "sourceRange": {
                                    "sources": [
                                        {
                                            "sheetId": sheet_id,
                                            "startRowIndex": 11,
                                            "endRowIndex": 21,
                                            "startColumnIndex": 1,
                                            "endColumnIndex": 2,
                                        }
                                    ]
                                }
                            },
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sheet_id,
                                "rowIndex": 9,
                                "columnIndex": 3,
                            },
                            "offsetXPixels": 0,
                            "offsetYPixels": 0,
                        }
                    },
                }
            }
        }
        return [chart]

    # ------------------------------------------------------------------
    # Premium: 6-month trend bar chart
    # ------------------------------------------------------------------
    def _bar_chart_request(self, sheet_id: int) -> list[dict]:
        now = datetime.now()
        months = []
        for i in range(5, -1, -1):
            d = now - timedelta(days=i * 30)
            months.append(d.strftime("%Y-%m"))

        requests = [
            self._cell_value(sheet_id, "A22", "TREN 6 BULAN", bold=True, font_size=12),
        ]
        for idx, month in enumerate(months, start=23):
            requests.append(self._cell_value(sheet_id, f"A{idx}", month))
            requests.append(
                self._cell_formula(
                    sheet_id,
                    f"B{idx}",
                    f'=SUMIFS(transaksi!E:E,transaksi!C:C,"expense",transaksi!B:B,"{month}*")',
                )
            )
        requests.append(
            self._cell_value(sheet_id, "A30", "Rata-rata:"),
        )
        requests.append(
            self._cell_formula(sheet_id, "B30", "=AVERAGE(B23:B28)"),
        )

        chart = {
            "addChart": {
                "chart": {
                    "spec": {
                        "title": "Tren Pengeluaran 6 Bulan",
                        "basicChart": {
                            "chartType": "COLUMN",
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Bulan"},
                                {"position": "LEFT_AXIS", "title": "Rp"},
                            ],
                            "domains": [
                                {
                                    "domain": {
                                        "sourceRange": {
                                            "sources": [
                                                {
                                                    "sheetId": sheet_id,
                                                    "startRowIndex": 22,
                                                    "endRowIndex": 28,
                                                    "startColumnIndex": 0,
                                                    "endColumnIndex": 1,
                                                }
                                            ]
                                        }
                                    }
                                }
                            ],
                            "series": [
                                {
                                    "series": {
                                        "sourceRange": {
                                            "sources": [
                                                {
                                                    "sheetId": sheet_id,
                                                    "startRowIndex": 22,
                                                    "endRowIndex": 28,
                                                    "startColumnIndex": 1,
                                                    "endColumnIndex": 2,
                                                }
                                            ]
                                        }
                                    },
                                    "targetAxis": "LEFT_AXIS",
                                }
                            ],
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sheet_id,
                                "rowIndex": 21,
                                "columnIndex": 3,
                            }
                        }
                    },
                }
            }
        }
        return requests + [chart]

    # ------------------------------------------------------------------
    # Premium: sparklines
    # ------------------------------------------------------------------
    def _sparkline_formulas(self, sheet_id: int) -> list[dict]:
        today = datetime.now()
        month_start = today.replace(day=1).strftime("%Y-%m-%d")
        return [
            self._cell_value(sheet_id, "A32", "SPARKLINE HARIAN", bold=True, font_size=12),
            self._cell_value(sheet_id, "A33", "Pengeluaran Harian:"),
            self._cell_formula(
                sheet_id,
                "B33",
                f'=SPARKLINE(FILTER(transaksi!E:E,transaksi!C:C="expense",transaksi!B:B>="{month_start}"),{{"charttype","column"}})',
            ),
            self._cell_value(sheet_id, "A34", "Pemasukan Harian:"),
            self._cell_formula(
                sheet_id,
                "B34",
                f'=SPARKLINE(FILTER(transaksi!E:E,transaksi!C:C="income",transaksi!B:B>="{month_start}"),{{"charttype","column"}})',
            ),
        ]

    # ------------------------------------------------------------------
    # Premium: top 5 expenses with progress bars
    # ------------------------------------------------------------------
    def _top_expenses_table(self, sheet_id: int) -> list[dict]:
        return [
            self._cell_value(sheet_id, "A36", "TOP 5 PENGELUARAN", bold=True, font_size=12),
            self._cell_value(sheet_id, "A37", "Kategori"),
            self._cell_value(sheet_id, "B37", "Jumlah"),
            self._cell_value(sheet_id, "C37", "% dari Total"),
            self._cell_formula(
                sheet_id,
                "A38",
                "=QUERY(transaksi!A:G,\"SELECT D, SUM(E) WHERE C='expense' GROUP BY D ORDER BY SUM(E) DESC LIMIT 5 LABEL SUM(E) ''\",1)",
            ),
            self._cell_formula(sheet_id, "C38", "=B38/SUM($B$38:$B$42)"),
            self._cell_formula(sheet_id, "C39", "=B39/SUM($B$38:$B$42)"),
            self._cell_formula(sheet_id, "C40", "=B40/SUM($B$38:$B$42)"),
            self._cell_formula(sheet_id, "C41", "=B41/SUM($B$38:$B$42)"),
            self._cell_formula(sheet_id, "C42", "=B42/SUM($B$38:$B$42)"),
        ]

    # ------------------------------------------------------------------
    # Conditional formatting & protection
    # ------------------------------------------------------------------
    def _conditional_formatting(self, sheet_id: int) -> list[dict]:
        return [
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": 22,
                                "endRowIndex": 28,
                                "startColumnIndex": 1,
                                "endColumnIndex": 2,
                            }
                        ],
                        "gradientRule": {
                            "minpoint": {"color": {"green": 0.8, "red": 0.3, "blue": 0.3}, "type": "MIN"},
                            "maxpoint": {"color": {"green": 0.3, "red": 0.8, "blue": 0.3}, "type": "MAX"},
                        },
                    },
                    "index": 0,
                }
            }
        ]

    def _protect_ranges(self, sheet_id: int, is_premium: bool) -> list[dict]:
        ranges = [
            {
                "sheetId": sheet_id,
                "startRowIndex": 3,
                "endRowIndex": 8,
                "startColumnIndex": 0,
                "endColumnIndex": 2,
            }
        ]
        if is_premium:
            ranges.extend(
                [
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 10,
                        "endRowIndex": 20,
                        "startColumnIndex": 0,
                        "endColumnIndex": 2,
                    },
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 22,
                        "endRowIndex": 30,
                        "startColumnIndex": 0,
                        "endColumnIndex": 2,
                    },
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 32,
                        "endRowIndex": 35,
                        "startColumnIndex": 0,
                        "endColumnIndex": 2,
                    },
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": 36,
                        "endRowIndex": 43,
                        "startColumnIndex": 0,
                        "endColumnIndex": 3,
                    },
                ]
            )
        return [
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": r,
                        "description": "Formula cells - jangan diubah manual",
                        "warningOnly": True,
                    }
                }
            }
            for r in ranges
        ]

    # ------------------------------------------------------------------
    # Utility builders
    # ------------------------------------------------------------------
    def _cell_value(
        self,
        sheet_id: int,
        a1: str,
        value: str,
        bold: bool = False,
        font_size: int = 10,
    ) -> dict:
        grid = self._a1_to_grid_range(sheet_id, a1)
        return {
            "updateCells": {
                "range": grid,
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": str(value)},
                                "userEnteredFormat": {
                                    "textFormat": {"bold": bold, "fontSize": font_size}
                                },
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue,userEnteredFormat.textFormat",
            }
        }

    def _cell_formula(
        self, sheet_id: int, a1: str, formula: str, bold: bool = False
    ) -> dict:
        grid = self._a1_to_grid_range(sheet_id, a1)
        return {
            "updateCells": {
                "range": grid,
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"formulaValue": formula},
                                "userEnteredFormat": {"textFormat": {"bold": bold}},
                            }
                        ]
                    }
                ],
                "fields": "userEnteredValue,userEnteredFormat.textFormat",
            }
        }

    def _a1_to_grid_range(self, sheet_id: int, a1: str) -> dict:
        """Convert A1 notation like 'A12' or 'B5' to GridRange dict."""
        match = re.match(r"^([A-Z]+)(\d+)$", a1)
        if not match:
            raise ValueError(f"Unsupported A1 notation: {a1}")
        col_letters, row = match.groups()
        col_index = 0
        for ch in col_letters:
            col_index = col_index * 26 + (ord(ch) - ord("A") + 1)
        row_index = int(row) - 1
        return {
            "sheetId": sheet_id,
            "startRowIndex": row_index,
            "endRowIndex": row_index + 1,
            "startColumnIndex": col_index - 1,
            "endColumnIndex": col_index,
        }
