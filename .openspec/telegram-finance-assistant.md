# Portfolio Feature: Personal Finance Recap Assistant (Telegram Bot)

## Specification ID
`telegram-finance-assistant-2026-06`

## Phase: PROPOSAL

> **Monetization Pivot (2026-06-21):** Tambah **freemium model** — free tier fungsional penuh untuk basic usage, premium Rp 25.000/bulan unlock fitur advanced. Target: sustainable income. Payment via **Telegram Stars** (native, no setup) + **QRIS/e-wallet via Midtrans** (fallback).
>
> **UX Pivot (2026-06-21):** Onboarding <2 menit + Google Sheets Dashboard tab.
>
> **Architectural Pivot v2 (2026-06-21):** Per-user Google Sheets via OAuth, zero data liability.
>
> **Pivot v1 (2026-06-21):** PostgreSQL → Google Sheets (Service Account).

---

## Brainstorming Summary — Sharpening the Idea

The raw idea: *"Platform Telegram bot untuk personal asisten yang melakukan semua proses rekap keuangan user."* Below are the key decisions made after exploring edge cases, personas, and scope constraints.

### Key Decisions

| Decision Point | Choice | Rationale |
|---|---|---|
| **Recap scope (MVP)** | Expense + income tracking + category breakdown + daily/monthly summaries + budget alerts + Dashboard | Dashboard visual di sheet user bikin laporan lebih powerful dari sekadar chart PNG |
| **Input methods (MVP)** | Natural-language text (Bahasa Indonesia) + slash commands | Voice/photo require STT/OCR — jadi fitur premium |
| **Output formats** | Text recap + Google Sheets native charts + inline keyboard | Dashboard interaktif, auto-update, user akses kapan aja |
| **Data backend** | Google Sheets — per-user, di Google Drive user sendiri via OAuth | Zero data liability; gratis; portable |
| **Data privacy** | Zero data liability — semua data di Drive user; bot cuma "editor" via OAuth | GDPR built-in; user revoke kapan aja |
| **Auth method** | Google OAuth 2.0 via Telegram WebApp auto-callback + fallback copy-paste | 1-klik login; zero friction |
| **Token storage** | SQLite — encrypted mapping `user_id → refresh_token + spreadsheet_id` | Ringan; 1-2 MB |
| **Onboarding UX** | Wizard-style <2 menit; progressive disclosure; default everything | Friction minimal = conversion tinggi |
| **Monetization** | **Freemium: Free (basic) + Premium Rp 25k/bulan + Lifetime Rp 750k** | Sustainable; target Indonesia; payment via Telegram Stars + QRIS |
| **Integrations** | MVP is fully manual input (free); OCR receipt + recurring = premium | Premium features justify subscription |
| **Primary language** | Bahasa Indonesia | Target user Indonesian; English toggle via `/bahasa` |
| **Tech stack** | Python 3.12+ + PTB + gspread + google-auth-oauthlib + SQLite + matplotlib + Sheets API v4 + Midtrans SDK | Zero infra cost for free tier; premium revenue covers API costs |
| **Deployment** | Railway free tier (1 process) → upgrade ke Hobby saat user >500 | Scale with revenue |
| **Total cost (free)** | Rp 0/bulan | — |
| **Target revenue** | 1000 user × 5% premium × Rp 25k = Rp 1.25jt/bulan | Covers hosting + OCR API + profit |

### Edge Cases Identified

1. **Duplicate entries:** Dedup by amount + category within 5 min window
2. **Ambiguous amounts:** Parser normalizes all formats to integer
3. **Multi-line messages:** Split by newline, parse each
4. **Edit/delete:** `/edit [id]`, `/hapus [id]`
5. **Month-end rollover:** Show previous month on the 1st
6. **Zero transactions:** Friendly onboarding message
7. **Category collision:** Both map to matching category
8. **Rate limits:** Telegram 30 msg/sec; Google Sheets 60 req/min/user → aman
9. **Concurrent sessions:** Handled by Telegram sync
10. **Google Sheets API error:** Exponential backoff + graceful message
11. **OAuth token expired:** Auto-inform user → re-auth
12. **Sheet deleted:** "File gak ketemu. Mau bikin baru?"
13. **User ganti akun Google:** Re-auth → new sheet → data dari 0
14. **User tanpa akun Google:** Mode offline opsional
15. **OAuth user cancel:** "Login dibatalkan. Coba lagi nanti."
16. **Dashboard formula error:** Protected ranges + `/perbaiki`
17. **Dashboard chart quota:** Max 20 charts; hapus lama + regenerate
18. **User skip onboarding:** Bisa /login nanti; pakai default
19. **Payment pending >24 jam:** Expired, user harus restart dari `/premium`
20. **Premium expired:** Data tetap ada; fitur premium locked; user bisa re-subscribe
21. **Midtrans webhook gagal:** Retry 3x + backoff; fallback manual verification via `/statuspremium`
22. **Telegram Stars refund:** Bot detect refund → auto-downgrade user ke free
23. **Free trial abuse:** User bikin akun baru tiap 7 hari → rate-limit trial: 1 trial per Telegram ID
24. **OCR API cost spike:** User upload 100 struk/hari. Premium limits: 30 OCR/bulan (cukup untuk daily). Extra: Rp 1.000/OCR.
25. **User ganti akun Google saat premium:** Premium tetap attached ke Telegram ID, bukan Google account. Beda sheet = data beda, tapi status premium sama.

---

## Requirements (Business)

### R1 — Natural-Language Transaction Logging
**Priority:** P0 (MVP — Free)

