# Panduan Setup Akun Layanan Eksternal

Dokumen ini menjelaskan langkah demi langkah untuk menyiapkan semua akun dan layanan eksternal yang dibutuhkan oleh **Asisten Keuangan Telegram Bot**.

Ikuti urutan di bawah ini. Setiap bagian mencakup perintah yang bisa langsung di-*copy-paste* dan placeholder screenshot agar dokumentasi bisa ditambahkan gambar nanti.

---

## 1. Google Cloud Console

Aplikasi ini menggunakan Google Sheets sebagai database pribadi pengguna. Kita membutuhkan project Google Cloud dengan OAuth 2.0 agar pengguna bisa memberikan izin akses ke spreadsheet miliknya.

### 1.1 Buat Project Baru

1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Pastikan akun Google yang aktif adalah akun pengembang utama.
3. Klik dropdown project di bagian atas, lalu pilih **New Project**.
4. Isi:
   - **Project name**: `personal-finance-bot`
   - **Location**: `No organization` (atau organisasi jika ada)
5. Klik **Create**.

[SCREENSHOT: Halaman pembuatan project baru di Google Cloud Console dengan nama project personal-finance-bot]

### 1.2 Aktifkan API yang Dibutuhkan

Buka halaman berikut satu per satu dan klik **Enable**:

- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)

[SCREENSHOT: Tombol Enable pada Google Sheets API di API Library]

### 1.3 Konfigurasi OAuth Consent Screen

1. Buka menu **APIs & Services > OAuth consent screen**.
2. Pilih **External**, lalu klik **Create**.
3. Isi bagian **App information**:
   - **App name**: `Asisten Keuangan`
   - **User support email**: pilih email pengembang
   - **Developer contact information**: email pengembang
4. Klik **Save and Continue**.
5. Pada langkah **Scopes**, klik **Add or Remove Scopes**.
6. Centang scope berikut:
   - `.../auth/drive.file` (Google Drive API)
7. Klik **Update**, lalu **Save and Continue**.
8. Pada langkah **Test users**, klik **Add Users** dan masukkan email Google yang akan digunakan untuk uji coba OAuth.
9. Klik **Save and Continue**, lalu **Back to Dashboard**.

> Catatan: Karena menggunakan **External + Testing mode**, hanya email test user yang bisa login sampai aplikasi dipublikasikan ( Publishing status diset ke **In production**).

[SCREENSHOT: Halaman OAuth consent screen dengan User Type External yang dipilih]

[SCREENSHOT: Daftar scopes OAuth dengan drive.file dicentang]

### 1.4 Buat OAuth 2.0 Client ID

1. Buka menu **APIs & Services > Credentials**.
2. Klik **Create Credentials > OAuth client ID**.
3. Pada **Application type**, pilih **Web application**.
4. Isi **Name**: `Telegram Bot Web Client`.
5. Tambahkan **Authorized redirect URIs**:
   - `https://your-domain.com/oauth/callback`
   - `urn:ietf:wg:oauth:2.0:oob`
6. Klik **Create**.
7. Klik **Download JSON**.
8. Simpan file tersebut sebagai `client_secret.json` di root project.

[SCREENSHOT: Form pembuatan OAuth 2.0 Client ID dengan redirect URI yang sudah diisi]

### 1.5 Ekstrak CLIENT_ID dan CLIENT_SECRET

Setelah file `client_secret.json` diunduh, jalankan perintah berikut untuk mengekstrak nilai yang dibutuhkan:

```bash
python - << 'PY'
import json
with open('client_secret.json') as f:
    data = json.load(f)
client = data['web']
print('GOOGLE_CLIENT_ID=', client['client_id'], sep='')
print('GOOGLE_CLIENT_SECRET=', client['client_secret'], sep='')
print('REDIRECT_URIS=', client['redirect_uris'], sep='')
PY
```

Salin nilai `GOOGLE_CLIENT_ID` dan `GOOGLE_CLIENT_SECRET` untuk dimasukkan ke environment variables nanti.

---

## 2. Telegram @BotFather

Bot Telegram dibuat dan dikonfigurasi melalui akun resmi `@BotFather`.

### 2.1 Buat Bot Baru

1. Buka aplikasi Telegram dan cari kontak `@BotFather`.
2. Klik **START**, lalu kirim perintah:

```text
/newbot
```

3. Masukkan nama bot:

```text
Asisten Keuangan
```

4. Masukkan username bot. Username harus diakhiri dengan `bot` dan bersifat unik. Contoh:

```text
asistenkeuangan_saya_bot
```

5. BotFather akan mengirimkan pesan sukses yang berisi **token bot**. Simpan token tersebut, contoh:

```text
123456789:ABCdefGHIjklMNOpqrSTUvwxyz
```

[SCREENSHOT: Chat BotFather setelah berhasil membuat bot dengan token yang disorot]

### 2.2 Atur Daftar Perintah Bot

Kirim perintah berikut ke `@BotFather`:

```text
/setcommands
```

Pilih bot yang baru dibuat, lalu kirim daftar perintah berikut persis seperti ini:

```text
start - Mulai bot dan onboarding
login - Login dengan akun Google
logout - Putuskan koneksi Google
masuk - Catat pemasukan
keluar - Catat pengeluaran
laporan - Lihat laporan keuangan
dashboard - Buka dashboard Google Sheet
kategori - Atur kategori
budget - Atur budget bulanan
tagihan - Atur transaksi berulang (Premium)
ocr - Scan struk/foto (Premium)
insight - Analisis keuangan AI (Premium)
premium - Upgrade ke Premium
statuspremium - Cek status langganan
cancel - Batalkan langganan
perbaiki - Perbaiki dashboard yang rusak
export - Download data CSV
hapusdata - Hapus semua data
bahasa - Ganti bahasa
bantuan - Panduan penggunaan
```

[SCREENSHOT: Chat BotFather saat mengirimkan setcommands dengan daftar perintah]

### 2.3 Aktifkan Pembayaran

Bot mendukung pembayaran Premium melalui Telegram Payments.

1. Kirim perintah ke `@BotFather`:

```text
/mybots
```

2. Pilih bot `Asisten Keuangan`.
3. Pilih menu **Payments**.
4. Pilih provider pembayaran yang ingin digunakan, misalnya **Stripe** atau **Telegram Stars**.
5. Ikuti instruksi dari BotFather untuk menghubungkan akun pembayaran.
6. Setelah selesai, simpan **payment provider token** yang diberikan.

[SCREENSHOT: Menu Payments di BotFather dengan provider yang sudah dipilih]

---

## 3. Midtrans Sandbox

Midtrans digunakan untuk memproses pembayaran langganan Premium.

### 3.1 Daftar dan Buat Project

