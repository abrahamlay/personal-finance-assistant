# Task Plan: Personal Finance Recap Assistant (Telegram Bot)

**Spec:** `.openspec/telegram-finance-assistant.md`
**Plan ID:** `telegram-finance-assistant-2026-06`
**Generated:** 2026-06-21
**GSD Config:** maxParallel=2, taskTimeout=1800s, atomic commits

---

## Requirement Traceability Matrix

| Req | Description | Tasks | Wave |
|-----|-------------|-------|------|
| R1 | NL Transaction Logging | 4.1, 4.2 | 4 |
| R2 | Slash Command System | 3.1, 3.2, 5.1, 5.2, 6.1, 6.2, 7.2 | 3-7 |
| R3 | Category Management | 5.1 | 5 |
| R4 | Budget Tracking & Alerts | 5.2 | 5 |
| R5 | Reports & Analytics | 6.1 | 6 |
| R6 | Multi-User Isolation | 1.1, 2.1 | 1-2 |
| R7 | Onboarding Experience | 3.2 | 3 |
| R8 | Error Handling & Resilience | 9.1 | 9 |
| R9 | Google OAuth Authentication | 1.2, 2.1 | 1-2 |
| R10 | Google Sheets Dashboard | 6.2 | 6 |
| R11 | Premium Tier & Monetization | 7.1, 7.2 | 7 |
| R12 | OCR Receipt Scanner | 8.1 | 8 |
| R13 | Recurring Transactions | 8.2 | 8 |

---

## Dependency Graph (ASCII)

```
Wave 0: [0.1] [0.2]
           │     │
Wave 1: [1.1] [1.2]
           │     │
Wave 2: [2.1] [2.2]
           │     │
Wave 3: [3.1] [3.2]
           │     │
Wave 4: [4.1] [4.2]
           │     │
Wave 5: [5.1] [5.2]
           │     │
Wave 6: [6.1] [6.2]
           │     │
Wave 7: [7.1] [7.2]
           │     │
Wave 8: [8.1] [8.2]
           │     │
Wave 9: [9.1] [9.2]
           │     │
Wave 10:[10.1][10.2]
```

Cross-wave dependencies:
- 1.2 depends on 0.2 (needs Google Cloud credentials)
- 2.1 depends on 1.1 + 1.2 (needs config + OAuth)
- 2.2 depends on 2.1 (needs sheets client)
- 3.1 depends on 1.1 + 1.2 + 2.1 (needs all infra)
- 3.2 depends on 3.1 + 2.2 (needs bot + sheet setup)
- 4.1 depends on nothing beyond Python (pure logic)
- 4.2 depends on 4.1 + 2.1 + 2.2 (parser + sheets)
- 5.1 depends on 2.2 (sheets categories tab)
- 5.2 depends on 5.1 + 4.2 (categories + transactions)
- 6.1 depends on 4.2 + 5.1 (transactions + categories data)
- 6.2 depends on 2.1 + 4.2 (sheets API + transaction data)
- 7.1 depends on 1.1 (SQLite for subscriptions)
- 7.2 depends on 7.1 + 3.1 (subscription service + bot handlers)
- 8.1 depends on 7.1 + 4.2 (premium gate + transaction service)
- 8.2 depends on 7.1 + 4.2 + 3.1 (premium gate + transactions + bot)
- 9.1 depends on all waves 1-8 (error handling wraps everything)
- 9.2 depends on 7.1 + 4.2 (premium gate + transactions)
- 10.1 depends on all waves 1-9 (tests cover everything)
- 10.2 depends on 10.1 (docs reference test results)

---

## Wave 0: Project Scaffolding
**Estimated time:** 30 minutes
**Goal:** Bootable Python project with all dependencies and external accounts ready.

---

### Task 0.1: Python Project Init + Directory Structure (Priority: P0)
**Depends on:** None
**Files to create/modify:**
- `pyproject.toml` (create) — Python 3.12+, all dependencies
- `requirements.txt` (create) — pip-compatible lock
- `src/__init__.py` (create)
- `src/bot.py` (create) — empty placeholder
- `src/config.py` (create) — empty placeholder
- `src/handlers/__init__.py` (create)
- `src/services/__init__.py` (create)
- `src/sheets/__init__.py` (create)
- `src/auth/__init__.py` (create)
- `src/payments/__init__.py` (create)
- `src/middleware/__init__.py` (create)
- `src/cache/__init__.py` (create)
- `static/login.html` (create) — empty placeholder
- `tests/__init__.py` (create)
- `tests/conftest.py` (create) — pytest fixtures skeleton
- `.env.example` (create) — all required env vars documented
- `.gitignore` (create) — Python, venv, .env, *.db, __pycache__
- `README.md` (create) — minimal placeholder

**Dependencies (pyproject.toml):**
```
python-telegram-bot[job-queue,webhooks]>=21.0,<22.0
gspread>=6.0,<7.0
google-auth-oauthlib>=1.2,<2.0
google-api-python-client>=2.0,<3.0
cryptography>=42.0,<43.0
aiohttp>=3.9,<4.0
pydantic-settings>=2.0,<3.0
matplotlib>=3.9,<4.0
midtransclient>=1.0,<2.0
google-genai>=1.0,<2.0
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
```

**TDD:**
- N/A (scaffolding only — no logic to test)

**Commands to verify:**
```bash
python -m venv .venv
pip install -e ".[dev]"
python -c "import telegram; print(telegram.__version__)"
pytest --collect-only
```

**Acceptance Criteria:**
- [ ] `python -c "import telegram"` succeeds
- [ ] All directories exist with `__init__.py`
- [ ] `.env.example` lists: TELEGRAM_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, FERNET_KEY, MIDTRANS_SERVER_KEY, MIDTRANS_CLIENT_KEY, GEMINI_API_KEY, WEBHOOK_URL, OAUTH_REDIRECT_URI
- [ ] `pytest --collect-only` runs without import errors
- [ ] `.gitignore` covers .env, *.db, __pycache__, .venv/

---

### Task 0.2: External Service Accounts Setup (Priority: P0)
**Depends on:** None
**Files to create/modify:**
- `docs/setup-guide.md` (create) — step-by-step for each service

**Manual steps (not automatable):**

1. **Google Cloud Console:**
   - Create project "personal-finance-bot"
   - Enable Google Sheets API + Google Drive API
   - Configure OAuth consent screen (External, test mode)
   - Create OAuth 2.0 Client ID (Web application)
   - Add redirect URI: `https://<your-domain>/oauth/callback`
   - Download `client_secret.json` → extract CLIENT_ID + CLIENT_SECRET

2. **Telegram @BotFather:**
   - `/newbot` → name: "Asisten Keuangan" → username: `personal_finance_assistant_bot`
   - Save bot token
   - `/setcommands` → paste command list from spec
   - Enable payments: `/mybots` → select bot → Payments → enable

3. **Midtrans Sandbox:**
   - Register at dashboard.sandbox.midtrans.com
   - Create project → get Server Key + Client Key
   - Configure webhook URL: `https://<your-domain>/payments/midtrans/webhook`

4. **Gemini API:**
   - Get API key from aistudio.google.com
   - Verify access to `gemini-2.0-flash-001`

**Commands to verify:**
```bash
# Test Telegram bot token
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/getMe"

# Test Google OAuth (manual browser test)
# Test Midtrans sandbox
curl -X GET "https://api.sandbox.midtrans.com/v2/health" \
  -H "Authorization: Basic <base64_server_key>"
```

**Acceptance Criteria:**
- [ ] Google Cloud project created with Sheets + Drive APIs enabled
- [ ] OAuth 2.0 Client ID created with redirect URI configured
- [ ] Telegram bot created and token saved
- [ ] Midtrans sandbox account active with server key
- [ ] Gemini API key obtained and verified
- [ ] All credentials documented in `.env` (local, not committed)

---

## Wave 1: Core Infrastructure
**Estimated time:** 2 hours
**Goal:** Config management, encrypted SQLite token store, and OAuth web server operational.

---

### Task 1.1: Config + SQLite Token Store + Encryption (Priority: P0)
**Depends on:** Task 0.1
**Files to create/modify:**
- `src/config.py` (create) — pydantic-settings model with all env vars
- `src/auth/token_store.py` (create) — SQLite manager: user_tokens, subscriptions, invoices tables
- `src/auth/encryption.py` (create) — Fernet encrypt/decrypt for refresh tokens
- `src/auth/__init__.py` (modify) — export public API
- `tests/test_config.py` (create) — config loading tests
- `tests/test_token_store.py` (create) — CRUD tests for all 3 tables
- `tests/test_encryption.py` (create) — round-trip encrypt/decrypt tests