**Acceptance Criteria:**
- [ ] Parse "makan siang 50rb" → Makanan, 50000, expense
- [ ] Parse "gaji 5jt" → Gaji, 5000000, income
- [ ] Parse multiple transactions: "pulsa 100k, bensin 80rb"
- [ ] Prompt for ambiguous categories
- [ ] Amount formats: "50rb", "50.000", "50000", "50k"
- [ ] Date override: "kemarin makan siang 50rb"
- [ ] Write latency <2 detik

### R2 — Slash Command System
**Priority:** P0 (MVP)

**Acceptance Criteria:**
- [ ] `/start` — wizard onboarding <2 menit
- [ ] `/login` — Google OAuth (WebApp auto-callback)
- [ ] `/catat` — guided transaction logging
- [ ] `/hariini`, `/mingguan`, `/bulanan` — reports
- [ ] `/dashboard` — link ke tab Dashboard sheet user
- [ ] `/anggaran` — view/set budget
- [ ] `/kategori` — manage categories
- [ ] `/edit <id>`, `/hapus <id>` — edit/delete
- [ ] `/export` — CSV / link spreadsheet
- [ ] `/perbaiki` — regenerate Dashboard
- [ ] `/premium` — **lihat paket + pilih + bayar** (inline keyboard)
- [ ] `/statuspremium` — **status langganan + sisa hari + invoice history**
- [ ] `/logout` — revoke token + hapus mapping
- [ ] `/bantuan` — help

### R3 — Category Management
**Priority:** P0 (Free)

**Acceptance Criteria:**
- [ ] 13 default categories langsung siap — user gak perlu setup
- [ ] **Free: max 5 custom categories.** Premium: unlimited.
- [ ] User can rename/delete custom categories (defaults undeletable)
- [ ] Denormalized `category_name` for historical accuracy

### R4 — Budget Tracking & Alerts
**Priority:** P1

**Acceptance Criteria:**
- [ ] Set budget via `/anggaran`; tampil di Dashboard
- [ ] Warnings at 50%, 80%, 90%, 100%
- [ ] **Free: 1 budget total. Premium: unlimited budgets + per-category.**
- [ ] Budget resets monthly
- [ ] Dashboard conditional formatting (merah kalau over)

### R5 — Reports & Analytics
**Priority:** P0 (Free)

**Acceptance Criteria:**
- [ ] `/hariini` — text recap di Telegram
- [ ] `/mingguan` — text + bar chart PNG
- [ ] `/bulanan` — text + dashboard link
- [ ] Dashboard tab (R10): **Free = basic (ringkasan aja). Premium = full (pie, bar, sparkline, conditional formatting, top 5).**
- [ ] **Free: history 3 bulan. Premium: unlimited history.**
- [ ] Report responds <3 detik untuk <1000 transaksi

### R6 — Multi-User Isolation
**Priority:** P0 (Free)

**Acceptance Criteria:**
- [ ] Physical isolation — setiap user punya spreadsheet sendiri
- [ ] Bot akses via OAuth token user — impossible cross-access
- [ ] SQLite hanya simpan mapping + subscription data

### R7 — Onboarding Experience (Simplified)
**Priority:** P1

**Target: <2 menit dari `/start` ke transaksi pertama.**

**Acceptance Criteria:**
- [ ] 4 langkah wizard: nama → Google OAuth → selesai → quick tutorial
- [ ] Default categories, default config — setup minimal
- [ ] Budget optional (skip)
- [ ] Progressive disclosure: fitur advanced dikenalin nanti
- [ ] **After onboarding: tawaran 7-day free trial Premium** (opsional, bisa skip)
- [ ] Total waktu: <120 detik

### R8 — Error Handling & Resilience
**Priority:** P1

**Acceptance Criteria:**
- [ ] Unknown command, unparseable amount, belum login — graceful messages
- [ ] Google Sheets API error → retry 3x + backoff
- [ ] OAuth expired / sheet not found → specific recovery messages
- [ ] **Payment webhook failure → retry 3x; alert developer; user bisa cek manual**
- [ ] **Premium feature accessed by free user → "🔒 Fitur Premium. Upgrade di /premium"**
- [ ] **OCR failure → "Gagal baca struk. Coba foto lebih jelas atau input manual."**

### R9 — Google OAuth Authentication
**Priority:** P0 (Free)

**Acceptance Criteria:**
- [ ] WebApp auto-callback (primary) + copy-paste (fallback)
- [ ] Scope: `drive.file` (minimal)
- [ ] Token encrypted di SQLite; auto-refresh
- [ ] `/logout` revoke + hapus

### R10 — Google Sheets Dashboard
**Priority:** P0

**Acceptance Criteria:**
- [ ] Tab Dashboard auto-generated saat setup
- [ ] **Free tier:** Ringkasan (SUMIF totals + saldo). **No native charts.**
- [ ] **Premium tier:** Full dashboard — Pie Chart, Bar Chart (6-month trend), Sparklines (daily), Top 5 + bar visual, Conditional Formatting. Detail di Appendix D.
- [ ] Protected ranges; `/perbaiki` regenerate

### R11 — Premium Tier & Monetization (NEW)
**Priority:** P1

**Freemium model dengan target revenue dari 5% conversion rate.**

**Acceptance Criteria:**
- [ ] `/premium` — tampilkan paket + fitur comparison (Free vs Premium table)
- [ ] **Pricing:**
  - Bulanan: Rp 25.000/bulan
  - Tahunan: Rp 200.000/tahun (hemat 33%, Rp 16.667/bulan)
  - Lifetime: Rp 750.000 (sekali bayar)
- [ ] **Payment methods:**
  - Primary: **Telegram Stars** (native, no KYC, instant)
  - Secondary: **QRIS / GoPay / OVO / Dana via Midtrans**
  - Fallback: Transfer bank (manual verification)