1. Buka [Midtrans Sandbox Dashboard](https://dashboard.sandbox.midtrans.com/).
2. Daftar akun baru atau login.
3. Setelah masuk dashboard, buat project baru, misalnya:
   - **Project name**: `personal-finance-bot-sandbox`
4. Buka halaman **Settings > Access Keys**.
5. Simpan **Server Key** dan **Client Key**.

[SCREENSHOT: Halaman Access Keys di Midtrans Sandbox dengan Server Key dan Client Key]

### 3.2 Konfigurasi Webhook

1. Di dashboard Midtrans, buka menu **Settings > Configuration**.
2. Pada bagian **Notification URL**, isi:

```text
https://your-domain.com/payments/midtrans/webhook
```

3. Simpan perubahan.

[SCREENSHOT: Form Notification URL di Midtrans dengan webhook URL yang sudah diisi]

### 3.3 Verifikasi dengan cURL

Ganti `<SERVER_KEY>` dengan Server Key Midtrans Sandbox Anda, lalu jalankan:

```bash
curl -X GET "https://api.sandbox.midtrans.com/v1/status/TEST-ORDER-ID" \
  -H "Accept: application/json" \
  -H "Authorization: Basic $(echo -n '<SERVER_KEY>:' | base64)"
```

Jika kredensial valid, respons akan berupa JSON status transaksi (walaupun order ID tidak ditemukan, respons 401 tidak muncul). Contoh respons yang menandakan koneksi berhasil:

```json
{
  "status_code": "404",
  "status_message": "Transaction doesn't exist.",
  "id": "TEST-ORDER-ID"
}
```

[SCREENSHOT: Terminal yang menampilkan respons curl Midtrans Sandbox]

---

## 4. Google Gemini API

Gemini digunakan untuk fitur **insight keuangan AI** (Premium).

### 4.1 Dapatkan API Key

1. Buka [Google AI Studio](https://aistudio.google.com/).
2. Login dengan akun Google yang sama dengan project Google Cloud.
3. Klik menu **Get API key**.
4. Klik **Create API key**.
5. Pilih project `personal-finance-bot` yang sudah dibuat sebelumnya.
6. Simpan API key yang muncul.

[SCREENSHOT: Halaman API Keys di Google AI Studio dengan key yang baru dibuat]

### 4.2 Verifikasi Akses Model

Pastikan model `gemini-2.0-flash-001` tersedia. Ganti `<GEMINI_API_KEY>` dengan API key Anda, lalu jalankan:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-001?key=<GEMINI_API_KEY>"
```

Respons yang berhasil akan menampilkan metadata model seperti `name`, `version`, dan `supportedGenerationMethods`.

[SCREENSHOT: Terminal yang menampilkan metadata model gemini-2.0-flash-001]

### 4.3 Catatan Mengenai Free Tier

- Free tier Gemini memiliki batasan jumlah request per menit dan per hari.
- Pantau penggunaan di menu **Quota** pada Google AI Studio.
- Untuk produksi dengan banyak pengguna Premium, pertimbangkan untuk upgrade ke tier berbayar.

---

## 5. Deploy Options (Railway / Render)

Setelah kode siap, deploy bot ke platform cloud. Pilih salah satu platform berikut.

### 5.1 Deploy ke Railway

1. Buka [Railway](https://railway.app/) dan login dengan akun GitHub.
2. Klik **New Project**.
3. Pilih **Deploy from GitHub repo**, lalu pilih repository `personal-finance-bot`.
4. Setelah project dibuat, buka menu **Variables**.
5. Tambahkan semua environment variables sesuai checklist di bagian 6.
6. Railway akan otomatis deploy setiap kali ada push ke branch utama.
7. Salin public domain Railway Anda, misalnya:

```text
https://personal-finance-bot-production.up.railway.app
```

8. Pastikan `WEBHOOK_URL` mengarah ke domain tersebut.

[SCREENSHOT: Dashboard Railway dengan tab Variables yang sudah terisi]

### 5.2 Deploy ke Render

1. Buka [Render](https://render.com/) dan login.
2. Klik **New > Web Service**.
3. Pilih repository GitHub project ini.
4. Isi konfigurasi deploy:
   - **Name**: `personal-finance-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m src.bot`
5. Klik **Advanced** dan tambahkan semua environment variables sesuai checklist di bagian 6.
6. Klik **Create Web Service**.
7. Tunggu deploy selesai, lalu salin URL layanan, misalnya:

```text
https://personal-finance-bot.onrender.com
```

8. Pastikan `WEBHOOK_URL` mengarah ke URL tersebut.

[SCREENSHOT: Form pembuatan Web Service di Render dengan build command dan start command yang sudah diisi]

### 5.3 Catatan Penting Webhook URL

`WEBHOOK_URL` harus selalu mengarah ke URL deployment aktual. Contoh:

```text
https://your-domain.com/webhook
```

Jangan gunakan `localhost` untuk webhook Telegram atau Midtrans karena kedua layanan tersebut tidak bisa mengirim request ke mesin lokal.

---

## 6. Final Checklist

Setelah semua layanan di atas selesai disiapkan, pastikan kredensial berikut sudah didapat dan disimpan dengan aman.

| Kredensial | Sumber | Tempat Penyimpanan |
|------------|--------|--------------------|
| `GOOGLE_CLIENT_ID` | Google Cloud Console > OAuth client ID | Environment variable / `.env` |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console > OAuth client ID | Environment variable / `.env` |
| `GOOGLE_REDIRECT_URI` | OAuth client ID redirect URIs | Environment variable / `.env` |
| `TELEGRAM_BOT_TOKEN` | @BotFather setelah `/newbot` | Environment variable / `.env` |
| `TELEGRAM_PAYMENT_PROVIDER_TOKEN` | @BotFather > Payments | Environment variable / `.env` (opsional) |
| `MIDTRANS_SERVER_KEY` | Midtrans Sandbox > Access Keys | Environment variable / `.env` |
| `MIDTRANS_CLIENT_KEY` | Midtrans Sandbox > Access Keys | Environment variable / `.env` |
| `MIDTRANS_WEBHOOK_URL` | Midtrans Sandbox > Notification URL | Environment variable / `.env` |
| `GEMINI_API_KEY` | Google AI Studio > API Keys | Environment variable / `.env` |
| `WEBHOOK_URL` | Railway / Render public URL | Environment variable / `.env` |

### Verifikasi Akhir

#### a. Verifikasi Telegram Bot

Ganti `<TELEGRAM_BOT_TOKEN>` dengan token bot Anda, lalu jalankan:

```bash
curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getMe"
```

Respons yang diharapkan:

```json
{
  "ok": true,
  "result": {
    "id": 123456789,
    "is_bot": true,
    "first_name": "Asisten Keuangan",
    "username": "asistenkeuangan_saya_bot"
  }
}
```

[SCREENSHOT: Terminal yang menampilkan respons getMe dari Telegram Bot API]

#### b. Verifikasi Midtrans

Ulangi perintah dari bagian 3.3 dan pastikan tidak ada error autentikasi.

#### c. Verifikasi OAuth Secara Manual

1. Jalankan aplikasi bot di lokal atau deployment.
2. Buka URL berikut di browser, ganti `<CLIENT_ID>` dan `<REDIRECT_URI>`:

```text
https://accounts.google.com/o/oauth2/v2/auth?client_id=<CLIENT_ID>&redirect_uri=<REDIRECT_URI>&response_type=code&scope=https://www.googleapis.com/auth/drive.file&access_type=offline&prompt=consent
```

3. Pilih akun Google test user.
4. Pastikan muncul halaman izin aplikasi dengan scope **Google Drive file metadata** atau serupa.
5. Setelah menyetujui, browser akan dialihkan ke redirect URI dengan parameter `?code=...`.

[SCREENSHOT: Halaman persetujuan OAuth Google yang meminta izin akses Google Drive file]

---

## Catatan Tambahan

- Jangan pernah mengunggah file `client_secret.json` atau isi `.env` ke repository publik.
- Gunakan GitHub Secrets atau fitur Environment Variables di platform deploy jika tersedia.
- Untuk produksi, publikasikan OAuth consent screen Google dari **Testing** ke **In production** setelah melalui proses verifikasi Google.
- Midtrans Sandbox digunakan untuk development dan uji coba. Untuk produksi, gunakan akun Midtrans Production dan ubah URL API dari `api.sandbox.midtrans.com` ke `api.midtrans.com`.

Selamat mengembangkan!