**TDD:**
- RED: Write test `test_encrypt_decrypt_roundtrip` → fails (no implementation)
- GREEN: Implement `encrypt_token()` and `decrypt_token()` using Fernet → passes
- RED: Write test `test_token_store_create_and_get` → fails
- GREEN: Implement `TokenStore.create_user_token()`, `get_user_token()` → passes
- RED: Write test `test_subscription_state_transitions` → fails
- GREEN: Implement `TokenStore.create_subscription()`, `update_subscription_status()` → passes
- RED: Write test `test_invoice_create_and_lookup` → fails
- GREEN: Implement `TokenStore.create_invoice()`, `get_invoices_by_user()` → passes
- REFACTOR: Extract SQL queries to constants; add connection pooling context manager

**Commands to verify:**
```bash
pytest tests/test_config.py tests/test_token_store.py tests/test_encryption.py -v --cov=src/auth --cov-report=term-missing
```

**Acceptance Criteria:**
- [ ] `Settings` class loads all env vars with validation (pydantic-settings)
- [ ] SQLite auto-creates `token_store.db` on first run with 3 tables (user_tokens, subscriptions, invoices)
- [ ] Fernet encryption round-trip: encrypt → decrypt returns original
- [ ] Token store CRUD: create, read, update, delete for user_tokens
- [ ] Subscription table enforces CHECK constraints (plan, status enums)
- [ ] Invoice table stores raw_response JSON for debugging
- [ ] Test coverage ≥80% on `src/auth/` and `src/config.py`
- [ ] All tests pass: `pytest tests/test_config.py tests/test_token_store.py tests/test_encryption.py -v`

---

### Task 1.2: OAuth Flow + aiohttp Web Server (Priority: P0)
**Depends on:** Task 0.1, Task 0.2
**Files to create/modify:**
- `src/web_server.py` (create) — aiohttp app with routes: `/oauth/callback`, `/payments/midtrans/webhook`, `/login` (WebApp HTML)
- `src/auth/oauth.py` (create) — Google OAuth flow: generate auth URL, exchange code for tokens, refresh tokens
- `static/login.html` (create) — Telegram WebApp HTML: opens Google OAuth, auto-callback via `Telegram.WebApp.sendData()`
- `tests/test_oauth.py` (create) — mock Google OAuth exchange, test token refresh
- `tests/test_web_server.py` (create) — aiohttp test client for route handlers

**TDD:**
- RED: Write test `test_generate_auth_url_contains_scope` → fails
- GREEN: Implement `OAuthManager.get_authorization_url()` with `drive.file` scope → passes
- RED: Write test `test_exchange_code_returns_tokens` → fails (mock google-auth-oauthlib)
- GREEN: Implement `OAuthManager.exchange_code()` → passes
- RED: Write test `test_refresh_token_returns_new_access` → fails
- GREEN: Implement `OAuthManager.refresh_token()` → passes
- RED: Write test `test_oauth_callback_route_stores_token` → fails
- GREEN: Implement `/oauth/callback` route handler → passes
- RED: Write test `test_webapp_login_page_returns_html` → fails
- GREEN: Implement `/login` route serving `static/login.html` → passes
- REFACTOR: Extract OAuth state parameter generation; add CSRF state validation

**Commands to verify:**
```bash
pytest tests/test_oauth.py tests/test_web_server.py -v --cov=src/auth/oauth.py --cov=src/web_server.py
```

**Acceptance Criteria:**
- [ ] `OAuthManager.get_authorization_url()` returns valid Google OAuth URL with `drive.file` scope
- [ ] `OAuthManager.exchange_code(code)` returns `{access_token, refresh_token, expiry}`
- [ ] `OAuthManager.refresh_token(refresh_token)` returns new access token
- [ ] `/oauth/callback` route: receives code, exchanges for tokens, stores in SQLite, redirects to success page
- [ ] `/login` serves WebApp HTML that opens Google OAuth in WebView
- [ ] WebApp HTML uses `Telegram.WebApp.sendData()` for auto-callback to bot
- [ ] Fallback: copy-paste code flow works if WebApp fails
- [ ] CSRF state parameter validated on callback
- [ ] Test coverage ≥80% on `src/auth/oauth.py` and `src/web_server.py`

---

## Wave 2: Google Sheets Integration
**Estimated time:** 2 hours
**Goal:** Per-user Google Sheets CRUD operational with retry logic.

---

### Task 2.1: Google Sheets Client with Per-User OAuth (Priority: P0)
**Depends on:** Task 1.1, Task 1.2
**Files to create/modify:**
- `src/sheets/client.py` (create) — `SheetsClient` class: authenticate per-user, read/write cells, batch operations
- `src/sheets/__init__.py` (modify) — export SheetsClient
- `tests/test_sheets_client.py` (create) — mock gspread, test auth + CRUD operations

**TDD:**
- RED: Write test `test_authenticate_with_user_token` → fails
- GREEN: Implement `SheetsClient.authenticate(telegram_id)` using stored OAuth credentials → passes
- RED: Write test `test_read_range_returns_list` → fails
- GREEN: Implement `SheetsClient.read_range(sheet_id, tab, range)` → passes
- RED: Write test `test_append_row_adds_data` → fails
- GREEN: Implement `SheetsClient.append_row(sheet_id, tab, values)` → passes
- RED: Write test `test_retry_on_429_error` → fails
- GREEN: Implement exponential backoff decorator `@retry_with_backoff(max_retries=3)` → passes
- RED: Write test `test_handle_token_expired_triggers_refresh` → fails
- GREEN: Implement auto-refresh on 401 → passes
- REFACTOR: Extract retry logic to reusable decorator; add logging for all API calls

**Commands to verify:**
```bash
pytest tests/test_sheets_client.py -v --cov=src/sheets/client.py
```

**Acceptance Criteria:**
- [ ] `SheetsClient.authenticate(telegram_id)` loads encrypted refresh token, decrypts, creates gspread client
- [ ] Read/write/batch operations work on user's spreadsheet
- [ ] Exponential backoff on 429 (rate limit) and 503 (service unavailable): 1s, 2s, 4s delays
- [ ] Auto-refresh on 401 (token expired): refresh token, retry original request
- [ ] Graceful error on 404 (sheet deleted): returns specific `SheetNotFoundError`
- [ ] All operations log: operation type, sheet_id, tab, latency
- [ ] Test coverage ≥80%

---

### Task 2.2: Sheet Setup Service — Create Spreadsheet + 5 Tabs (Priority: P0)
**Depends on:** Task 2.1
**Files to create/modify:**
- `src/sheets/setup.py` (create) — `SheetSetupService`: create spreadsheet, create 5 tabs, preload default categories, set config
- `tests/test_sheet_setup.py` (create) — test spreadsheet creation, tab structure, default data

**TDD:**
- RED: Write test `test_create_spreadsheet_returns_id` → fails
- GREEN: Implement `SheetSetupService.create_spreadsheet(telegram_id, name)` → passes
- RED: Write test `test_create_tabs_creates_5_tabs` → fails
- GREEN: Implement `SheetSetupService.create_tabs(spreadsheet_id)` — creates: transaksi, kategori, anggaran, config, Dashboard → passes
- RED: Write test `test_preload_default_categories_writes_13_rows` → fails
- GREEN: Implement `SheetSetupService.preload_categories(spreadsheet_id)` — writes 13 default categories → passes
- RED: Write test `test_initialize_config_tab_writes_user_info` → fails
- GREEN: Implement `SheetSetupService.initialize_config(spreadsheet_id, user_info)` → passes
- REFACTOR: Combine into single `setup_new_user(telegram_id, name)` method; add idempotency check

**Default 13 categories:**
```
Makanan, Transportasi, Belanja, Tagihan, Kesehatan, Hiburan, Pendidikan, Gaji, Investasi, Hadiah, Donasi, Liburan, Lainnya
```

**Tab structure:**
| Tab | Headers |
|-----|---------|
| transaksi | id, tanggal, tipe, kategori, jumlah, deskripsi, created_at |
| kategori | id, nama, tipe, is_default, icon |
| anggaran | id, kategori, jumlah_bulan, bulan, terpakai |
| config | key, value |
| Dashboard | (formulas + charts, generated by Task 6.2) |

**Commands to verify:**
```bash
pytest tests/test_sheet_setup.py -v --cov=src/sheets/setup.py
```