- [ ] Payment state machine: `pending → paid → active | expired | cancelled → expired`
- [ ] Midtrans webhook handler: verify signature, update subscription
- [ ] `/statuspremium` — status + sisa hari + invoice history + auto-renew status
- [ ] **7-day free trial** for new users (auto-downgrade after 7 days unless subscribed)
- [ ] Trial reminder at day 5: "Premium gratis tinggal 2 hari. Mau lanjut? /premium"
- [ ] Auto-renew: user opt-in, bot charge via Telegram Stars atau Midtrans token
- [ ] Premium badge "⭐ Premium" di `/statuspremium` dan header laporan
- [ ] Free user lihat fitur premium dengan label "🔒 Premium" + inline button "Upgrade ke Premium →"
- [ ] `/cancel` — batalkan auto-renew; premium tetap aktif sampai periode habis
- [ ] Grace period 3 hari kalau payment failed (kecuali lifetime)

### R12 — OCR Receipt Scanner (Premium Only — NEW)
**Priority:** P2

**User foto struk → bot extract data via AI Vision API → auto-input transaksi.**

**Acceptance Criteria:**
- [ ] User kirim foto struk ke bot (sebagai Telegram Photo message)
- [ ] Bot kirim foto ke Gemini / Claude Vision API dengan prompt: "Extract: merchant, total amount, date, items (optional). Format: JSON. Language: Indonesian."
- [ ] Bot parse response → pre-fill transaction: amount, category (auto-detect), date, description (nama toko)
- [ ] Bot konfirmasi ke user: "Dari struk: Indomaret, Rp 85.000, 21 Juni 2026. Kategori: Belanja. ✅ Simpan? [Ya] [Edit]"
- [ ] Kalau OCR gagal (blur, bukan struk): "Gak bisa baca struknya. Coba foto lebih jelas atau input manual."
- [ ] **Limit: 30 OCR/bulan untuk Premium.** Extra: Rp 1.000/OCR (opsional add-on).
- [ ] OCR history: user bisa lihat struk yang udah di-scan
- [ ] Cost analysis: 1 OCR call ~Rp 20-50 (Gemini Flash) atau ~Rp 150 (Claude). 30 OCR/user/bulan = max Rp 4.500/user. Premium revenue Rp 25.000 → margin positif.

### R13 — Recurring Transactions & Bill Reminders (Premium Only — NEW)
**Priority:** P2

**User setup transaksi berulang; bot auto-input + kirim reminder.**

**Acceptance Criteria:**
- [ ] `/tagihan` command — setup recurring transaction:
  - "Nama tagihan?" → "WiFi"
  - "Jumlah?" → "350000"
  - "Kategori?" → "Tagihan"
  - "Frekuensi?" → [Bulanan] [Mingguan] [Tahunan]
  - "Tanggal?" → "5" (tiap tanggal 5)
  - "Ingatkan H-?" → "1" (reminder H-1)
- [ ] Bot auto-input transaksi di tanggal jatuh tempo
- [ ] Bot kirim reminder via Telegram: "📅 Besok bayar WiFi Rp 350.000 ya."
- [ ] `/tagihan list` — lihat semua recurring
- [ ] `/tagihan hapus <id>` — stop recurring
- [ ] Cron job: check tiap jam, execute recurring yang jatuh tempo hari ini
- [ ] **Free tier: tidak tersedia.** Muncul "🔒 Fitur Premium" kalau user coba akses.

---

## Free vs Premium Feature Matrix

| Fitur | Free | Premium (Rp 25k/bln) |
|---|---|---|
| Transaksi unlimited | ✓ | ✓ |
| Kategori default (13) | ✓ | ✓ |
| Custom categories | 5 max | **Unlimited** |
| History data di laporan | 3 bulan | **Unlimited** |
| Budget tracking | 1 budget total | **Unlimited + per-category** |
| Dashboard di Sheet | Basic (ringkasan) | **Full (charts, sparkline, conditional formatting)** |
| Export CSV | Manual (`/export`) | **Auto bulanan + Excel format** |
| Recurring transactions | ✗ | ✓ |
| Bill reminders (Telegram) | ✗ | ✓ |
| OCR foto struk | ✗ | **30/bulan** |
| Multi-currency (auto-convert IDR) | ✗ | ✓ |
| Insight AI ("boros di kategori X") | ✗ | ✓ |
| Report sharing (share sheet ke pasangan/akuntan) | ✗ | ✓ |
| Priority support | Community (Grup TG) | **WA/Telegram priority** |
| ⭐ Premium badge | ✗ | ✓ |
| Transaksi via NL text | ✓ | ✓ |
| `/hariini` `/mingguan` `/bulanan` | ✓ | ✓ |
| Google Sheets data ownership | ✓ | ✓ |
| Zero data liability | ✓ | ✓ |

---

## Design (Architecture)

### System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Telegram Cloud                                   │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────────────┐    │
│  │  User    │  │ Telegram     │  │  Telegram Payments (Stars)       │    │
│  │ (Client) │  │ Bot API      │  │  • User bayar pakai Stars        │    │
│  │          │  │              │  │  • Bot verify via API            │    │
│  │ ┌────────┴──┴────────────┐ │  │  • Telegram settle ke developer  │    │
│  │ │ Mini App (WebView)     │ │  └──────────────────────────────────┘    │
│  │ │ • OAuth login          │ │                                           │
│  │ │ • Payment confirmation │ │                                           │
│  │ └────────────────────────┘ │                                           │
│  └────────────────────────────┘                                           │
└──────────────────────────────────────────────────────────────────────────┘
           │                          │                        │
           │  Polling + HTTP server   │                        │
           ▼                          ▼                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     Finance Bot (Python 3.12+)                            │
