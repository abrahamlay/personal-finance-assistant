# Asisten Keuangan — Personal Finance Bot

Asisten Keuangan adalah bot Telegram yang membantu kamu mencatat pemasukan & pengeluaran harian secara otomatis. Data disimpan di Google Sheet milik kamu sendiri, jadi tetap privat dan bisa diakses kapan saja.

## Fitur Utama

- **Pencatatan cepat**: ketik `makan siang 50rb`, bot langsung mencatat.
- **Google Sheet integration**: data kamu tersimpan rapi di sheet pribadi.
- **Laporan harian, mingguan, bulanan** dengan grafik.
- **Budget & kategori** custom sesuai kebutuhan.
- **Premium**: OCR scan struk, tagihan rutin + pengingat, dan insight AI.

## Tech Stack

- Python 3.12+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (PTB)
- Google Sheets API + OAuth 2.0
- Google Gemini AI
- Midtrans (QRIS / GoPay)
- Telegram Stars
- SQLite + Fernet encryption
- Matplotlib untuk chart

## Environment Variables

Salin `.env.example` ke `.env` dan isi variabel berikut:

```bash
TELEGRAM_TOKEN=          # Bot token dari @BotFather
GOOGLE_CLIENT_ID=        # Google OAuth Client ID
GOOGLE_CLIENT_SECRET=    # Google OAuth Client Secret
OAUTH_REDIRECT_URI=      # Contoh: http://localhost:8080/oauth/callback
FERNET_KEY=              # Key untuk enkripsi token (32 url-safe base64 bytes)
GEMINI_API_KEY=          # Google Gemini API key (untuk OCR & insight)
MIDTRANS_SERVER_KEY=     # Opsional, untuk pembayaran QRIS/GoPay
MIDTRANS_CLIENT_KEY=     # Opsional, untuk pembayaran QRIS/GoPay
```

> Lihat panduan lengkap setup Google OAuth, Gemini, dan Midtrans di `docs/setup-external-services.md`.

## Quick Start

```bash
# 1. Clone dan buat virtual environment
git clone <repo-url>
cd personal-finance-bot
python -m venv .venv

# 2. Aktifkan environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Isi file .env
# cp .env.example .env

# 5. Jalankan bot
python -m src.bot
```

Bot akan menjalankan:
- Polling Telegram di foreground
- Web server di port `8080` untuk OAuth callback dan webhook Midtrans

## Project Structure

```
personal-finance-bot/
├── src/
│   ├── bot.py                 # Entry point & handler registration
│   ├── config.py              # Settings dari environment variables
│   ├── web_server.py          # aiohttp web server (OAuth/Midtrans)
│   ├── auth/                  # OAuth, token store, encryption
│   ├── cache/                 # In-memory dedup cache
│   ├── handlers/              # Telegram command & message handlers
│   ├── middleware/            # @require_login, @premium_required
│   ├── payments/              # Telegram Stars & Midtrans
│   ├── services/              # Business logic (OCR, insight, recurring, dll)
│   └── sheets/                # Google Sheets operations
├── tests/                     # Test suite (pytest)
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Commands Reference

### Free Commands

| Command | Deskripsi |
|---------|-----------|
| `/start` | Mulai wizard onboarding |
| `/login` | Sambungkan Google Sheet |
| `/logout` | Putuskan koneksi Google |
| `/bantuan` | Daftar semua perintah |
| `/catat` | Panduan input transaksi |
| `/hariini` | Ringkasan transaksi hari ini |
| `/mingguan` | Laporan minggu ini + grafik |
| `/bulanan` | Laporan bulan ini |
| `/dashboard` | Buka dashboard Google Sheet |
| `/perbaiki` | Regenerasi dashboard |
| `/kategori` | Atur kategori |
| `/anggaran` | Atur budget |
| `/edit <id> <field> <value>` | Edit transaksi |
| `/hapus <id>` | Hapus transaksi |
| `/premium` | Lihat paket premium |
| `/statuspremium` | Cek status langganan |

### Premium Commands

| Command | Deskripsi |
|---------|-----------|
| `/ocr` | Scan struk belanja via foto |
| `/tagihan` | Tambah tagihan rutin |
| `/reminder` | Lihat tagihan mendatang |
| `/insight` | Analisis keuangan AI |

### Natural Input

Kamu bisa langsung ketik transaksi tanpa command:

```
makan siang 50rb
bensin 100rb
gaji 5jt
wifi bulanan 300rb
```

## Free vs Premium

| Fitur | Free | Premium |
|-------|------|---------|
| Pencatatan transaksi | ✅ | ✅ |
| Laporan harian/mingguan/bulanan | ✅ | ✅ |
| Kategori default | ✅ 13 kategori | ✅ semua kategori |
| Custom kategori | 5 kategori | Unlimited |
| Budget | 1 budget | Unlimited |
| OCR scan struk | ❌ | ✅ 30 scan/bulan |
| Tagihan rutin + reminder | 3 tagihan | Unlimited |
| Insight AI | ❌ | ✅ |
| Dashboard premium charts | ❌ | ✅ |

## Deployment Notes

- Pastikan `OAUTH_REDIRECT_URI` cocok dengan Google OAuth console.
- Gunakan webhook jika men-deploy ke server publik (atur `WEBHOOK_URL`).
- Untuk production, gunakan database persistent (token_store.db akan dibuat otomatis).

## Testing

```bash
# Jalankan semua test
pytest -v

# Dengan coverage
pytest --cov=src --cov-report=term-missing
```

Target coverage: ≥80%.

## License

MIT
