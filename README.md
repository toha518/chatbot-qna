# NARA (NextGen AI Response Agent)

Asisten permasalahan IT dari **BPS Provinsi Kepulauan Bangka Belitung**.

> **N**extGen — Teknologi modern dan inovatif
> **A**I — Kecerdasan buatan sebagai mesin utama
> **R**esponse — Fokus menjawab dan merespons kebutuhan pengguna
> **A**gent — Asisten digital yang bertindak atas nama layanan

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Bridge-25D366?logo=whatsapp)](https://whatsapp.com)
[![Hybrid](https://img.shields.io/badge/Retrieval-Hybrid%20(E5%2BBM25)-purple)](https://huggingface.co/intfloat/multilingual-e5-base)
[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)]()

Asisten permasalahan IT dari **BPS Provinsi Kepulauan Bangka Belitung**. Melayani pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026** via Telegram & WhatsApp.

> **Stack:** FastAPI + Hybrid E5+BM25 (RRF fusion) + Multi-LLM failover + SQLite + EasyOCR
> **Model:** Cloud (OpenAI-compatible) → Ollama lokal — auto failover

---

## 📋 Daftar Isi

- [✨ Fitur](#-fitur)
- [📸 Tangkapan Layar](#tangkapan-layar)
- [🛠️ Tech Stack](#tech-stack)
- [🔒 Security & Proteksi](#-security--proteksi)
- [🧠 Arsitektur Modular](#-arsitektur-modular)
- [🔄 Replikasi / Custom Bot](#-replikasi--custom-bot)
- [💻 Panduan Instalasi — Windows](#-panduan-instalasi--windows)
- [🐧 Panduan Instalasi — Linux](#-panduan-instalasi--linux)
- [🔗 API Endpoints](#-api-endpoints)
- [📊 Logging & Evaluasi](#-logging--evaluasi)
- [❓ FAQ](#-faq)
- [📜 Riwayat Versi](#riwayat-versi)
- [📞 Kontak & Dukungan](#kontak-dukungan)


---

## 📸 Tangkapan Layar

<table>
  <tr>
    <td><img src="screenshots/wa-chat.jpg" alt="WhatsApp — Nara menjawab pertanyaan" width="300"></td>
    <td><img src="screenshots/tg-chat.jpg" alt="Telegram — Nara menjawab pertanyaan" width="300"></td>
  </tr>
  <tr>
    <td align="center"><sub>WhatsApp</sub></td>
    <td align="center"><sub>Telegram</sub></td>
  </tr>
</table>

---

## 🛠️ Tech Stack

| Layer | Teknologi |
|-------|-----------|
| **API Server** | FastAPI (Python) |
| **Hybrid Retrieval** | E5+BM25 via RRF fusion (semantic + keyword) |
| **Domain Filter** | BM25 (custom Python, keyword overlap) |
| **LLM Gateway** | Cloud API / Local (Ollama) — auto failover |
| **Database** | Google Sheets (FAQ) + SQLite (chat history) |
| **Telegram** | python-telegram-bot (Polling) |
| **WhatsApp** | whatsapp-web.js (Node.js bridge) |
| **OCR** | EasyOCR (Indonesia + Inggris) |
| **Bahasa** | Python 3.11+ / Node.js v20 LTS

---

## ✨ Fitur

| Fitur | Detail |
|-------|--------|
| 🤖 **AI Answering** | Multi-LLM dengan failover chain. Coba provider 1 → error? auto lanjut provider 2 → dst. Cloud API (OpenAI-compatible) & Ollama lokal |
| 🧠 **Hybrid Search (E5 + BM25 via RRF)** | E5 semantic + BM25 keyword via Reciprocal Rank Fusion. Kategori metadata terpisah (gak di-embedding). top_k=5. Cascade fallback depth 2 — concat 1-2 prev query kalo skor < 0.82 |
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
| 4 | 🎯 **BM25 Domain Filter** | `core/bm25.py` | Keyword overlap vs FAQ. **Skor < 0.5?** Ditolak langsung tanpa LLM |
| 5 | 🔍 **Hybrid Threshold + Cascade Fallback** | `server.py` | Skor E5 cosine similarity < 0.82? Cascade: concat 1-2 query user sebelumnya, search ulang. Masih < 0.82? tolak. BM25 tetap diproses rescue |
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
│   ├── embedder.py           ←   E5-base: load, encode, hybrid search (E5+BM25)
│   ├── bm25.py               ←   BM25: domain checker + per-doc scoring hybrid
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
         │  (↘ Telegram/WA kirim typing indicator)
         ▼
┌─ 4. GREETING? ──────────────────────────────┐
│  "halo", "pagi" → langsung LLM, no search   │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 5. BM25 DOMAIN CHECK ──────────────────────┐
│  Keyword overlap vs FAQ                     │
│  Score < 0.5? → TOLAK (gak lanjut ke LLM)   │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 6. MULTI-PART SPLIT ───────────────────────┐
│  Pisah "dan", "serta", "lalu"               │
│  Tiap bagian dicek BM25 domain + hybrid search  │
│  Bagian di luar domain → di-skip            │
└───────────────────────────────────────────────┘
         │
         ▼
┌─ 7. HYBRID RETRIEVAL (E5 + BM25) ──────────┐
│  E5 semantic similarity (cosine)             │
│  BM25 keyword overlap (per-doc)              │
│  RRF fusion: 1/(rank_E5+60) + 1/(rank_BM25+60)  │
│  top-5 berdasarkan RRF score                 │
│  Score < 0.82? → Cascade Fallback            │
│    depth=1: concat 1 prev user query        │
│    depth=2: concat 2 prev user query        │
│    Masih < 0.82? → tolak                    │
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
| `core/embedder.py` | ⬜ Opsional | Bisa ganti model hybrid search |
| `core/bm25.py` | ⬜ Opsional | Stopwords disesuaikan domain |
| `security/*.py` | ❌ **Jangan** | Proteksi built-in |

---

## 💻 Panduan Instalasi — Windows

<details>
<summary><b>Klik untuk lihat panduan Windows</b></summary>

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **Node.js** | v20 LTS (v24 mungkin bermasalah dengan puppeteer) |
| **RAM** | **Minimal 8GB** (disarankan 16GB kalau mau + Ollama lokal) |

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

</details>

---

## 🐧 Panduan Instalasi — Linux

<details>
<summary><b>Klik untuk lihat panduan Linux</b></summary>

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Ubuntu 22.04+ / Debian 12+ (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **Node.js** | v20 LTS |
| **RAM** | **Minimal 8GB** (disarankan 16GB kalau mau + Ollama lokal) |

> **Catatan WhatsApp Bridge:** `whatsapp-web.js` butuh Chrome/Chromium. Di Linux server tanpa GUI, jalanin `npx puppeteer browsers install chrome` setelah npm install.
> Untuk production, disarankan **Telegram Bot saja** tanpa WA bridge di Linux.

### 1. Install Python 3.11

```bash
# Ubuntu 22.04+
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-pip
```

Verifikasi:
```bash
python3.11 --version   # harus Python 3.11.x
```

### 2. Install Node.js v20

```bash
# Pake NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verifikasi:
```bash
node --version   # harus v20.x.x
npm --version
```

### 3. Install Git & Clone

```bash
sudo apt install -y git
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

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr requests flask
```

> **Catatan:** `sentence-transformers` akan download E5-base (~278MB) di first run.

### 6. Install Node.js Dependencies (WhatsApp Bridge)

```bash
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
```bash
cd chatbot-qna
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — WhatsApp Handler (port 3001):**
```bash
cd chatbot-qna
source venv/bin/activate
python wa_handler.py
```

**Terminal 3 — WhatsApp Bridge (port 3000):**
```bash
cd chatbot-qna/whatsapp-bridge
node bridge.js
```
QR code muncul → scan pake WhatsApp > Perangkat Tertaut.

**Terminal 4 — Telegram Bot:**
```bash
cd chatbot-qna
source venv/bin/activate
python telegram_bot.py
```

### 8. Start All (1 Script)

Buat file `start.sh`:
```bash
#!/bin/bash
echo "=== Starting NARA Services ==="
cd "$(dirname "$0")"
source venv/bin/activate

# Terminal via gnome-terminal (kalo pake GUI)
gnome-terminal -- bash -c "python -m uvicorn server:app --host 0.0.0.0 --port 8000; exec bash"
gnome-terminal -- bash -c "source venv/bin/activate && python wa_handler.py; exec bash"
gnome-terminal -- bash -c "cd whatsapp-bridge && node bridge.js; exec bash"
gnome-terminal -- bash -c "source venv/bin/activate && python telegram_bot.py; exec bash"
```

Kasih izin:
```bash
chmod +x start.sh
```

### 9. Pindah ke Server Baru

```bash
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
```

Buat `.env`, terus `./start.sh`. Selesai.

</details>

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
  "total_qna": 100+,
  "engine": "hybrid (E5+BM25)",
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

<details>
<summary><b>Klik untuk lihat FAQ</b></summary>

**Q:** Kok jawabannya gak nyambung?

**A:** Bisa jadi FAQ database belum mencakup topik tersebut. Update Google Sheets lalu POST ke `/reload`.

---

**Q:** Error "Address already in use"?

**A:** Port 8000 masih dipakai. Cek:
```cmd
netstat -ano | findstr :8000    # Windows
sudo lsof -i :8000              # Linux
```

---

**Q:** Bikin bot dengan identitas beda?

**A:** Ganti `prompts/identity.json` + `.env` — gak perlu edit Python.

---

**Q:** Chat history ilang?

**A:** History di `chatbot.db`. Di-ignore git, aman.

---

**Q:** Bisa pake LLM model lain?

**A:** Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env`.

---

**Q:** WhatsApp bridge-nya gak muncul QR?

**A:** Pastikan `node bridge.js` jalan dari folder `whatsapp-bridge/`. Cek log — harus ada `[BM25]` waktu ada chat. Kalo score selalu 999 → restart server.

---

**Q:** BM25 score kok 999?

**A:** BM25 gagal di-build. Restart server (`python -m uvicorn server:app ...`). Cek log startup — harus ada `[RELOAD] N Q&A loaded` + BM25 index kebangun otomatis.

---

**Q:** Error "Browser was not found at the configured executablePath"?

**A:** Chrome 146 belum terdownload. Jalanin: `npx puppeteer browsers install chrome` di folder `whatsapp-bridge/`.

---

**Q:** Mau offline pake CPU doang?

**A:** Install Ollama, pull `gemma3n:e4b`, ubah `.env` ke `http://localhost:11434/v1/chat/completions`.

---

**Q:** Cara reset daily limit?

**A:** Otomatis reset tiap ganti hari (WIB). Restart server juga reset.

---

**Q:** Siapa trusted user?

**A:** User di `TRUSTED_CHAT_IDS` di `.env` — skip anti-spam & daily limit.

---

**Q:** Bot WA error "tidak ada jawaban"?

**A:** Cek terminal wa_handler. Biasanya karena `requests` belum diinstall (`pip install requests`) atau URL double path (`/chat/chat`). Pull terbaru + restart.

---

**Q:** Pertanyaan di luar BPS masih tembus?

**A:** Cek terminal server — apakah ada log `[BM25]`? Kalo tidak ada → BM25 gagal build (restart). Kalo score 999 → sama. Kalo score 0 tapi masih tembus → laporkan.

</details>

## 📜 Riwayat Versi

<details>
<summary><b>Klik untuk lihat riwayat lengkap</b></summary>


---

#### v2.2.0 — 2026-05-29

**Added**
- **Hybrid retrieval** E5+BM25 via RRF fusion — BM25 keyword + E5 semantic digabung pake Reciprocal Rank Fusion
- `get_bm25_scores_all()` — BM25 return score per-doc buat hybrid
- `hybrid_search()` — fungsi baru di embedder, RRF dengan K=60
- Kategori sebagai **metadata terpisah** — gak ikut di-embedding, similarity murni konten
- `prompts/responses.json` — single source of truth untuk SEMUA user-facing text
- **Cascade Fallback** — hybrid score < 0.82? concat 1-2 query user sebelumnya, search ulang. depth max 2. Fix follow-up pendek kayak "di dtsen juga udah sesuai"

**Changed**
- top_k: 3 → 5 (distribusi hybrid lebih variatif)
- `/health` → engine: `hybrid (E5+BM25)`
- Greeting prompt: sekarang menyebutkan nama, role, dan topik yang dikuasai
- Multi-part split flowchart: BM25 + E5 → BM25 domain + hybrid search
- Tabel "Perbedaan Format Pesan Telegram vs WhatsApp" dihapus dari README
- Contoh `total_qna` di health response: 79 → 100+
- Flowchart step 7: cascade fallback detail (depth 1-2)
- Badge: `E5-base` → `Hybrid (E5+BM25)`

**Refactor**
- **Zero hardcode prompt** — semua teks statis di .py dipindah ke `prompts/responses.json`
  - server.py, telegram_bot.py, wa_handler.py, security/rate_limiter.py
  - Cukup edit `prompts/responses.json` untuk ubah semua pesan
- `load_responses()` di `core/llm.py` — helper buat load responses.json
- Greeting fallback di `server.py`: bacanya dari `prompts/identity.json` + `responses.json`

**Docs**
- Flowchart step 6 di-update: multi-part split → hybrid search
- Flowchart step 7 di-update: HYBRID RETRIEVAL + cascade fallback
- Tech Stack: Semantic Search → Hybrid Retrieval
- Lisensi: Apache 2.0 → Proyek internal BPS

---

#### v2.1.1 — 2026-05-26

**Fixed**
- Akronim dipisah jadi referensi, bukan bagian dari daftar topik utama
- Greeting detection pake prefix matching — `"haloo"`, `"pagii"`, `"helo"` tetap terdeteksi
- Korupsi server.py setelah edit beruntun

---

#### v2.1.0 — 2026-05-26

**Added**
- Intro detection: `"kamu bisa apa?"`, `"siapa kamu?"` langsung pake greeting prompt (skip E5/BM25)
- File referensi akronim terpisah `prompts/acronyms.md`

---

#### v2.0.0 — 2026-05-26

**Added**
- Rebrand total: **Cici Anova → NARA (NextGen AI Response Agent)**
- Personality system di `prompts/system.md` — Nara si IT Support sabar & step-by-step
- Command handler WhatsApp: `/start`, `/help`, `/topics`, `/stop`
- WA watchdog notifikasi session expired via bridge `/send`
- WA image processing indicator "⏳ Memproses gambar..."
- Foto + caption di Telegram diarahkan ke handler gambar (bukan handler teks)

**Changed**
- Identity, role, gender bot berubah total (nama, persona, domain framing)

**Fixed**
- WA bold: `**text**` → `*text*` (sekarang bold di WA)
- Semua sisa string "Cici Anova" di 10 file dihapus total
- Emoji rule relax — bebas emoji
- Pesan "Memproses gambar..." di WA dibiarkan (gak dihapus, hindari "Pesan telah dihapus")

**Docs**
- Backronym NARA, FAQ rapi, RAM 8GB, Linux guide selengkap Windows

---

#### v1.0.0 — 2026-05-25/26

**Added**
- BM25 hybrid domain filter — keyword overlap, zero-dependency
- E5-base semantic search (hybrid RRF dengan BM25)
- Evaluasi logging (`query_log.jsonl`) — BM25 score, status, jawaban tiap query
- Multi-part query split — pertanyaan dengan "dan", "serta" dipisah otomatis
- WA typing indicator (`sendStateTyping`)
- WA image support — detect + OCR via EasyOCR
- Telegram image processing "⏳ Memproses gambar..." + auto-hapus
- WA watchdog notif session expired via bridge
- Daily limit 50→25 (perintah Owner)
- Resureksi repo: WA bridge + start-all 4 terminal

**Fixed**
- Python import trap — `build_bm25()` pake list kosong
- WA handler double path bug (`/chat/chat`)
- WA bridge kirim pesan biasa, bukan reply
- top_k tuning: 3→5→3 setelah embedding kategori
- BM25 stopwords — filter angka-only
- E5 score threshold 0.82 sebelum LLM
- Prompt strict — HANYA data referensi, temperature=0.1
- Encoding UTF-8 fix untuk Windows (cp1252)
- `scores.argmax()` wrong index fix
- Puppeteer `--single-process` (LifecycleWatcher crash)

---

#### v0.4.0 — 2026-05-21

**Added**
- Gemini 2.5 Flash sebagai opsi free LLM
- Daily chat limit 100/user/hari, reset otomatis
- `TRUSTED_CHAT_IDS` dari `.env` — admin skip security
- LLM failover chain sampai 20 provider

**Fixed**
- Rate limiter duplikat di telegram_bot.py
- Session rest 6 jam (redundan)
- Error logging API response sebelum akses `choices`

---

#### v0.3.0 — 2026-05-20

**Added**
- 6-layer security: sanitasi input, anti-spam, daily limit, BM25 filter, E5 threshold, session watchdog
- Credit: dibuat dan dikelola oleh Syahrul Toha Saputra
- Failover chain: 3→10 provider
- Logging sukses/gagal tiap provider LLM

**Fixed**
- Deteksi otomatis Ollama lokal
- max_tokens: 500→2000 — jawaban gak kepotong
- Fallback plain text kalo markdown error di Telegram
- Rate limiter duplikat

---

#### v0.2.0 — 2026-05-19

**Added**
- Refactor modular: `core/`, `prompts/`, `security/`
- EasyOCR untuk screenshot/image
- LLM failover: 3 provider backup chain
- ParseMode.MARKDOWN di Telegram — bold/italic tampil

**Fixed**
- TOP_K: 5→3 — hemat token
- OCR: hapus `paragraph=True` — format output beda
- Import `ParseMode` ketinggalan
- Rename DB: `cici_anova.db` → `chatbot.db`
- Rename kolom: `pertanyaan→kendala`, `jawaban→solusi`

---

#### v0.1.0 — 2026-05-18 — Rilis Perdana

**Added**
- FastAPI server + Telegram bot
- OpenCode Go: deepseek-v4-flash (thinking off)
- LLM config dari `.env` (DEEPSEEK_* → LLM_*)
- Anti-spam rate limit: 5 chat/menit
- 500 karakter limit per chat
- Input sanitasi + media filter
- Chat history limit: 20→10
- `.gitignore` + CLEANED history (token aman)

</details>

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Syahrul Toha Saputra** — Pengembang & Arsitek Sistem.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

## 📄 Lisensi

Proyek internal BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