│       (Railway Free/Hobby — public URL: bot-name.railway.app)            │
│                                                                           │
│  ┌────────────┐ ┌────────────┐ ┌───────────┐ ┌──────────────────────┐   │
│  │Message     │ │Command     │ │Report Gen │ │Premium Gate (deco)   │   │
│  │Parser      │ │Router      │ │(matplot)  │ │@premium_required     │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬─────┘ └──────────────────────┘   │
│        │              │              │                                    │
│        └──────┬───────┘              │                                    │
│               ▼                      │                                    │
│  ┌──────────────────────┐            │                                    │
│  │  Transaction Service │◄───────────┘                                    │
│  └──────────┬───────────┘                                                 │
│             │                                                             │
│             ▼                                                             │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────┐  │
│  │  OAuth + Token Manager       │  │  Payment Manager                 │  │
│  │  (WebApp, token store, enc)  │  │  ┌────────────┐ ┌────────────┐  │  │
│  └──────────────────────────────┘  │  │Telegram    │ │ Midtrans   │  │  │
│                                    │  │Stars       │ │ (QRIS,     │  │  │
│  ┌──────────────────────────────┐  │  │(sendInvoice│ │ e-wallet,  │  │  │
│  │  Dashboard Generator         │  │  │ → verify)  │ │ bank tf)   │  │  │
│  │  (Sheets API v4: charts,     │  │  └────────────┘ └─────┬──────┘  │  │
│  │   conditional fmt, protect)  │  │           │            │         │  │
│  └──────────────────────────────┘  │           ▼            ▼         │  │
│                                    │  ┌──────────────────────────┐   │  │
│  ┌──────────────────────────────┐  │  │ Subscription Service     │   │  │
│  │  Sheets Client (gspread)     │  │  │ (SQLite: subscriptions   │   │  │
│  │  per-user OAuth credential   │  │  │  table + state machine)  │   │  │
│  └──────────────────────────────┘  │  └──────────────────────────┘   │  │
│                                    └──────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Premium Services (gated):                                        │    │
│  │  ┌──────────────┐ ┌────────────────┐ ┌────────────────────────┐  │    │
│  │  │ OCR Scanner  │ │ Recurring Cron │ │ AI Insight Generator   │  │    │
│  │  │ (Gemini API) │ │ (JobQueue)     │ │ (LLM call: analyze     │  │    │
│  │  └──────────────┘ └────────────────┘ │  spending patterns)    │  │    │
│  │                                      └────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │ In-Memory    │  │ SQLite: user_tokens + subscriptions + invoices  │   │
│  │ Cache        │  │ (3 tables, ~2-3 MB for 1000 users)              │   │
│  └──────────────┘  └─────────────────────────────────────────────────┘   │
└─────────────────────┼──────────────────────────────────────────────────────┘
                      │
                      ▼  Google APIs (per-user OAuth) + Gemini API + Midtrans
         ┌────────────────────────────────────────────────┐
         │  Google Drive (per user)  │  Gemini Vision    │
         │  • KeuanganBot sheet     │  • OCR receipts   │
         │  • 5 tabs + Dashboard    │                   │
         └──────────────────────────┴───────────────────┘
```

### Component Descriptions (Updated)

| Component | Responsibility | Tech |
|---|---|---|
| **Message Parser** | NL text → structured txn | regex + keyword matching |
| **Command Router** | Route slash commands + ConversationHandler | PTB |
| **Transaction Service** | CRUD, dedup, aggregation, budget calc | Python |
| **Report Generator** | matplotlib PNG (fallback) | matplotlib |
| **Dashboard Generator** | Native charts, formulas, sparklines, conditional fmt, protected ranges | Google Sheets API v4 |
| **Premium Gate** | Decorator: `@premium_required` — auto-reject free users with "🔒 Upgrade" message | Python decorator |
| **OAuth Token Manager** | WebApp OAuth + fallback, token refresh, encryption | google-auth-oauthlib, cryptography |
| **Token Store** | SQLite: user_tokens + subscriptions + invoices | sqlite3 |
| **Sheets Client** | gspread per-user OAuth; spreadsheet + Dashboard creation | gspread + Sheets API v4 |
| **Payment Manager** | Telegram Stars invoice + Midtrans charge + webhook handler | PTB payments, midtransclient |
| **Subscription Service** | State machine: pending→paid→active→expired; trial management; auto-renew | Python |
| **OCR Scanner** | Gemini Vision API: extract amount, merchant, date, category from photo | google-genai |
| **Recurring Cron** | PTB JobQueue: check tiap jam, auto-input + reminder | PTB JobQueue |
| **AI Insight Generator** | LLM call: analyze spending, generate insight text | OpenAI / Claude / Gemini |
| **Tiny HTTP Server** | OAuth callback + Midtrans webhook + WebApp HTML | aiohttp |
| **In-Memory Cache** | Dedup + daily totals | Python dict |
| **Bot Application** | Lifecycle, handlers, job queue | PTB v21.x |

### Payment Architecture

#### Flow: Telegram Stars (Primary)

```
User: /premium → pilih paket → pilih "Bayar dengan Telegram Stars"
  │
  ▼
Bot: PTB send_invoice(title="Premium Bulanan", amount=25000, currency="IDR",
                       payment_provider="stars")
  │
  ▼
User: Konfirmasi pembayaran di popup Telegram (native UI)
  │
  ▼
Telegram: Verifikasi Stars balance → deduct → kirim update ke bot
  │
  ▼
Bot: pre_checkout_query handler → verify → accept
Bot: successful_payment handler → activate subscription di SQLite
  │
  ▼