**Acceptance Criteria:**
- [ ] `setup_new_user(telegram_id, name)` creates spreadsheet titled "KeuanganBot - {name}"
- [ ] 5 tabs created with correct headers
- [ ] 13 default categories preloaded in `kategori` tab
- [ ] Config tab populated: telegram_id, first_name, language=id, join_date, premium_status=free
- [ ] Spreadsheet ID stored in SQLite `user_tokens` table
- [ ] Operation is idempotent: calling twice doesn't create duplicate sheets
- [ ] Test coverage ≥80%

---

## Wave 3: Bot Skeleton + Onboarding
**Estimated time:** 2.5 hours
**Goal:** Bot responds to /start, runs onboarding wizard, handles /login and /logout.

---

### Task 3.1: Bot Entry Point + Command Router + Auth Handlers (Priority: P0)
**Depends on:** Task 1.1, Task 1.2, Task 2.1
**Files to create/modify:**
- `src/bot.py` (create) — PTB Application builder, handler registration, job queue setup, web server co-run
- `src/handlers/commands.py` (create) — /start, /bantuan, /export stubs
- `src/handlers/auth.py` (create) — /login (sends WebApp button), /logout (revoke + cleanup)
- `src/handlers/__init__.py` (modify) — export handlers
- `src/cache/memory_cache.py` (create) — in-memory dict for dedup + daily totals
- `tests/test_bot.py` (create) — PTB test client, test handler registration
- `tests/test_auth_handlers.py` (create) — test /login sends WebApp button, /logout revokes token

**TDD:**
- RED: Write test `test_bot_starts_without_errors` → fails
- GREEN: Implement `build_bot()` using `Application.builder().token(TOKEN).build()` → passes
- RED: Write test `test_start_command_sends_welcome` → fails
- GREEN: Implement `/start` handler → passes
- RED: Write test `test_login_sends_webapp_button` → fails
- GREEN: Implement `/login` handler with `InlineKeyboardButton(web_app=WebAppInfo(url=...))` → passes
- RED: Write test `test_logout_revokes_and_clears` → fails
- GREEN: Implement `/logout` handler: revoke Google token, delete SQLite mapping, confirm → passes
- RED: Write test `test_bantuan_lists_commands` → fails
- GREEN: Implement `/bantuan` handler with categorized command list → passes
- REFACTOR: Extract common "require login" check into middleware function

**Commands to verify:**
```bash
pytest tests/test_bot.py tests/test_auth_handlers.py -v
# Manual: run bot locally, test /start /login /logout in Telegram
python -m src.bot
```

**Acceptance Criteria:**
- [ ] `python -m src.bot` starts without errors, bot responds to /start
- [ ] /start sends welcome message with inline button
- [ ] /login sends inline keyboard with "Login Google" WebApp button
- [ ] /logout revokes Google OAuth token, deletes SQLite mapping, confirms to user
- [ ] /bantuan lists all commands with descriptions in Bahasa Indonesia
- [ ] Bot handles unknown commands gracefully: "Command tidak dikenali. Ketik /bantuan"
- [ ] Memory cache initialized (empty dict)
- [ ] Web server (aiohttp) runs alongside bot polling

---

### Task 3.2: Onboarding Wizard ConversationHandler (Priority: P1)
**Depends on:** Task 3.1, Task 2.2
**Files to create/modify:**
- `src/handlers/onboarding.py` (create) — 4-step ConversationHandler: nama → Google OAuth → selesai → tutorial
- `tests/test_onboarding.py` (create) — test each wizard step, test skip paths, test timeout

**TDD:**
- RED: Write test `test_step1_asks_name` → fails
- GREEN: Implement step 1: ask name with skip button → passes
- RED: Write test `test_step2_sends_login_button` → fails
- GREEN: Implement step 2: send Google OAuth WebApp button + offline mode fallback → passes
- RED: Write test `test_step3_confirms_setup_and_offers_trial` → fails
- GREEN: Implement step 3: confirm sheet creation, offer 7-day free trial → passes
- RED: Write test `test_step4_shows_quick_tutorial` → fails
- GREEN: Implement step 4: quick tutorial message + "Coba catat transaksi pertama" button → passes
- RED: Write test `test_skip_name_uses_telegram_first_name` → fails
- GREEN: Handle skip: use `update.effective_user.first_name` → passes
- RED: Write test `test_offline_mode_skips_oauth` → fails
- GREEN: Handle offline mode: skip OAuth, use local-only mode → passes
- RED: Write test `test_trial_activation_creates_subscription` → fails
- GREEN: Wire trial button to `SubscriptionService.start_free_trial()` → passes
- REFACTOR: Extract wizard state management; add timeout handler (cancel after 10 min inactivity)

**Wizard flow:**
```
Step 1 (NAME): "Siapa nama panggilan kamu?" → [text input] [Skip]
Step 2 (AUTH): "Data kamu aman di Google Sheet milikmu." → [Login Google] [Mode Offline]
Step 3 (DONE): "Login berhasil! Sheet siap." → [Coba Premium Gratis] [Nanti Aja]
Step 4 (TUTORIAL): Quick tutorial + "Coba catat transaksi pertama"
```

**Commands to verify:**
```bash
pytest tests/test_onboarding.py -v --cov=src/handlers/onboarding.py
# Manual: /start → complete wizard in Telegram
```

**Acceptance Criteria:**
- [ ] /start triggers 4-step wizard
- [ ] Step 1: asks name, skip uses Telegram first_name
- [ ] Step 2: sends WebApp login button + offline mode option
- [ ] Step 3: confirms setup, offers 7-day trial (creates trial subscription in SQLite)
- [ ] Step 4: shows quick tutorial with example transactions
- [ ] Total wizard time <120 seconds for typical user
- [ ] Wizard timeout (10 min inactivity) cancels gracefully
- [ ] User who already completed onboarding gets "Kamu sudah setup! Ketik /bantuan" on /start
- [ ] Test coverage ≥80%

---

## Wave 4: Transaction Core
**Estimated time:** 3 hours
**Goal:** Users can log transactions via natural language and slash commands. This is the MVP core.

---

### Task 4.1: Natural Language Message Parser (Priority: P0)
**Depends on:** Task 0.1
**Files to create/modify:**
- `src/services/parser_service.py` (create) — NL text → structured transaction: amount extraction, category matching, date parsing, multi-transaction splitting
- `tests/test_parser.py` (create) — comprehensive test suite (50+ test cases)

**Parser design (from spec Appendix A):**

1. **Amount normalization:** regex patterns for Indonesian number formats
   - `50rb`, `50.000`, `50000`, `50k`, `5jt`, `5.000.000`, `5 juta`
   - All normalized to integer (Rupiah)

2. **Category keyword matching:** dictionary of keywords → category
   - "makan", "nasi", "resto" → Makanan
   - "bensin", "parkir", "ojek" → Transportasi
   - "belanja", "supermarket", "indomaret" → Belanja
   - etc.

3. **Date extraction:** relative date keywords
   - "kemarin" → yesterday
   - "hari ini" → today (default)
   - "besok" → tomorrow
   - "tanggal 15" → specific date this month

4. **Multi-transaction splitting:** comma or newline separated
   - "pulsa 100k, bensin 80rb" → 2 transactions

5. **Type detection:** income vs expense keywords
   - "gaji", "dapat", "terima" → income
   - default → expense

**TDD:**
- RED: Write test `test_parse_simple_expense` — "makan siang 50rb" → {category: "Makanan", amount: 50000, type: "expense"} → fails
- GREEN: Implement basic regex parser → passes
- RED: Write test `test_parse_amount_formats` — all 8 amount formats → fails
- GREEN: Add amount normalization regex → passes
- RED: Write test `test_parse_income` — "gaji 5jt" → {category: "Gaji", amount: 5000000, type: "income"} → fails
- GREEN: Add income keyword detection → passes
- RED: Write test `test_parse_date_override` — "kemarin makan siang 50rb" → date=yesterday → fails
- GREEN: Add date extraction → passes
- RED: Write test `test_parse_multi_transaction` — "pulsa 100k, bensin 80rb" → 2 results → fails
- GREEN: Add comma/newline splitting → passes
- RED: Write test `test_parse_ambiguous_category` — "something 50rb" → category=None, prompt user → fails
- GREEN: Return `category=None` for unmatched → passes
- RED: Write test `test_parse_category_collision` — text matches 2 categories → both returned → fails
- GREEN: Return list of candidates for collision → passes
- RED: Write test `test_parse_edge_case_no_amount` — "makan siang" → error: no amount found → fails
- GREEN: Return structured error → passes
- RED: Write 30+ additional edge case tests (multi-line, mixed formats, emoji, etc.)
- GREEN: Fix all edge cases → passes
- REFACTOR: Extract regex patterns to constants; add parser confidence scoring

