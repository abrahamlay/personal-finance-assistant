"""Google Sheets client with per-user OAuth authentication, retry logic, and error handling."""
import time
import logging
from functools import wraps
import gspread
from google.oauth2.credentials import Credentials
from src.auth.oauth import OAuthManager
from src.auth.token_store import TokenStore

logger = logging.getLogger(__name__)


class SheetNotFoundError(Exception):
    """User's spreadsheet not found (deleted or never created)."""
    pass

class SheetAuthError(Exception):
    """OAuth token invalid or expired beyond refresh."""
    pass


def retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=8.0):
    """Exponential backoff decorator for Google Sheets API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    code = getattr(e, 'code', 0)
                    if code in (429, 503, 500) and attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"API error {code}, retrying in {delay}s (attempt {attempt+1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    raise
                except Exception:
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        time.sleep(delay)
                        continue
                    raise
            raise last_exception
        return wrapper
    return decorator


class SheetsClient:
    """Per-user Google Sheets client authenticated via stored OAuth tokens."""
    
    def __init__(self, oauth_manager: OAuthManager, token_store: TokenStore):
        self.oauth_manager = oauth_manager
        self.token_store = token_store
        self._clients: dict[str, gspread.Client] = {}
    
    def authenticate(self, telegram_id: str) -> gspread.Client:
        """Get or create authenticated gspread client for a user."""
        if telegram_id in self._clients:
            return self._clients[telegram_id]
        
        credentials = self.oauth_manager.get_valid_credentials(telegram_id)
        if not credentials:
            raise SheetAuthError(f"No valid credentials for user {telegram_id}")
        
        client = gspread.authorize(credentials)
        self._clients[telegram_id] = client
        return client
    
    @retry_with_backoff(max_retries=3)
    def read_range(self, telegram_id: str, spreadsheet_id: str, range_spec: str) -> list[list[str]]:
        """Read a range of cells. range_spec like 'transaksi!A2:G'"""
        client = self.authenticate(telegram_id)
        try:
            sheet = client.open_by_key(spreadsheet_id)
            worksheet = sheet.worksheet(range_spec.split("!")[0])
            start = range_spec.split("!")[1] if "!" in range_spec else "A1"
            return worksheet.get(start)
        except gspread.exceptions.SpreadsheetNotFound:
            raise SheetNotFoundError(f"Spreadsheet {spreadsheet_id} not found")
    
    @retry_with_backoff(max_retries=3)
    def read_all_rows(self, telegram_id: str, spreadsheet_id: str, tab: str) -> list[list[str]]:
        """Read all rows from a tab (skipping header)."""
        client = self.authenticate(telegram_id)
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(tab)
        all_data = worksheet.get_all_values()
        return all_data[1:] if all_data else []  # skip header row
    
    @retry_with_backoff(max_retries=3)
    def append_row(self, telegram_id: str, spreadsheet_id: str, tab: str, values: list[str]) -> int:
        """Append a single row. Returns the new row number."""
        client = self.authenticate(telegram_id)
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(tab)
        worksheet.append_row(values, value_input_option="USER_ENTERED")
        return worksheet.row_count
    
    @retry_with_backoff(max_retries=3)
    def update_cell(self, telegram_id: str, spreadsheet_id: str, tab: str, row: int, col: int, value: str):
        """Update a specific cell."""
        client = self.authenticate(telegram_id)
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(tab)
        worksheet.update_cell(row, col, value)
    
    @retry_with_backoff(max_retries=3)
    def batch_update(self, telegram_id: str, spreadsheet_id: str, requests: list[dict]):
        """Execute batch update using Google Sheets API v4."""
        client = self.authenticate(telegram_id)
        # Use the underlying googleapiclient
        from googleapiclient.discovery import build
        credentials = self.oauth_manager.get_valid_credentials(telegram_id)
        service = build("sheets", "v4", credentials=credentials)
        body = {"requests": requests}
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    
    def clear_client_cache(self, telegram_id: str):
        """Remove cached client (e.g., after token refresh failure)."""
        self._clients.pop(telegram_id, None)