Bot: "✅ Premium aktif! Selamat menikmati semua fitur ⭐"
```

#### Flow: Midtrans (Secondary — QRIS, e-wallet, transfer)

```
User: /premium → pilih paket → pilih "QRIS / GoPay / Transfer"
  │
  ▼
Bot: Panggil Midtrans API → create transaction → dapat QRIS URL / payment URL
  │
  ▼
Bot: Kirim inline keyboard: [💳 Bayar via QRIS] [📱 GoPay] [🏧 Transfer Bank]
  │
  ▼
User: Pilih metode → bayar
  │
  ▼
Midtrans: Kirim webhook HTTP POST ke bot: /payments/midtrans/webhook
  │
  ▼
Bot: Verify signature → update subscription → kirim konfirmasi
  │
  ▼
Bot: "✅ Pembayaran diterima! Premium aktif ⭐"
```

#### Payment State Machine

```
          ┌──────────┐
          │  NONE    │  (user baru atau expired)
          └────┬─────┘
               │ user: /premium → pilih paket → payment created
               ▼
          ┌──────────┐
          │ PENDING  │  (menunggu pembayaran / webhook)
          └────┬─────┘
               │
         ┌─────┼──────────────┐
         │     │              │
    payment  │  >24 jam     user cancel
    success  │              │
         │   │              │
         ▼   ▼              ▼
   ┌──────────┐       ┌──────────┐
   │  ACTIVE  │       │ EXPIRED  │
   └────┬─────┘       └──────────┘
        │
   ┌────┼────────────┐
   │    │            │
  renew  │       periode habis
   │    │            │
   │   ┌▼────────┐   ▼
   │   │GRACE    │  ┌──────────┐
   │   │(3 hari) │  │ EXPIRED  │
   │   └────┬────┘  └──────────┘
   │        │
   │   paid?│─── yes ──► ACTIVE (extend)
   │        │
   │        └─── no ───► EXPIRED
   │
   └── auto-renew setiap periode
```

### Tech Stack (Updated)

| Layer | Technology | Justification |
|---|---|---|
| **Language** | Python 3.12+ | Async ecosystem |
| **Bot Framework** | python-telegram-bot v21.x | Async; ConversationHandler; JobQueue; **built-in Payments API (send_invoice, pre_checkout_query, successful_payment)** |
| **Google Sheets RW** | gspread 6.x | Per-user OAuth |
| **Google Sheets API v4** | google-api-python-client | Charts, conditional fmt, protected ranges |
| **Google OAuth** | google-auth-oauthlib | Web Server flow; token refresh |
| **Token Encryption** | cryptography (Fernet) | AES-128-CBC + HMAC |
| **Token + Sub Store** | SQLite (sqlite3) | Zero-setup; user_tokens + subscriptions + invoices |
| **HTTP Server** | aiohttp 3.9+ | OAuth callback + Midtrans webhook + WebApp HTML |
| **Payment — Stars** | PTB built-in | `send_invoice`, `PreCheckoutQueryHandler`, `SuccessfulPaymentHandler` |
| **Payment — Midtrans** | midtransclient (PyPI) | QRIS, e-wallet, bank transfer; webhook verification |
| **OCR (Premium)** | google-genai (Gemini Flash) | Receipt extraction; Rp 20-50/call; fast & cheap |
| **Charting (fallback)** | matplotlib 3.9+ | PNG charts |
| **Deployment** | Railway Free → Hobby | Public URL; scale with revenue |
| **Config** | pydantic-settings 2.x | Env vars: TELEGRAM_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, FERNET_KEY, MIDTRANS_SERVER_KEY, MIDTRANS_CLIENT_KEY, GEMINI_API_KEY |

### Data Model (Updated)

#### SQLite — `token_store.db` (3 tables)

```sql
-- Existing
CREATE TABLE user_tokens (
    telegram_id    BIGINT PRIMARY KEY,
    spreadsheet_id TEXT NOT NULL,
    refresh_token  TEXT NOT NULL,          -- Fernet-encrypted
    token_expiry   TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

-- NEW: Subscription management
CREATE TABLE subscriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id    BIGINT NOT NULL,
    plan           TEXT NOT NULL CHECK (plan IN ('monthly', 'yearly', 'lifetime')),
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'active', 'grace', 'expired', 'cancelled')),
    start_date     TEXT,                     -- ISO8601
    end_date       TEXT,                     -- ISO8601 (NULL for lifetime)
    trial_end      TEXT,                     -- ISO8601 (7-day trial end)
    payment_method TEXT,                     -- 'telegram_stars', 'midtrans_qris', 'midtrans_gopay', etc.
    payment_ref    TEXT,                     -- Stars: charge_id; Midtrans: order_id
    auto_renew     INTEGER DEFAULT 0,        -- 0 or 1
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