**Test cases (minimum 50):**
```
# Basic
"makan siang 50rb" → Makanan, 50000, expense
"gaji 5jt" → Gaji, 5000000, income
"belanja 100.000" → Belanja, 100000, expense

# Amount formats
"50rb" → 50000
"50.000" → 50000
"50000" → 50000
"50k" → 50000
"5jt" → 5000000
"5.000.000" → 5000000
"5 juta" → 5000000
"1,5jt" → 1500000

# Date overrides
"kemarin makan 50rb" → date=yesterday
"besok bayar listrik 200rb" → date=tomorrow
"tanggal 15 sewa 2jt" → date=15th of month

# Multi-transaction
"pulsa 100k, bensin 80rb" → 2 transactions
"makan 30rb\ntransport 20rb" → 2 transactions

# Edge cases
"makan siang" → error: no amount
"50rb" → error: no category (prompt user)
"" → error: empty input
"transfer ke budi 500rb" → Transfer, 500000, expense
```

**Commands to verify:**
```bash
pytest tests/test_parser.py -v --cov=src/services/parser_service.py --cov-report=term-missing
```

**Acceptance Criteria:**
- [ ] Parses "makan siang 50rb" → {Makanan, 50000, expense, today}
- [ ] Parses "gaji 5jt" → {Gaji, 5000000, income, today}
- [ ] Parses "pulsa 100k, bensin 80rb" → 2 transactions
- [ ] Handles all 8 amount formats correctly
- [ ] Date override: "kemarin", "besok", "tanggal N"
- [ ] Ambiguous category → returns None, bot prompts user
- [ ] No amount found → returns structured error
- [ ] 50+ test cases all passing
- [ ] Test coverage ≥90% on parser (critical component)
- [ ] Parse latency <100ms per message

---

### Task 4.2: Transaction Service + CRUD + Commands (Priority: P0)
**Depends on:** Task 4.1, Task 2.1, Task 2.2
**Files to create/modify:**
- `src/services/transaction_service.py` (create) — CRUD: create, read, update, delete transactions; dedup; aggregation
- `src/sheets/transactions.py` (create) — Google Sheets read/write for transaksi tab
- `src/handlers/messages.py` (create) — natural language message handler (non-command text → parser → service)
- `src/handlers/commands.py` (modify) — add /catat (guided), /edit <id>, /hapus <id>, /hariini stub
- `tests/test_transaction_service.py` (create) — CRUD, dedup, aggregation tests
- `tests/test_sheets_transactions.py` (create) — mock sheets, test read/write
- `tests/test_message_handler.py` (create) — end-to-end: text → parser → service → response

**TDD:**
- RED: Write test `test_create_transaction_appends_to_sheet` → fails
- GREEN: Implement `TransactionService.create()` → calls `SheetsTransactions.append()` → passes
- RED: Write test `test_dedup_within_5min_window` → fails
- GREEN: Implement dedup: same amount + category within 5 min → skip with warning → passes
- RED: Write test `test_get_today_transactions` → fails
- GREEN: Implement `TransactionService.get_by_date_range()` → passes
- RED: Write test `test_update_transaction_modifies_row` → fails
- GREEN: Implement `TransactionService.update()` → passes
- RED: Write test `test_delete_transaction_removes_row` → fails
- GREEN: Implement `TransactionService.delete()` → passes
- RED: Write test `test_message_handler_parses_and_creates` → fails
- GREEN: Wire message handler: text → parser → service → confirmation reply → passes
- RED: Write test `test_catat_command_guided_flow` → fails
- GREEN: Implement /catat ConversationHandler: amount → category → description → confirm → passes
- RED: Write test `test_edit_command_updates` → fails
- GREEN: Implement /edit <id> handler → passes
- RED: Write test `test_hapus_command_deletes` → fails
- GREEN: Implement /hapus <id> handler → passes
- REFACTOR: Extract confirmation message formatting; add daily recap inline keyboard

**Transaction ID scheme:** Row number in sheet (e.g., row 5 = id 5). Displayed in confirmation: "ID: #5"

**Confirmation message format:**
```
✅ Tercatat: 🍔 Makanan — Rp 50.000
📊 Hari ini: Rp 150.000 (3 transaksi)
[#5] /edit_5 /hapus_5
```

**Commands to verify:**
```bash
pytest tests/test_transaction_service.py tests/test_sheets_transactions.py tests/test_message_handler.py -v --cov=src/services/transaction_service.py --cov=src/sheets/transactions.py --cov=src/handlers/messages.py
```

**Acceptance Criteria:**
- [ ] User types "makan siang 50rb" → transaction appears in sheet within 2 seconds
- [ ] Bot replies with confirmation: category, amount, daily total
- [ ] Dedup: same amount + category within 5 min → "Transaksi duplikat? [Ya, simpan] [Tidak]"
- [ ] /catat starts guided flow: amount → category (inline keyboard) → description → confirm
- [ ] /edit <id> updates transaction in sheet
- [ ] /hapus <id> deletes transaction from sheet
- [ ] Multi-transaction message: "pulsa 100k, bensin 80rb" → 2 confirmations
- [ ] Ambiguous parse → bot asks: "Kategori apa? [inline keyboard]"
- [ ] Test coverage ≥80%

---

## Wave 5: Categories & Budgets
**Estimated time:** 2 hours
**Goal:** Users can manage categories and set budgets with alerts.

---

### Task 5.1: Category Management (Priority: P0)
**Depends on:** Task 2.2
**Files to create/modify:**
- `src/sheets/categories.py` (create) — CRUD for kategori tab: list, add, rename, delete
- `src/handlers/categories.py` (create) — /kategori handler with inline keyboard UI
- `tests/test_sheets_categories.py` (create) — mock sheets, test category CRUD
- `tests/test_category_handler.py` (create) — test /kategori bot interactions

**TDD:**
- RED: Write test `test_list_categories_returns_13_defaults` → fails
- GREEN: Implement `SheetsCategories.list_all()` → passes
- RED: Write test `test_add_custom_category_appends_row` → fails
- GREEN: Implement `SheetsCategories.add(name, type, icon)` → passes
- RED: Write test `test_rename_category_updates_row` → fails
- GREEN: Implement `SheetsCategories.rename(id, new_name)` → passes
- RED: Write test `test_delete_default_category_blocked` → fails
- GREEN: Implement guard: `if is_default: raise CannotDeleteDefaultError` → passes
- RED: Write test `test_free_tier_max_5_custom_categories` → fails
- GREEN: Implement limit check: count custom categories, reject if ≥5 and free tier → passes
- RED: Write test `test_kategori_command_shows_inline_keyboard` → fails
- GREEN: Implement /kategori handler with inline keyboard: list + [Tambah] [Edit] [Hapus] → passes
- REFACTOR: Extract category validation; add icon picker

**Commands to verify:**
```bash
pytest tests/test_sheets_categories.py tests/test_category_handler.py -v
```

**Acceptance Criteria:**
- [ ] /kategori shows all 13 default categories + any custom ones
- [ ] User can add custom category (free: max 5, premium: unlimited)
- [ ] User can rename custom categories
- [ ] Default categories cannot be deleted or renamed
- [ ] Category names are denormalized in transactions (historical accuracy)
- [ ] Inline keyboard UI: [Tambah Kategori] [Edit] [Hapus]
- [ ] Free tier hitting 5 custom categories → "🔒 Max 5 kategori custom. Upgrade ke Premium untuk unlimited. /premium"
- [ ] Test coverage ≥80%

---

### Task 5.2: Budget Tracking & Alerts (Priority: P1)
**Depends on:** Task 5.1, Task 4.2
**Files to create/modify:**
- `src/services/budget_service.py` (create) — budget CRUD, usage calculation, warning thresholds
- `src/sheets/budgets.py` (create) — CRUD for anggaran tab
- `src/handlers/budgets.py` (create) — /anggaran handler with ConversationHandler
- `tests/test_budget_service.py` (create) — budget calc, warning threshold tests
- `tests/test_budget_handler.py` (create) — test /anggaran bot interactions

