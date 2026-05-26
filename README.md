# NARA — Chatbot Permasalahan IT BPS

> **N**extGen → Teknologi modern dan inovatif
> **A**I → Kecerdasan buatan sebagai mesin utama
> **R**esponse → Fokus menjawab dan merespons kebutuhan pengguna
> **A**gent → Asisten digital yang bertindak atas nama layanan

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Bridge-25D366?logo=whatsapp)](https://whatsapp.com)
[![E5-base](https://img.shields.io/badge/Embedding-E5--base-orange)](https://huggingface.co/intfloat/multilingual-e5-base)

Asisten Q&A resmi **BPS Provinsi Kepulauan Bangka Belitung**. Melayani pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026** via Telegram & WhatsApp.

> **Stack:** FastAPI + E5-base (semantic search) + BM25 (domain filter) + Multi-LLM failover + SQLite + EasyOCR
> **Model:** Cloud (OpenAI-compatible) → Ollama lokal — auto failover

---

## 📋 Daftar Isi

- [✨ Fitur](#-fitur)
- [🔒 Security & Proteksi](#-security--proteksi)
- [🧠 Arsitektur Modular](#-arsitektur-modular)
- [🔄 Replikasi / Custom Bot](#-replikasi--custom-bot)
- [💻 Panduan Instalasi — Windows](#-panduan-instalasi--windows)
- [🐧 Panduan Instalasi — Linux](#-panduan-instalasi--linux)
- [🔗 API Endpoints](#-api-endpoints)
- [📊 Logging & Evaluasi](#-logging--evaluasi)
- [❓ FAQ](#-faq)

---

## ✨ Fitur

| Fitur | Detail |
|-------|--------|
| 🤖 **AI Answering** | Multi-LLM dengan failover chain. Coba provider 1 → error? auto lanjut provider 2 → dst. Cloud API (OpenAI-compatible) & Ollama lokal |
| 🧠 **Hybrid Search (BM25 + E5)** | Keyword overlap (BM25) untuk filter domain, semantic search (E5) untuk retrieval jawaban |
| 📱 **WhatsApp Integration** | Bridge via `whatsapp-web.js`. QR scan, typing indicator, kirim pesan biasa (bukan reply), support gambar + OCR |
| ✈️ **Telegram Bot** | Reply keyboard, typing indicator, "⏳ Memproses gambar..." untuk image processing (auto-hapus setelah jawaban datang) |
| 🗣️ **OCR Gambar** | Screenshot/foto dibaca otomatis pakai EasyOCR. Support Indo + Inggris |
| 🔄 **Auto-Reload FAQ** | Download ulang dari Google Sheets tiap 10 menit. Bisa reload manual via `/reload` |
| 📜 **Chat History** | Semua percakapan tersimpan di SQLite — kolom `kendala` & `solusi` |
| 📊 **Query Logging** | Semua pertanyaan dicatat ke `query_log.jsonl` — BM25 score, status, jawaban |
| 🧠 **Multi-Part Split** | Pertanyaan dengan "dan", "serta", "lalu" dipisah otomatis. Bagian di luar BPS di-skip |
| 🧹 **Input Sanitasi** | Karakter kontrol dibuang, emoji dibatasi maks 5, panjang maks 500 karakter |
| 📝 **Markdown di Telegram** | Kirim **bold** dan *italic* via `ParseMode.MARKDOWN`. WhatsApp otomatis strip formatting biar bersih |

---

## 🔒 Security & Proteksi

Bot ini punya **6 lapis proteksi**:

| # | Lapisan | File | Cara Kerja |
|---|---------|------|------------|
| 1 | 🚫 **Anti-Spam** | `security/rate_limiter.py` | **5 request per menit** per user. Lewat? Block **5 menit**. Silent block setelah peringatan pertama |
| 2 | 📅 **Daily Chat Limit** | `server.py` | **25 chat per hari** per user. Reset otomatis tiap ganti hari (WIB) |
| 3 | 💬 **Session Timeout** | `security/session.py` | Session expired setelah **30 menit idle**. Watchdog tiap 15 detik, notif otomatis |
| 4 | 🎯 **BM25 Domain Filter** | `core/bm25.py` | Keyword overlap vs 79 FAQ. **Skor < 0.5?** Ditolak langsung tanpa LLM |
| 5 | 🔍 **E5 Score Threshold** | `server.py` | Skor cosine similarity < 0.82? Dianggap di luar domain — tolak |
| 6 | 👑 **Trusted User** | `security/rate_limiter.py` | User di `TRUSTED_CHAT_IDS` **skip anti-spam & daily limit** |

### Detail Threshold Domain Filter

| Pertanyaan | Contoh | BM25 Score | E5 Score | Hasil |
|------------|--------|:----------:|:---------:|:-----:|
| Tentang SOBAT / GC PLN / FASIH | "cara daftar SOBAT" | 4.60 | 0.86 | ✅ Dijawab |
| Tentang SE2026 | "se2026 prelist" | 3.68 | 0.89 | ✅ Dijawab |
| Di luar konteks BPS | "siapa presiden indonesia" | **0.00** | 0.80 | ❌ Ditolak |
| Di luar konteks BPS | "resep nasi goreng" | **0.00** | 0.77 | ❌ Ditolak |
| Multi-part campuran | "aktivasi FASIH dan siapa presiden" | ✅ + ❌ | — | ✅ Bagian FASIH dijawab, sisanya di-skip |

> **Catatan:** BM25 bekerja berdasarkan **keyword overlap**. Kata umum (stopwords) seperti "siapa", "bagaimana", "nama", "bapak", "ibu" dihapus sebelum perhitungan. Angka doang (tahun, nomor) juga difilter. Skor BM25 = 0 jika tidak ada satupun kata yang cocok dengan FAQ.

### Trusted User

User di `TRUSTED_CHAT_IDS` (dari `.env`) **tidak kena** anti-spam & daily limit. Tapi tetap kena session timeout.

### Input Sanitasi (Layer Awal)

- Control characters (`\x00-\x1f`) — dibuang
- Emoji > 5 — kelebihan dihapus
- Karakter > 500 — ditolak

### Perbedaan Format Pesan Telegram vs WhatsApp

| Fitur | Telegram | WhatsApp |
|-------|----------|----------|
| **Bold** | `**bold**` tampil tebal ✅ | `**bold**` → teks biasa (strip) |
| *Italic* | `*italic*` tampil miring ✅ | `*italic*` → teks biasa (strip) |
| `Code` | `` `code` `` tampil monospace ✅ | `` `code` `` → teks biasa (strip) |
| Gambar + OCR | "⏳ Memproses gambar..." → hapus → jawaban ✅ | typing indicator → jawaban ✅ |
| Image caption | Gabung caption + OCR text auto ✅ | Sama ✅ |
| Kirim pesan | `reply_text()` — balas ke pesan tertentu | `sendMessage()` — kirim pesan biasa (bukan reply) |
| Typing indicator | `send_action("typing")` | `chat.sendStateTyping()` → `chat.clearState()` |
| Session watchdog | 30 menit idle → notif Telegram | 30 menit idle → session dihapus (skip notif) |
- Pesan kosong setelah filtering — ditolak

---

## 🧠 Arsitektur Modular

```
chatbot-qna/
│
├── server.py                 ← FastAPI router — inti logika chatbot
├── telegram_bot.py           ← Layer Telegram (OCR, sanitasi, kirim API)
├── wa_handler.py             ← Layer WhatsApp (Flask, terima dari bridge)
├── start-all.bat             ← 1 klik buka 4 terminal
│
├── core/                     ← 🔧 Mesin utama
│   ├── database.py           ←   SQLite: init, log chat, query history
│   ├── embedder.py           ←   E5-base: load model, encode, semantic search
│   ├── bm25.py               ←   BM25 domain checker (keyword overlap, stopwords)
│   ├── llm.py                ←   Multi-provider LLM, failover chain, build prompt
│   └── query_logger.py       ←   Query evaluation logging (JSONL)
│
├── security/                 ← 🔒 Lapisan pengaman
│   ├── rate_limiter.py       ←   Anti-spam (5/menit), trusted user
│   └── session.py            ←   Session: timeout 30 menit, watchdog
│
├── prompts/                  ← 🎯 IDENTITAS & ATURAN (ganti untuk replikasi)
│   ├── identity.json         ←   Nama, role, topik (ubah ini saja untuk bot berbeda)
│   ├── system.md             ←   System prompt — aturan main LLM
│   └── greeting.md           ←   Template sapaan pertama
│
├── whatsapp-bridge/          ← 📱 Bridge WhatsApp
│   ├── bridge.js             ←   whatsapp-web.js client (QR scan, typing, image)
│   └── package.json          ←   Node.js dependencies
│
└── query_log.jsonl           ← 📊 Log evaluasi query (auto-generated)
```

### Alur Proses Chat

```
USER: "Kenapa mitra tidak bisa verifikasi nik dan siapa presiden?"
         │
         ▼
┌─ 1. INPUT SANITASI ──────────────────────────┐
│  Control chars, emoji, panjang, kosong       │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 2. ANTI-SPAM & DAILY LIMIT ────────────────┐
│  5 req/menit + 25 chat/hari                  │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 3. TYPING INDICATOR ──────────────────────┐
│  Telegram: bot.send_action("typing")       │
│  WhatsApp: chat.sendStateTyping()           │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 4. GREETING? ──────────────────────────────┐
│  "halo", "pagi" → langsung LLM, no search   │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 5. BM25 DOMAIN CHECK ──────────────────────┐
│  Keyword overlap vs 79 FAQ                  │
│  Score < 0.5? → TOLAK (gak lanjut ke LLM)   │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 6. MULTI-PART SPLIT ───────────────────────┐
│  Pisah "dan", "serta", "lalu"               │
│  Tiap bagian dicek BM25 + E5 independen     │
│  Bagian di luar domain → di-skip            │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 7. E5 SEMANTIC SEARCH ─────────────────────┐
│  Cosine similarity, top-3 FAQ               │
│  Score < 0.82? → dianggap gak relevan       │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 8. LLM ANSWER ─────────────────────────────┐
│  System prompt + context referensi          │
│  3 provider backup chain                    │
└───────────────────────────────────────────────┘
         │
         ▼
    ⚠️ QUERY LOGGED (query_log.jsonl)
```

---

## 🔄 Replikasi / Custom Bot

| File | Wajib? | Keterangan |
|------|:------:|------------|
| `.env` | ✅ **Wajib** | Sesuaikan token, API key, model |
| `prompts/identity.json` | ✅ **Wajib** | Nama & role bot baru |
| `prompts/system.md` | ⬜ Opsional | Aturan main LLM |
| `prompts/greeting.md` | ⬜ Opsional | Template sambutan |
| `core/embedder.py` | ⬜ Opsional | Bisa ganti model embedder |
| `core/bm25.py` | ⬜ Opsional | Stopwords disesuaikan domain |
| `security/*.py` | ❌ **Jangan** | Proteksi built-in |

---

## 💻 Panduan Instalasi — Windows

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **Node.js** | v20 LTS (v24 mungkin bermasalah dengan puppeteer) |
| **RAM** | Minimal 4GB (8GB untuk OCR + E5) |

### 1. Install Python

1. Buka [python.org/downloads](https://www.python.org/downloads/release/python-3119/)
2. Download **Windows installer (64-bit)**
3. ✅ Centang **Add Python to PATH** → Install Now
4. Verifikasi: `python --version`

### 2. Install Node.js

Download dari [nodejs.org](https://nodejs.org/) — pilih **v20 LTS**.

Verifikasi: `node --version` (harus v20.x.x)

### 3. Install Git & Clone

```cmd
winget install git.git
cd C:\Proyek
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 4. Buat file `.env`

```env
TELEGRAM_BOT_TOKEN=isi_token_telegram
CHATBOT_URL=http://localhost:8000/chat
GSHEET_CSV_URL=https://docs.google.com/spreadsheets/d/.../pub?...&output=csv

# LLM 1 — Utama
LLM_API_1=https://opencode.ai/zen/go/v1/chat/completions
LLM_API_KEY_1=sk-...
LLM_MODEL_1=deepseek-v4-flash

# LLM 2 — Cadangan
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-...
LLM_MODEL_2=deepseek-chat

# LLM 3 — Cadangan akhir (Ollama lokal)
LLM_API_3=http://localhost:11434/v1/chat/completions
LLM_API_KEY_3=***
LLM_MODEL_3=qwen2.5:1.5b

# Admin — skip anti-spam & daily limit
TRUSTED_CHAT_IDS=1267972859
```

### 5. Install Python Dependencies

```cmd
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr requests flask
```

> **Catatan:** `sentence-transformers` akan download E5-base (~278MB) di first run.

### 6. Install Node.js Dependencies (WhatsApp Bridge)

```cmd
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
cd ..
```

### 7. Jalankan (4 Terminal)

**Skema arsitektur:**
```
Telegram ──> telegram_bot.py ──┐
                              ├──> server.py:8000 (E5 + BM25 + LLM)
WhatsApp ──> wa_handler.py:3001 ─┘
                ^
                │
         bridge.js:3000 (Chrome/WA Web)
```

**Terminal 1 — Server API (port 8000):**
```cmd
cd C:\Proyek\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — WhatsApp Handler (port 3001):**
```cmd
cd C:\Proyek\chatbot-qna
python wa_handler.py
```

**Terminal 3 — WhatsApp Bridge (port 3000):**
```cmd
cd C:\Proyek\chatbot-qna\whatsapp-bridge
node bridge.js
```
QR code muncul → scan pake WhatsApp > Linked Devices.

**Terminal 4 — Telegram Bot:**
```cmd
cd C:\Proyek\chatbot-qna
python telegram_bot.py
```

### 8. Start All (1 Klik)

Double-click `start-all.bat` — langsung buka 4 terminal.

### 9. Pindah ke PC Baru

```cmd
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
pip install -r requirements.txt
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
```

Buat `.env`, terus `start-all.bat`. Selesai.

---

## 🐧 Panduan Instalasi — Linux

> **Catatan:** WhatsApp Bridge (`whatsapp-web.js`) membutuhkan Chrome/Chromium. Di Linux server tanpa GUI, jalankan:
> ```bash
> npx puppeteer browsers install chrome
> ```
> Namun untuk production, disarankan hanya menggunakan Telegram Bot (tanpa WhatsApp bridge) di Linux.

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nodejs npm
```

### 2. Clone & Setup

```bash
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr requests flask
```

### 3. Jalankan (Server + Telegram saja)

```bash
# Terminal 1 — Server
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2 — Telegram Bot
python telegram_bot.py
```

---

## ✅ Verifikasi

### Cek server:
```bash
curl http://localhost:8000/health
```

Output:
```json
{
  "status": "ok",
  "total_qna": 79,
  "engine": "E5-base",
  "source": "Google Sheets",
  "active_sessions": 0,
  "query_stats": {
    "total": 85,
    "accepted": 62,
    "rejected": 20,
    "greetings": 3,
    "errors": 0
  }
}
```

### Cek bot Telegram:
Buka Telegram, cari bot Anda, kirim pesan.

### Cek WhatsApp:
Chat nomor yang discan — bot harus merespon dengan typing indicator.

---

## 🔗 API Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/health` | GET | Status server, total Q&A, active sessions, query stats |
| `/log-stats` | GET | Statistik query log (total, accepted, rejected, errors) |
| `/chat` | POST | Kirim pertanyaan → dapat jawaban dari AI |
| `/start` | POST | Inisialisasi sesi baru untuk user |
| `/stop` | POST | Akhiri sesi chat (dapat durasi) |
| `/reload` | POST | Reload FAQ dari Google Sheets manual |
| `/history` | GET | Daftar semua sesi chat |
| `/history/{chat_id}` | GET | Detail chat per user |

### Contoh `/chat`

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pertanyaan": "Cara daftar SOBAT", "chat_id": "12345"}'
```

Response:
```json
{
  "jawaban": "Untuk mendaftar SOBAT...",
  "skor": 0.89
}
```

### Contoh `/log-stats`

```bash
curl http://localhost:8000/log-stats
```

Response:
```json
{
  "total": 120,
  "accepted": 95,
  "rejected": 22,
  "greetings": 3,
  "errors": 0,
  "file": "C:\\Proyek\\chatbot-qna\\query_log.jsonl",
  "size_kb": 4.2
}
```

---

## 📊 Logging & Evaluasi

Semua pertanyaan user dicatat otomatis ke `query_log.jsonl` (format JSONL — 1 baris per query).

### Contoh isi log:

```json
{"waktu":"2026-05-25 20:30:00","chat_id":"62xxx","pertanyaan":"siapa nama ibu jokowi","bm25_score":0.0,"bm25_status":"REJECT","top_score":0.773,"top_faq":"GC PLN eror ya Bapak ibu?","dijawab":false,"multi_part":false,"greeting":false,"error":""}
{"waktu":"2026-05-25 20:31:00","chat_id":"62xxx","pertanyaan":"aktivasi FASIH","bm25_score":5.04,"bm25_status":"ACCEPT","top_score":0.876,"top_faq":"Link Aktivasi Tidak Berlaku","dijawab":true,"multi_part":false,"greeting":false,"error":"","jawaban_preview":"Untuk aktivasi FASIH..."}
```

### Kegunaan:
- **Monitor performa** — berapa % pertanyaan diterima vs ditolak
- **False positive detection** — ada pertanyaan BPS yang salah ditolak?
- **Threshold tuning** — distribusi BM25 score untuk domain in vs out
- **Audit** — riwayat lengkap tiap query

### Rotasi otomatis:
File log dirotate saat mencapai ~500KB (~2500 query). File lama diberi timestamp.

---

## ❓ FAQ

**Q: Kok jawabannya gak nyambung?**
A: Bisa jadi FAQ database belum mencakup topik tersebut. Update Google Sheets lalu POST ke `/reload`.

**Q: Error "Address already in use"?**
A: Port 8000 masih dipakai. Cek:
```cmd
netstat -ano | findstr :8000    # Windows
sudo lsof -i :8000              # Linux
```

**Q: Bikin bot dengan identitas beda?**
A: Ganti `prompts/identity.json` + `.env` — gak perlu edit Python.

**Q: Chat history ilang?**
A: History di `chatbot.db`. Di-ignore git, aman.

**Q: Bisa pake LLM model lain?**
A: Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env`.

**Q: WhatsApp bridge-nya gak muncul QR?**
A: Pastikan `node bridge.js` jalan dari folder `whatsapp-bridge/`. Cek log: `[BM25]` harus muncul waktu ada chat. Kalo score selalu 999 → restart server.

**Q: BM25 score kok 999?**
A: BM25 gagal di-build. Restart server (`python -m uvicorn server:app ...`). Cek log startup — harus ada `[RELOAD] 79 Q&A loaded` + BM25 index kebangun otomatis.

**Q: Error "Browser was not found at the configured executablePath"?**
A: Chrome 146 belum terdownload. Jalanin: `npx puppeteer browsers install chrome` di folder `whatsapp-bridge/`.

**Q: Mau offline pake CPU doang?**
A: Install Ollama, pull `gemma3n:e4b`, ubah `.env` ke `http://localhost:11434/v1/chat/completions`.

**Q: Cara reset daily limit?**
A: Otomatis reset tiap ganti hari (WIB). Restart server juga reset.

**Q: Siapa trusted user?**
A: User di `TRUSTED_CHAT_IDS` di `.env` — skip anti-spam & daily limit.

**Q: Bot WA error "tidak ada jawaban"?**
A: Cek terminal wa_handler. Biasanya karena `requests` belum diinstall (`pip install requests`) atau URL double path (`/chat/chat`). Pull terbaru + restart.

**Q: Pertanyaan di luar BPS masih tembus?**
A: Cek terminal server — apakah ada log `[BM25]`? Kalo tidak ada → BM25 gagal build (restart). Kalo score 999 → sama. Kalo score 0 tapi masih tembus → laporkan.

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Syahrul Toha Saputra** — Pengembang & Arsitek Sistem.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