-- NEW: Payment audit trail
CREATE TABLE invoices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id    BIGINT NOT NULL,
    subscription_id INTEGER REFERENCES subscriptions(id),
    amount         INTEGER NOT NULL,         -- Rupiah
    method         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'paid', 'failed', 'refunded', 'expired')),
    payment_ref    TEXT,
    raw_response   TEXT,                     -- JSON dari Midtrans/Telegram (debugging)
    created_at     TEXT DEFAULT (datetime('now'))
);
```

#### Per-User Spreadsheet — `config` tab (updated)

| Column | New? | Description |
|---|---|---|
| `telegram_id` | — | Telegram user ID |
| `first_name` | — | Nama panggilan |
| `language` | — | `id` / `en` |
| `monthly_budget` | — | Budget bulanan |
| `join_date` | — | Tanggal join |
| `premium_status` | **NEW** | `free`, `premium`, `trial` |
| `premium_expiry` | **NEW** | ISO8601 (kalau premium/trial) |
| `preferences` | — | JSON preferences |

**4 tabs lainnya:** `transaksi`, `kategori`, `anggaran`, `Dashboard` — tidak berubah.

### Bot Command Structure (Updated)

```
Commands (Free):
  /start          — Onboarding wizard (<2 menit)
  /login          — Google OAuth
  /catat          — Guided transaction logging
  /hariini        — Today's recap
  /mingguan       — Weekly recap
  /bulanan        — Monthly recap + dashboard link
  /dashboard      — Link ke Dashboard sheet
  /anggaran       — View/set budget (free: 1)
  /kategori       — Manage categories (free: 5 custom)
  /edit <id>      — Edit transaction
  /hapus <id>     — Delete transaction
  /export         — Export CSV (manual)
  /perbaiki       — Regenerate Dashboard
  /logout         — Revoke token
  /bantuan        — Help

Commands (Premium only):
  /premium        — Lihat paket + pilih + bayar (free user bisa akses)
  /statuspremium  — Status langganan + invoice history
  /cancel         — Batalkan auto-renew
  /tagihan        — Setup recurring transaction + bill reminder
  /ocr            — (atau kirim foto langsung) OCR struk
  /insight        — AI insight: "Bulan ini kamu boros di..."

🔒 Premium Gate:
  Free user mengakses fitur premium → bot reply:
  "🔒 Fitur Premium. Butuh akses? /premium"
  + inline keyboard [⭐ Upgrade ke Premium] [📋 Lihat fitur Premium]
```

### Privacy & Security Design (Updated)

| Concern | Decision |
|---|---|
| **Data ownership** | User-owned — semua data di Drive user |
| **Zero financial data liability** | SQLite hanya: telegram_id → encrypted(spreadsheet_id + refresh_token) + subscription status |
| **Payment data** | **Minimal** — simpan payment_ref + status aja. Tidak simpan detail kartu, nomor rekening, atau CVV. |
| **Midtrans webhook** | Verify signature hash (SHA512) sebelum proses; IP whitelist Midtrans |
| **Telegram Stars** | Native Telegram API — tidak ada data payment yang lewat server bot |
| **Token storage** | Encrypted at rest (Fernet AES-128-CBC + HMAC) |
| **Token scope** | `drive.file` minimal |
| **No PII logging** | `telegram_id` only; sanitized logs |

### Directory Structure (Updated)

```
personal-finance-bot/
├── .openspec/
│   └── telegram-finance-assistant.md
├── src/
│   ├── __init__.py
│   ├── bot.py
│   ├── config.py
│   ├── web_server.py                       # aiohttp: OAuth + Midtrans webhook + WebApp
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   ├── messages.py
│   │   ├── categories.py
│   │   ├── budgets.py
│   │   ├── onboarding.py
│   │   ├── auth.py
│   │   ├── premium.py                      # NEW: /premium, /statuspremium, /cancel
│   │   └── payments.py                     # NEW: Stars handlers + Midtrans webhook
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transaction_service.py
│   │   ├── parser_service.py
│   │   ├── report_service.py
│   │   ├── budget_service.py
│   │   ├── ocr_service.py                  # NEW: Gemini Vision OCR
│   │   ├── recurring_service.py            # NEW: Recurring tx cron + reminders
│   │   ├── insight_service.py              # NEW: AI spending insights
│   │   └── subscription_service.py         # NEW: State machine, trial, auto-renew
│   ├── sheets/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── setup.py
│   │   ├── transactions.py
│   │   ├── categories.py
│   │   ├── budgets.py
│   │   └── dashboard.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oauth.py
│   │   ├── token_store.py                  # Updated: + subscriptions + invoices tables
│   │   └── encryption.py
│   ├── payments/
│   │   ├── __init__.py
│   │   ├── stars.py                        # Telegram Stars integration
│   │   ├── midtrans.py                     # Midtrans client + webhook verify
│   │   └── models.py                       # Subscription dataclass
│   ├── middleware/
│   │   └── premium_gate.py                 # NEW: @premium_required decorator
│   └── cache/
│       └── memory_cache.py
├── static/
│   └── login.html
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Cost Analysis & Revenue Projection

### Developer Costs

| Layanan | Free Tier (<500 user) | Scale (500-2000 user) |
|---|---|---|
| Hosting (Railway) | Rp 0 (Free) | ~Rp 75.000/bln (Hobby) |
| SQLite storage | Rp 0 | Rp 0 |
| Google Sheets API | Rp 0 (per-user quota) | Rp 0 |
| Google OAuth | Rp 0 | Rp 0 |
| **Subtotal** | **Rp 0** | **Rp 75.000** |

### Premium Feature Costs (Variable, per Premium User)

| Layanan | Cost per Use | Usage per User/Month | Cost per User/Month |
|---|---|---|---|
| Gemini Flash OCR (struk) | ~Rp 30/call | 30 OCR | ~Rp 900 |
| AI Insight (LLM call) | ~Rp 50/call | 4 insights | ~Rp 200 |
| Midtrans fee (% transaksi) | 2-3% | Rp 25.000 | ~Rp 625 |
| Telegram Stars commission | ~5% | Rp 25.000 | ~Rp 1.250 |
| **Subtotal per premium user** | | | **~Rp 2.975** |

### Revenue Projection