**TDD:**
- RED: Write test `test_set_monthly_budget` → fails
- GREEN: Implement `BudgetService.set_budget(category, amount, month)` → passes
- RED: Write test `test_calculate_usage_returns_percentage` → fails
- GREEN: Implement `BudgetService.get_usage(category, month)` → passes
- RED: Write test `test_warning_at_50_percent` → fails
- GREEN: Implement threshold check: 50%, 80%, 90%, 100% → passes
- RED: Write test `test_free_tier_one_budget_only` → fails
- GREEN: Implement: free tier = 1 total budget only; premium = unlimited + per-category → passes
- RED: Write test `test_anggaran_command_shows_current_budgets` → fails
- GREEN: Implement /anggaran handler: show current + [Set Budget] button → passes
- RED: Write test `test_budget_warning_message_format` → fails
- GREEN: Implement warning message: "⚠️ Budget Makanan 80% terpakai (Rp 400k / Rp 500k)" → passes
- REFACTOR: Extract budget period calculation; add monthly reset logic

**Warning thresholds:**
| Threshold | Message |
|-----------|---------|
| 50% | "💡 Budget {kategori} sudah 50% terpakai" |
| 80% | "⚠️ Budget {kategori} 80% terpakai. Hati-hati!" |
| 90% | "🔴 Budget {kategori} 90%! Sisa Rp {remaining}" |
| 100% | "🚨 Budget {kategori} HABIS! Over Rp {over}" |

**Commands to verify:**
```bash
pytest tests/test_budget_service.py tests/test_budget_handler.py -v --cov=src/services/budget_service.py --cov=src/sheets/budgets.py
```

**Acceptance Criteria:**
- [ ] /anggaran shows current budgets + usage percentages
- [ ] User can set budget via ConversationHandler: category → amount → confirm
- [ ] Free tier: 1 total monthly budget only
- [ ] Premium: unlimited budgets + per-category budgets
- [ ] Warnings triggered at 50%, 80%, 90%, 100% when transaction logged
- [ ] Budget resets monthly (new month = fresh calculation)
- [ ] Dashboard conditional formatting: red when over budget (implemented in Task 6.2)
- [ ] Test coverage ≥80%

---

## Wave 6: Reports & Dashboard
**Estimated time:** 3 hours
**Goal:** Users get text recaps and a Google Sheets Dashboard with native charts.

---

### Task 6.1: Report Service + Text Reports + matplotlib Charts (Priority: P0)
**Depends on:** Task 4.2, Task 5.1
**Files to create/modify:**
- `src/services/report_service.py` (create) — aggregation: daily/weekly/monthly summaries, category breakdown, top expenses
- `src/handlers/commands.py` (modify) — implement /hariini, /mingguan, /bulanan handlers
- `tests/test_report_service.py` (create) — aggregation logic tests
- `tests/test_report_handlers.py` (create) — test report command responses

**TDD:**
- RED: Write test `test_daily_summary_totals` → fails
- GREEN: Implement `ReportService.get_daily_summary(date)` → passes
- RED: Write test `test_weekly_summary_with_category_breakdown` → fails
- GREEN: Implement `ReportService.get_weekly_summary(week_start)` → passes
- RED: Write test `test_monthly_summary_with_comparison` → fails
- GREEN: Implement `ReportService.get_monthly_summary(month)` → passes
- RED: Write test `test_generate_bar_chart_png` → fails
- GREEN: Implement `ReportService.generate_chart_png(data, type='bar')` using matplotlib → passes
- RED: Write test `test_free_tier_3_month_history_limit` → fails
- GREEN: Implement: free tier reports limited to last 3 months; premium unlimited → passes
- RED: Write test `test_hariini_command_returns_text_recap` → fails
- GREEN: Implement /hariini handler → passes
- RED: Write test `test_mingguan_command_returns_text_plus_chart` → fails
- GREEN: Implement /mingguan: text recap + matplotlib bar chart PNG → passes
- RED: Write test `test_bulanan_command_returns_text_plus_dashboard_link` → fails
- GREEN: Implement /bulanan: text recap + link to Dashboard tab → passes
- REFACTOR: Extract report formatting; add caching for repeated queries

**Report format (example /hariini):**
```
📊 Rekap Hari Ini — 21 Juni 2026

💰 Pemasukan: Rp 0
💸 Pengeluaran: Rp 250.000 (5 transaksi)

Per kategori:
🍔 Makanan: Rp 85.000 (2x)
🚗 Transportasi: Rp 50.000 (1x)
🛒 Belanja: Rp 115.000 (2x)

📈 Saldo hari ini: -Rp 250.000
```

**Commands to verify:**
```bash
pytest tests/test_report_service.py tests/test_report_handlers.py -v --cov=src/services/report_service.py
```

**Acceptance Criteria:**
- [ ] /hariini returns text recap: income, expenses, category breakdown, saldo
- [ ] /mingguan returns text + bar chart PNG (matplotlib)
- [ ] /bulanan returns text + link to Dashboard tab
- [ ] Free tier: history limited to 3 months
- [ ] Premium: unlimited history
- [ ] Report responds <3 seconds for <1000 transactions
- [ ] Zero transactions → friendly message: "Belum ada transaksi hari ini. Coba catat: makan siang 50rb"
- [ ] Month-end rollover: on the 1st, show previous month summary
- [ ] Test coverage ≥80%

---

### Task 6.2: Dashboard Tab Generator — Sheets API v4 (Priority: P0)
**Depends on:** Task 2.1, Task 4.2
**Files to create/modify:**
- `src/sheets/dashboard.py` (create) — Dashboard generator: SUMIF formulas, native charts (pie, bar), sparklines, conditional formatting, protected ranges
- `src/handlers/commands.py` (modify) — implement /dashboard, /perbaiki handlers
- `tests/test_dashboard.py` (create) — test formula generation, chart creation, protected ranges

**TDD:**
- RED: Write test `test_generate_summary_formulas` → fails
- GREEN: Implement `DashboardGenerator.generate_summary_formulas()` — SUMIF for each category → passes
- RED: Write test `test_create_pie_chart_request` → fails
- GREEN: Implement `DashboardGenerator.create_pie_chart()` using Sheets API v4 `addChart` request → passes
- RED: Write test `test_create_bar_chart_6month_trend` → fails
- GREEN: Implement `DashboardGenerator.create_bar_chart()` → passes
- RED: Write test `test_apply_conditional_formatting` → fails
- GREEN: Implement `DashboardGenerator.apply_conditional_formatting()` — red for over budget → passes
- RED: Write test `test_protect_dashboard_ranges` → fails
- GREEN: Implement `DashboardGenerator.protect_ranges()` → passes
- RED: Write test `test_free_tier_basic_dashboard_only` → fails
- GREEN: Implement: free = SUMIF totals + saldo only; premium = full charts + sparklines + formatting → passes
- RED: Write test `test_perbaiki_regenerates_dashboard` → fails
- GREEN: Implement /perbaiki: clear Dashboard tab, regenerate all → passes
- RED: Write test `test_batch_update_sends_all_requests` → fails
- GREEN: Implement `DashboardGenerator.build_all()` → single `batchUpdate` call → passes
- REFACTOR: Extract chart config to constants; add chart quota check (max 20)

**Sheets API v4 batchUpdate requests:**
1. `updateCells` — write SUMIF/SUM formulas
2. `addChart` — pie chart (category breakdown)
3. `addChart` — bar chart (6-month trend)
4. `addConditionalFormatRule` — red for over budget
5. `addProtectedRange` — lock formula cells
6. `updateCells` — sparkline formulas (premium only)

**Commands to verify:**
```bash
pytest tests/test_dashboard.py -v --cov=src/sheets/dashboard.py
```

**Acceptance Criteria:**
- [ ] Dashboard tab auto-generated during user setup (basic for free, full for premium)
- [ ] Free tier: SUMIF totals + saldo display (no charts)
- [ ] Premium tier: Pie Chart + Bar Chart (6-month trend) + Sparklines + Conditional Formatting + Top 5
- [ ] Protected ranges prevent accidental formula edits
- [ ] /dashboard returns link to user's spreadsheet Dashboard tab
- [ ] /perbaiki clears and regenerates entire Dashboard
- [ ] Chart quota: max 20 charts; old charts removed before regeneration
- [ ] All operations in single `batchUpdate` call for atomicity
- [ ] Dashboard formula error → graceful message + suggest /perbaiki
- [ ] Test coverage ≥80%

---

## Wave 7: Premium System
**Estimated time:** 3 hours
**Goal:** Complete freemium model with payment processing and subscription management.

---

### Task 7.1: Subscription Service + Premium Gate Decorator (Priority: P1)
**Depends on:** Task 1.1
**Files to create/modify:**
- `src/services/subscription_service.py` (create) — state machine: NONE→PENDING→ACTIVE→GRACE→EXPIRED; trial management; auto-renew
- `src/middleware/premium_gate.py` (create) — `@premium_required(feature_name)` decorator
- `src/payments/models.py` (create) — Subscription, Invoice, Plan dataclasses
- `tests/test_subscription_service.py` (create) — state machine transitions, trial, expiry
- `tests/test_premium_gate.py` (create) — decorator blocks free users, allows premium

**TDD:**
- RED: Write test `test_state_transition_none_to_pending` → fails
- GREEN: Implement `SubscriptionService.create_subscription()` → passes
- RED: Write test `test_state_transition_pending_to_active` → fails
- GREEN: Implement `SubscriptionService.activate_subscription()` → passes
- RED: Write test `test_state_transition_active_to_grace` → fails
- GREEN: Implement `SubscriptionService.check_expiry()` → ACTIVE→GRACE after period ends → passes
- RED: Write test `test_state_transition_grace_to_expired_after_3_days` → fails
- GREEN: Implement grace period: 3 days then EXPIRED → passes
- RED: Write test `test_invalid_transition_raises` → fails
- GREEN: Implement transition validation: invalid → `InvalidStateTransitionError` → passes
- RED: Write test `test_start_free_trial_creates_7day_subscription` → fails
- GREEN: Implement `SubscriptionService.start_free_trial()` → passes
- RED: Write test `test_trial_abuse_one_per_telegram_id` → fails
- GREEN: Implement: check if trial ever used for this telegram_id → passes
- RED: Write test `test_premium_gate_blocks_free_user` → fails
- GREEN: Implement `@premium_required` decorator → free user gets "🔒 Fitur Premium" message → passes
- RED: Write test `test_premium_gate_allows_active_subscriber` → fails
- GREEN: Decorator passes through for active/trial subscribers → passes
- RED: Write test `test_lifetime_plan_never_expires` → fails
- GREEN: Implement: lifetime plan has `end_date=None`, never transitions to EXPIRED → passes
- REFACTOR: Extract state machine to enum; add logging for all transitions

**State machine (from spec E.3):**
```
NONE → PENDING (payment created)
PENDING → ACTIVE (payment success) | EXPIRED (>24h or cancelled)
ACTIVE → GRACE (period ended) | EXPIRED | CANCELLED (auto-renew off)
GRACE → ACTIVE (renewed) | EXPIRED (>3 days)
EXPIRED → PENDING (re-subscribe)
CANCELLED → PENDING (re-subscribe)
```

**Commands to verify:**
```bash
pytest tests/test_subscription_service.py tests/test_premium_gate.py -v --cov=src/services/subscription_service.py --cov=src/middleware/premium_gate.py
```

**Acceptance Criteria:**
- [ ] State machine enforces valid transitions only
- [ ] `@premium_required("Feature Name")` decorator blocks free users with upgrade message + inline keyboard
- [ ] Decorator allows active + trial subscribers through
- [ ] 7-day free trial: creates subscription with `trial_end = now + 7 days`
- [ ] Trial abuse prevention: 1 trial per Telegram ID (checked in SQLite)
- [ ] Lifetime plan never expires
- [ ] Grace period: 3 days after period ends before downgrading
- [ ] Auto-renew flag stored and checked
- [ ] All state transitions logged
- [ ] Test coverage ≥85% (critical business logic)

---

### Task 7.2: Payment Handlers — Telegram Stars + Midtrans (Priority: P1)
**Depends on:** Task 7.1, Task 3.1
**Files to create/modify:**
- `src/payments/stars.py` (create) — Telegram Stars: send_invoice, pre_checkout_query, successful_payment
- `src/payments/midtrans.py` (create) — Midtrans: create charge, verify webhook signature, handle notification
- `src/handlers/premium.py` (create) — /premium, /statuspremium, /cancel handlers
- `src/handlers/payments.py` (create) — PTB payment handlers: PreCheckoutQueryHandler, SuccessfulPaymentHandler
- `src/web_server.py` (modify) — add Midtrans webhook route
- `tests/test_stars_payment.py` (create) — mock PTB payment flow
- `tests/test_midtrans_payment.py` (create) — mock Midtrans API + webhook
- `tests/test_premium_handlers.py` (create) — test /premium, /statuspremium, /cancel

**TDD:**
- RED: Write test `test_premium_command_shows_plans` → fails
- GREEN: Implement /premium: inline keyboard with Monthly/Yearly/Lifetime + Stars/Midtrans options → passes
- RED: Write test `test_send_stars_invoice` → fails
- GREEN: Implement `StarsPayment.send_invoice(user_id, plan)` using PTB `send_invoice` → passes
- RED: Write test `test_pre_checkout_query_validates` → fails
- GREEN: Implement `PreCheckoutQueryHandler`: validate payload → `answer(ok=True)` → passes
- RED: Write test `test_successful_payment_activates_subscription` → fails
- GREEN: Implement `SuccessfulPaymentHandler`: activate subscription + create invoice record → passes
- RED: Write test `test_midtrans_create_charge_returns_payment_url` → fails
- GREEN: Implement `MidtransPayment.create_charge(order_id, amount, method)` → passes
- RED: Write test `test_midtrans_webhook_verifies_signature` → fails
- GREEN: Implement webhook handler: verify SHA512 signature → update subscription → passes
- RED: Write test `test_midtrans_webhook_idempotent` → fails
- GREEN: Implement dedup: check invoice status before processing → passes
- RED: Write test `test_statuspremium_shows_subscription_info` → fails
- GREEN: Implement /statuspremium: plan, status, sisa hari, invoice history → passes
- RED: Write test `test_cancel_disables_auto_renew` → fails
- GREEN: Implement /cancel: set auto_renew=0, premium stays active until period end → passes
- RED: Write test `test_stars_refund_downgrades_user` → fails
- GREEN: Implement refund detection: detect refund → downgrade to free → passes
- REFACTOR: Extract payment amount mapping (plan → Rupiah); add retry for webhook failures

**Pricing:**
| Plan | Price | Stars Amount |
|------|-------|-------------|
| Monthly | Rp 25.000 | 25000 |
| Yearly | Rp 200.000 | 200000 |
| Lifetime | Rp 750.000 | 750000 |

**Commands to verify:**
```bash
pytest tests/test_stars_payment.py tests/test_midtrans_payment.py tests/test_premium_handlers.py -v --cov=src/payments --cov=src/handlers/premium.py --cov=src/handlers/payments.py
```

**Acceptance Criteria:**
- [ ] /premium shows plan comparison table + payment method selection (inline keyboard)
- [ ] Telegram Stars: send_invoice → pre_checkout → successful_payment → activate subscription
- [ ] Midtrans: create charge → payment URL sent → webhook received → signature verified → subscription activated
- [ ] Webhook is idempotent: duplicate webhook for same order_id → no double activation
- [ ] /statuspremium shows: plan, status, sisa hari, auto-renew status, invoice history
- [ ] /cancel disables auto-renew; premium stays active until period end
- [ ] Stars refund detected → auto-downgrade to free
- [ ] Payment pending >24h → expired, user must restart from /premium
- [ ] Grace period: 3 days after failed renewal (except lifetime)
- [ ] Day 5 trial reminder: "⏰ Premium gratis tinggal 2 hari. Mau lanjut? /premium"
- [ ] Test coverage ≥80%

---

## Wave 8: Premium Features
**Estimated time:** 3 hours
**Goal:** OCR receipt scanning and recurring transactions with bill reminders.

---

### Task 8.1: OCR Receipt Scanner — Gemini Flash Vision (Priority: P2)
**Depends on:** Task 7.1, Task 4.2
**Files to create/modify:**
- `src/services/ocr_service.py` (create) — download photo, encode base64, call Gemini Flash, parse JSON response, map category
- `src/handlers/messages.py` (modify) — add photo message handler with @premium_required
- `tests/test_ocr_service.py` (create) — mock Gemini API, test parsing, test confidence threshold