| Skenario | User Total | 5% Premium | Revenue/Bulan | Cost/Bulan | **Profit/Bulan** |
|---|---|---|---|---|---|
| **Launch** | 100 | 5 | Rp 125.000 | Rp 0 (hosting free) + Rp 15.000 (API) | **Rp 110.000** |
| **Growth** | 500 | 25 | Rp 625.000 | Rp 75.000 (hosting) + Rp 75.000 (API) | **Rp 475.000** |
| **Scale** | 2000 | 100 | Rp 2.500.000 | Rp 75.000 (hosting) + Rp 300.000 (API) | **Rp 2.125.000** |
| **Established** | 10.000 | 500 | Rp 12.500.000 | Rp 150.000 (hosting) + Rp 1.500.000 (API) | **Rp 10.850.000** |

> **Catatan:** Estimasi konservatif. 5% conversion rate realistic untuk freemium model Indonesia. Lifetime plans (Rp 750k) mempercepat cash flow di awal.

---

## Arsitektur 3-Way Comparison (Updated)

| Aspek | PostgreSQL | 1 Sheet Dev (SA) | **Per-User OAuth (INI)** |
|---|---|---|---|
| Privacy | Developer lihat data | Developer lihat data | **Zero data liability** |
| User trust | Rendah | Rendah | **Tinggi** |
| Monetization ready | ❌ (perlu tier di kode) | ❌ (sulit tier tanpa lihat data) | **✅ Tier mudah karena data per-user + premium gate di kode** |
| Dashboard visual | ✗ | ✗ | **✅ Native Sheets charts** |
| Cost developer (free) | $7-15/bln | Rp 0 | **Rp 0** |
| Revenue potential | N/A | N/A | **Rp 1.25jt/bln (1000 user)** |

---

## Status

- **Proposed:** 2026-06-21
- **Pivot v1 (PostgreSQL → Google Sheets SA):** 2026-06-21
- **Pivot v2 (SA → Per-User OAuth):** 2026-06-21
- **UX Pivot (Onboarding + Dashboard):** 2026-06-21
- **Monetization Pivot (Freemium Premium Tier):** 2026-06-21 ← **CURRENT**
- **Applied:** _[awaiting OpenSpec apply phase]_
- **Archived:** _[future]_

---

## Appendix A: Message Parser Design

_(Tidak berubah — lihat spec sebelumnya. Amount normalization, category keyword mapping — identik.)_

---

## Appendix B: Simplified Onboarding Flow (Updated with Premium Trial)

```
── DETIK 0 ──
User: /start
Bot:  "Halo! 👋 Aku asisten keuangan pribadi kamu.
       Catat pengeluaran, auto-rekap, gratis selamanya.
       [🚀 Mulai]"

── DETIK 5 ──
User: taps [🚀 Mulai]
Bot:  "Siapa nama panggilan kamu? (bisa skip)"

── DETIK 15 ──
User: "Budi"
Bot:  "Hai Budi! 🙌

       💡 Data kamu aman di Google Sheet milikmu sendiri.
       [🔐 Login Google (30 detik)]  [📱 Mode Offline]"

── DETIK 30 ──
User: taps [🔐 Login Google]
Bot:  "🔄 Membuka halaman login..."
       [Telegram Mini App → Google OAuth → auto-callback → 30 detik]

── DETIK 60 ──
Bot:  "✅ Login berhasil! 📊 Spreadsheet siap.

       🎁 BONUS: Mau coba PREMIUM gratis 7 hari?
       ✨ Fitur premium: lihat Appendix E
       
       [🎁 Coba Premium Gratis]  [⏭ Nanti aja]

       (Bisa di-upgrade kapan aja. Gak ada kartu kredit.)"

── DETIK 75 ──
User: taps [🎁 Coba Premium Gratis]
Bot:  "🎉 Premium GRATIS 7 hari AKTIF! ⭐
       Nikmati semua fitur: dashboard full, history unlimited,
       budget unlimited, dan lainnya.
       
       Sekarang coba catat transaksi pertama kamu 👇
       [✏️ Coba catat transaksi pertama]"

── DETIK 90 ──
User: taps [✏️ Coba catat] → "makan siang 50rb"
Bot:  "✅ Tercatat: 🍔 Makanan — Rp 50.000 ⭐ Premium
       📊 Hari ini: Rp 50.000 (1 transaksi)"

── TOTAL: ~90 DETIK ──
```

**Day 5 reminder:** Bot kirim: "⏰ Premium gratis tinggal 2 hari. Mau lanjut? /premium"

---

## Appendix C: Open Questions (Updated)

1-14. _(Open questions sebelumnya tetap valid)_
15. **Telegram Stars settlement:** Bagaimana timing settlement ke developer di Indonesia? Perlu rekening bank? Research.
16. **Midtrans KYC:** Midtrans perlu dokumen bisnis (SIUP, NPWP) untuk akun production. Apakah bisa pakai akun pribadi dulu? Alternatif: Xendit (lebih mudah untuk individu).
17. **OCR cost optimization:** Gemini Flash vs Claude Haiku vs GPT-4o-mini — mana paling murah + akurat untuk struk Bahasa Indonesia? Benchmark.
18. **Trial abuse prevention:** Rate-limit 1 trial per Telegram ID. Cukup? Atau perlu device fingerprinting?
19. **Premium churn rate:** Target <10% monthly churn. Monitoring + win-back campaign (diskon 20% untuk user yang cancel).
20. **Multi-currency implementation:** Pakai Google Finance formula di sheet (`=GOOGLEFINANCE("CURRENCY:USDIDR")`) atau API call ke exchangerate-api.com? Yang mana lebih reliable?

---

## Appendix D: Dashboard Specification

_(Tidak berubah — Free: basic ringkasan aja. Premium: full dengan charts, sparklines, conditional formatting — layout + pseudocode identik dengan spec sebelumnya.)_

---

## Appendix E: Premium Feature Technical Specs (NEW)