**TDD:**
- RED: Write test `test_scan_receipt_returns_structured_data` → fails
- GREEN: Implement `OCRService.scan(photo_file_id)` → download → base64 → Gemini → parse JSON → passes
- RED: Write test `test_parse_gemini_response_extracts_fields` → fails
- GREEN: Implement JSON parsing: merchant, total_amount, date_iso, items, category_suggestion → passes
- RED: Write test `test_category_mapping_to_user_categories` → fails
- GREEN: Implement: map Gemini's category_suggestion to nearest user category → passes
- RED: Write test `test_low_confidence_prompts_user` → fails
- GREEN: Implement: confidence < 0.5 → "Gak yakin nih. Ini struk apa?" → passes
- RED: Write test `test_high_confidence_shows_confirmation` → fails
- GREEN: Implement: confidence ≥ 0.5 → "Indomaret, Rp 85.000. Simpan? [Ya] [Edit]" → passes
- RED: Write test `test_ocr_failure_returns_graceful_message` → fails
- GREEN: Implement: API error / unparseable → "Gagal baca struk. Coba foto lebih jelas atau input manual." → passes
- RED: Write test `test_ocr_limit_30_per_month` → fails
- GREEN: Implement: check OCR count in SQLite, reject if ≥30 → passes
- RED: Write test `test_photo_handler_gated_by_premium` → fails
- GREEN: Apply `@premium_required("OCR Scanner")` to photo handler → passes
- REFACTOR: Extract Gemini prompt template; add retry for transient API errors

**Gemini prompt:**
```
Extract receipt data from this image. Return JSON:
{
  "merchant": "string",
  "total_amount": integer,
  "date_iso": "YYYY-MM-DD",
  "items": [{"name": "string", "amount": integer}],
  "currency": "IDR",
  "category_suggestion": "string"
}
All fields optional. Language: Indonesian.
```

**Commands to verify:**
```bash
pytest tests/test_ocr_service.py -v --cov=src/services/ocr_service.py
```

**Acceptance Criteria:**
- [ ] User sends photo → bot downloads from Telegram → sends to Gemini Flash → parses response
- [ ] High confidence (≥0.5): shows confirmation with merchant, amount, category, date
- [ ] Low confidence (<0.5): asks user to clarify
- [ ] OCR failure: graceful message "Gagal baca struk. Coba foto lebih jelas atau input manual."
- [ ] Limit: 30 OCR/bulan for Premium; counter in SQLite
- [ ] Free user sends photo → "🔒 Fitur Premium. Butuh akses? /premium"
- [ ] Category auto-mapped to nearest user category
- [ ] [Ya] button → creates transaction via TransactionService
- [ ] [Edit] button → inline edit flow
- [ ] Test coverage ≥80%

---

### Task 8.2: Recurring Transactions + Bill Reminders (Priority: P2)
**Depends on:** Task 7.1, Task 4.2, Task 3.1
**Files to create/modify:**
- `src/services/recurring_service.py` (create) — recurring transaction CRUD, due date calculation, execution logic
- `src/handlers/commands.py` (modify) — add /tagihan ConversationHandler
- `src/auth/token_store.py` (modify) — add recurring_transactions table
- `src/bot.py` (modify) — register JobQueue recurring jobs
- `tests/test_recurring_service.py` (create) — due date calc, execution, reminder logic
- `tests/test_tagihan_handler.py` (create) — test /tagihan wizard flow

**TDD:**
- RED: Write test `test_create_recurring_transaction` → fails
- GREEN: Implement `RecurringService.create()` → stores in SQLite → passes
- RED: Write test `test_is_due_monthly_on_correct_date` → fails
- GREEN: Implement `RecurringService.is_due(recurring_tx, today)` → passes
- RED: Write test `test_execute_recurring_creates_transaction` → fails
- GREEN: Implement `RecurringService.execute(recurring_tx)` → calls TransactionService.create() → passes
- RED: Write test `test_reminder_sent_h_minus_n_days` → fails
- GREEN: Implement `RecurringService.check_reminders()` → sends Telegram message → passes
- RED: Write test `test_cron_job_executes_due_transactions` → fails
- GREEN: Implement JobQueue hourly job: check all recurring, execute due ones → passes
- RED: Write test `test_cron_job_sends_reminders_at_7am` → fails
- GREEN: Implement JobQueue daily 7AM job: check reminders → passes
- RED: Write test `test_tagihan_command_wizard_flow` → fails
- GREEN: Implement /tagihan ConversationHandler: name → amount → category → frequency → date → reminder → passes
- RED: Write test `test_tagihan_list_shows_all_recurring` → fails
- GREEN: Implement /tagihan list → passes
- RED: Write test `test_tagihan_hapus_deactivates` → fails
- GREEN: Implement /tagihan hapus <id> → sets is_active=0 → passes
- RED: Write test `test_recurring_gated_by_premium` → fails
- GREEN: Apply `@premium_required("Transaksi Berulang")` → passes
- REFACTOR: Extract due date calculation to utility; add timezone handling (WIB)