### E.1 — OCR Receipt Scanner

```
User: kirim foto struk ke bot (Telegram Photo message)
  │
  ▼
Bot: OCRService.scan(photo_file_id, user_id)
  │
  ├── Download photo dari Telegram server
  ├── Encode ke base64
  ├── Kirim ke Gemini Flash API:
  │   Prompt: "Extract receipt data. Return JSON:
  │   {merchant, total_amount, date_iso, items: [{name, amount}],
  │    currency, category_suggestion}. All fields optional.
  │    Language: Indonesian."
  │
  ├── Parse JSON response
  ├── Map category_suggestion ke kategori terdekat user
  ├── Return: {amount, category_id, date, description, confidence}
  │
  └── Confidence < 0.5 → tanya user: "Gak yakin nih. Ini struk apa?"
      Confidence >= 0.5 → konfirmasi: "Indomaret, Rp 85.000. Simpan?"
        │
        ├── User: [Ya] → TransactionService.create(...)
        └── User: [Edit] → user koreksi via inline edit
```

**API:** Gemini 2.0 Flash (`gemini-2.0-flash-001`). Cost: ~Rp 20-50 per image (512x512, prompt token + image token).

**Limit:** 30 OCR/bulan untuk Premium. Counter di SQLite subscriptions table.

### E.2 — Recurring Transactions & Bill Reminders

```
Setup flow:
  /tagihan → "Nama tagihan?" → "WiFi"
           → "Jumlah?" → "350000"
           → "Kategori?" → [🍔 Makanan] [💡 Tagihan] ...
           → "Frekuensi?" → [📅 Bulanan] [📆 Mingguan] [🗓 Tahunan]
           → "Tanggal?" → "5" (tiap tanggal 5)
           → "Ingatkan?" → [H-1] [H-3] [H-7] [Tidak]

Cron job (PTB JobQueue, tiap jam):
  for each recurring_tx where due_today AND not_executed_today:
      TransactionService.create(amount, category, type='expense', date=today,
                                 description=f"[Auto] {recurring_tx.name}")
      mark recurring_tx as executed_today

Reminder job (PTB JobQueue, tiap jam 7 pagi):
  for each recurring_tx where due_tomorrow:
      bot.send_message(user_id, "📅 Besok bayar {name} Rp {amount} ya.")
```

**Data model (in-memory + SQLite):**

```sql
CREATE TABLE recurring_transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   BIGINT NOT NULL,
    name          TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    category_id   INTEGER NOT NULL,
    frequency     TEXT NOT NULL CHECK (frequency IN ('daily','weekly','monthly','yearly')),
    day_of_month  INTEGER,          -- untuk monthly/yearly
    day_of_week   INTEGER,          -- untuk weekly
    remind_before INTEGER DEFAULT 1, -- H-berapa
    last_executed TEXT,             -- ISO8601
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

### E.3 — Payment State Machine Implementation

```python
# src/services/subscription_service.py

class SubscriptionState:
    NONE = "none"
    PENDING = "pending"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    TRANSITIONS = {
        NONE:     [PENDING],
        PENDING:  [ACTIVE, EXPIRED],
        ACTIVE:   [GRACE, EXPIRED, CANCELLED],
        GRACE:    [ACTIVE, EXPIRED],
        EXPIRED:  [PENDING],
        CANCELLED: [PENDING],
    }

async def create_subscription(telegram_id, plan, payment_method):
    """Create pending subscription + invoice record"""
    ...

async def activate_subscription(telegram_id, payment_ref):
    """Move PENDING → ACTIVE, set start_date + end_date"""
    ...

async def handle_expiry_check():
    """Cron: check all ACTIVE subscriptions, move to GRACE/EXPIRED"""
    ...

async def start_free_trial(telegram_id):
    """Create 7-day trial subscription (trial_end = now + 7 days)"""
    ...
```

### E.4 — Premium Gate Decorator

```python
# src/middleware/premium_gate.py

def premium_required(feature_name: str):
    """Decorator untuk handler yang hanya bisa diakses premium user."""
    def decorator(handler_func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            sub = await subscription_service.get_active_subscription(user_id)
            if sub and sub.status in ('active', 'trial'):
                return await handler_func(update, context)
            else:
                await update.message.reply_text(
                    f"🔒 *{feature_name}* adalah fitur Premium.\n\n"
                    f"⭐ Upgrade sekarang mulai Rp 25.000/bulan!\n"
                    f"Ketik /premium untuk lihat paket.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⭐ Upgrade ke Premium", callback_data="premium_upgrade"),
                        InlineKeyboardButton("📋 Lihat fitur Premium", callback_data="premium_features"),
                    ]])
                )
        return wrapper
    return decorator

# Usage:
@premium_required("OCR Scanner")
async def handle_ocr_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...
```

### E.5 — Telegram Stars Payment Handler

```python
# src/handlers/payments.py

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate incoming pre-checkout query from Telegram Stars."""
    query = update.pre_checkout_query
    # Verify payload matches our subscription intent
    payload = json.loads(query.invoice_payload)
    if payload.get('type') == 'premium_subscription':
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid payment")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Payment berhasil via Telegram Stars."""
    payment = update.message.successful_payment
    payload = json.loads(payment.invoice_payload)
    user_id = update.effective_user.id

    await subscription_service.activate_subscription(
        telegram_id=user_id,
        payment_ref=payment.telegram_payment_charge_id,
    )

    await update.message.reply_text(
        "✅ Pembayaran berhasil!\n"
        "⭐ Premium kamu udah AKTIF!\n"
        f"📅 Berlaku sampai: {get_end_date()}\n\n"
        "Selamat menikmati semua fitur premium! 🎉"
    )
```