**SQLite table (from spec E.2):**
```sql
CREATE TABLE recurring_transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   BIGINT NOT NULL,
    name          TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    category_id   INTEGER NOT NULL,
    frequency     TEXT NOT NULL CHECK (frequency IN ('daily','weekly','monthly','yearly')),
    day_of_month  INTEGER,
    day_of_week   INTEGER,
    remind_before INTEGER DEFAULT 1,
    last_executed TEXT,
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

**Commands to verify:**
```bash
pytest tests/test_recurring_service.py tests/test_tagihan_handler.py -v --cov=src/services/recurring_service.py
```

**Acceptance Criteria:**
- [ ] /tagihan starts wizard: name → amount → category → frequency → date → reminder
- [ ] Recurring transaction auto-executed on due date via JobQueue hourly cron
- [ ] Reminder sent at 7AM WIB, H-N days before due date
- [ ] /tagihan list shows all active recurring transactions
- [ ] /tagihan hapus <id> deactivates recurring
- [ ] Free user → "🔒 Fitur Premium"
- [ ] Auto-input transaction with description "[Auto] {name}"
- [ ] last_executed updated after each execution to prevent double-execution
- [ ] Test coverage ≥80%

---

## Wave 9: Polish & Error Handling
**Estimated time:** 2.5 hours
**Goal:** All edge cases handled, error messages in Bahasa Indonesia, resilience patterns in place.

---

### Task 9.1: Error Handling + Resilience + Edge Cases (Priority: P1)
**Depends on:** All Waves 1-8
**Files to create/modify:**
- `src/middleware/error_handler.py` (create) — global error handler for PTB: catch all exceptions, log, send user-friendly message
- `src/bot.py` (modify) — register global error handler
- `src/handlers/commands.py` (modify) — add /export handler
- All handler files (modify) — ensure all error messages in Bahasa Indonesia
- `tests/test_error_handling.py` (create) — test error scenarios

**TDD:**
- RED: Write test `test_unhandled_exception_sends_friendly_message` → fails
- GREEN: Implement global error handler: log error, send "Terjadi kesalahan. Coba lagi nanti." → passes
- RED: Write test `test_oauth_expired_informs_user` → fails
- GREEN: Implement: catch token expired → "Token Google kamu udah expired. Ketik /login untuk refresh." → passes
- RED: Write test `test_sheet_deleted_prompts_recreate` → fails
- GREEN: Implement: catch SheetNotFound → "Spreadsheet gak ketemu. Mau bikin baru? /login" → passes
- RED: Write test `test_google_api_rate_limit_retries` → fails
- GREEN: Implement: retry 3x with backoff on 429 → passes
- RED: Write test `test_not_logged_in_redirects_to_login` → fails
- GREEN: Implement: check auth before any sheet operation → "Kamu belum login. Ketik /login dulu ya." → passes
- RED: Write test `test_payment_webhook_retry` → fails
- GREEN: Implement: Midtrans webhook retry 3x on failure → passes
- RED: Write test `test_export_command_generates_csv` → fails
- GREEN: Implement /export: generate CSV from transaksi tab, send as document → passes
- REFACTOR: Centralize error messages in `src/i18n/messages.py` dict

**Edge cases to handle (from spec):**
1. Duplicate entries → dedup check
2. Ambiguous amounts → parser returns error
3. Multi-line messages → split and parse each
4. Edit/delete → /edit <id>, /hapus <id>
5. Month-end rollover → show previous month on 1st
6. Zero transactions → friendly message
7. Category collision → prompt user
8. Rate limits → retry with backoff
9. Google Sheets API error → exponential backoff
10. OAuth token expired → auto-inform + re-auth prompt
11. Sheet deleted → "File gak ketemu" + recreate option
12. User ganti akun Google → re-auth flow
13. OAuth user cancel → "Login dibatalkan"
14. Dashboard formula error → /perbaiki suggestion
15. Payment pending >24h → expired
16. Premium expired → data intact, features locked
17. Midtrans webhook gagal → retry 3x
18. Telegram Stars refund → auto-downgrade
19. Free trial abuse → 1 per Telegram ID
20. OCR cost spike → 30/bulan limit

**Commands to verify:**
```bash
pytest tests/test_error_handling.py -v
# Manual: test each error scenario in Telegram
```

**Acceptance Criteria:**
- [ ] All error messages in Bahasa Indonesia
- [ ] Global error handler catches unhandled exceptions
- [ ] OAuth expired → specific recovery message + /login prompt
- [ ] Sheet deleted → "File gak ketemu" + recreate option
- [ ] Google API rate limit → retry 3x with exponential backoff
- [ ] Not logged in → redirect to /login
- [ ] Payment webhook failure → retry 3x + alert developer
- [ ] Premium feature accessed by free user → "🔒 Fitur Premium. Upgrade di /premium"
- [ ] OCR failure → "Gagal baca struk. Coba foto lebih jelas atau input manual."
- [ ] /export generates CSV and sends as Telegram document
- [ ] All 25 edge cases from spec handled
- [ ] Test coverage ≥80% on error handling

---

### Task 9.2: AI Insights + Multi-Currency (Priority: P2)
**Depends on:** Task 7.1, Task 4.2
**Files to create/modify:**
- `src/services/insight_service.py` (create) — analyze spending patterns, generate insight text via LLM
- `src/handlers/commands.py` (modify) — add /insight handler with @premium_required
- `tests/test_insight_service.py` (create) — mock LLM, test insight generation

**TDD:**
- RED: Write test `test_generate_insight_analyzes_spending` → fails
- GREEN: Implement `InsightService.generate_insight(telegram_id, month)` → aggregate data → LLM call → insight text → passes
- RED: Write test `test_insidentifies_top_spending_category` → fails
- GREEN: Implement: find top spending category, compare to previous month → passes
- RED: Write test `test_insight_gated_by_premium` → fails
- GREEN: Apply `@premium_required("AI Insight")` → passes
- RED: Write test `test_multi_currency_converts_to_idr` → fails
- GREEN: Implement: detect USD/EUR/SGD in parser → convert to IDR using exchange rate → passes
- REFACTOR: Extract LLM prompt template; add caching for exchange rates

**Insight examples:**
- "💡 Bulan ini kamu boros di Makanan (Rp 1.2jt, naik 30% dari bulan lalu)"
- "📊 Pengeluaran terbesar: Transportasi (25% dari total)"
- "✅ Budget Tagihan aman — baru 40% terpakai"

**Commands to verify:**
```bash
pytest tests/test_insight_service.py -v --cov=src/services/insight_service.py
```

**Acceptance Criteria:**
- [ ] /insight generates spending analysis using LLM
- [ ] Identifies top spending category + trend vs previous month
- [ ] Free user → "🔒 Fitur Premium"
- [ ] Multi-currency: parser detects USD/EUR/SGD → converts to IDR
- [ ] Exchange rate cached for 1 hour
- [ ] Insight responds <5 seconds
- [ ] Test coverage ≥80%

---

## Wave 10: Testing & Documentation
**Estimated time:** 2 hours
**Goal:** Comprehensive test suite and complete documentation.

---

### Task 10.1: Comprehensive Test Suite (Priority: P1)
**Depends on:** All Waves 1-9
**Files to create/modify:**
- `tests/conftest.py` (modify) — shared fixtures: mock bot, mock sheets, mock OAuth, test database
- `tests/integration/test_full_flow.py` (create) — end-to-end: onboarding → login → transaction → report → premium
- `tests/integration/test_payment_flow.py` (create) — end-to-end: /premium → payment → activation → feature access
- `tests/integration/test_ocr_flow.py` (create) — end-to-end: photo → OCR → confirmation → transaction
- `tests/integration/test_recurring_flow.py` (create) — end-to-end: /tagihan → cron → auto-transaction → reminder

**TDD:**
- RED: Write integration test `test_full_user_journey` → fails
- GREEN: Wire all components → passes
- RED: Write integration test `test_premium_upgrade_flow` → fails
- GREEN: Wire payment → subscription → feature gate → passes
- RED: Write integration test `test_ocr_to_transaction` → fails
- GREEN: Wire photo handler → OCR → confirmation → transaction → passes
- RED: Write integration test `test_recurring_auto_execution` → fails
- GREEN: Wire JobQueue → recurring service → transaction service → passes
- REFACTOR: Extract common test fixtures; add test database cleanup

**Test categories:**
| Category | Count | Coverage Target |
|----------|-------|----------------|
| Unit (parser) | 50+ | 90% |
| Unit (services) | 30+ | 80% |
| Unit (sheets) | 20+ | 80% |
| Unit (auth) | 15+ | 85% |
| Unit (payments) | 15+ | 80% |
| Integration | 10+ | N/A |
| **Total** | **140+** | **80% overall** |

**Commands to verify:**
```bash
pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html
# Open htmlcov/index.html for visual coverage report
```

**Acceptance Criteria:**
- [ ] 140+ test cases total
- [ ] Overall coverage ≥80% on `src/`
- [ ] Parser coverage ≥90%
- [ ] All integration tests pass
- [ ] No test depends on external services (all mocked)
- [ ] Test database cleaned up between tests
- [ ] `pytest tests/ -v` completes in <60 seconds

---

### Task 10.2: Documentation + Setup Guides (Priority: P1)
**Depends on:** Task 10.1
**Files to create/modify:**
- `README.md` (modify) — complete project documentation
- `docs/setup-guide.md` (modify) — step-by-step setup for Google Cloud, Telegram, Midtrans
- `docs/deployment-guide.md` (create) — Railway deployment instructions
- `.env.example` (modify) — ensure all env vars documented with descriptions

**README.md structure:**
```markdown
# Asisten Keuangan — Personal Finance Telegram Bot

## Features
## Quick Start
## Prerequisites
## Installation
## Configuration
## Running Locally
## Deployment (Railway)
## Bot Commands
## Premium Features
## Architecture
## Development
## Testing
## License
```

**Commands to verify:**
```bash
# Verify README renders correctly
# Verify all links work
# Verify setup guide is complete
```

**Acceptance Criteria:**
- [ ] README.md covers: features, setup, installation, configuration, running, deployment, commands
- [ ] Setup guide covers: Google Cloud Console, Telegram BotFather, Midtrans sandbox, Gemini API
- [ ] Deployment guide covers: Railway setup, env vars, webhook URL configuration
- [ ] .env.example has all required variables with descriptions
- [ ] All code examples in docs are tested and correct
- [ ] Architecture diagram included (from spec)

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Waves** | 10 |
| **Total Tasks** | 20 |
| **Max Parallel per Wave** | 2 |
| **Estimated Total Time** | ~24 hours |
| **Requirements Covered** | R1-R13 (all 13) |
| **Edge Cases Covered** | 25/25 |

### Wave Time Estimates

| Wave | Focus | Est. Time | Cumulative |
|------|-------|-----------|------------|
| 0 | Project Scaffolding | 30 min | 30 min |
| 1 | Core Infrastructure | 2 hours | 2.5 hours |
| 2 | Google Sheets Integration | 2 hours | 4.5 hours |
| 3 | Bot Skeleton + Onboarding | 2.5 hours | 7 hours |
| 4 | Transaction Core (MVP) | 3 hours | 10 hours |
| 5 | Categories & Budgets | 2 hours | 12 hours |
| 6 | Reports & Dashboard | 3 hours | 15 hours |
| 7 | Premium System | 3 hours | 18 hours |
| 8 | Premium Features | 3 hours | 21 hours |
| 9 | Polish & Error Handling | 2.5 hours | 23.5 hours |
| 10 | Testing & Documentation | 2 hours | 25.5 hours |

### Critical Path

```
0.1 → 1.1 → 2.1 → 2.2 → 3.1 → 4.2 → 5.2 → 6.1 → 7.2 → 8.2 → 9.1 → 10.1
```

The critical path runs through: scaffolding → config → sheets client → sheet setup → bot → transactions → budgets → reports → payments → recurring → error handling → tests.

### Risk Areas

1. **Message Parser (Task 4.1):** Hardest component. 50+ test cases required. Indonesian NL is ambiguous. Plan for iterative refinement.
2. **OAuth Flow (Task 1.2):** Must work on first try. WebApp + fallback copy-paste. Test with real Google account.
3. **Dashboard Generator (Task 6.2):** Sheets API v4 `batchUpdate` is complex. Chart quota (max 20). Protected ranges. Plan for debugging time.
4. **Payment Webhooks (Task 7.2):** Must be idempotent. Midtrans signature verification. Stars refund detection. Test with sandbox.
5. **Premium Gate (Task 7.1):** Must be at every premium endpoint. Missing gate = revenue leak. Audit all handlers.

### GSD Execution Command

```bash
gsd execute tasks/telegram-finance-assistant.plan.md
```
