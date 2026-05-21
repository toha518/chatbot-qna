# Cici Anova — Chatbot Q&A BPS

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)
[![E5-base](https://img.shields.io/badge/Embedding-E5--base-orange)](https://huggingface.co/intfloat/multilingual-e5-base)

Asisten Q&A resmi **BPS Provinsi Kepulauan Bangka Belitung**. Menjawab pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026**.

> **Stack:** FastAPI + E5-base (semantic search) + Multi-LLM failover + SQLite + EasyOCR
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
- [❓ FAQ](#-faq)

---

## ✨ Fitur

| Fitur | Detail |
|-------|--------|
| 🤖 **AI Answering** | Multi-LLM dengan failover chain. Coba provider 1 → error? auto lanjut provider 2 → dst. Support cloud API (OpenAI-compatible) & Ollama lokal |
| 🧠 **Semantic Search** | E5-base multilingual — retrieval lebih akurat dari Tfidf/MinilM. Otomatis skip duplikat jawaban & skor rendah |
| 🗣️ **OCR Gambar** | Screenshot/foto dibaca otomatis pakai EasyOCR (lokal, GPU opsional). Support Indo + Inggris |
| 🔄 **Auto-Reload FAQ** | Download ulang dari Google Sheets tiap 10 menit. Bisa reload manual via `/reload` |
| 📜 **Chat History** | Semua percakapan tersimpan di SQLite — kolom `kendala` (pertanyaan) & `solusi` (jawaban) |
| ⌨️ **Reply Keyboard** | Tombol permanen: 🏠 Mulai, 📖 Bantuan, 📋 Daftar Topik, ⏹ Berhenti |
| 📊 **FAQ Database** | Auto-load dari Google Sheets CSV saat startup + reload periodik |
| 🧹 **Input Sanitasi** | Karakter kontrol dibuang, emoji dibatasi maks 5 per chat, panjang maks 500 karakter |
| 📝 **Markdown Fallback** | Kirim markdown ke Telegram; auto fallback ke plain text kalau error parsing |

---

## 🔒 Security & Proteksi

Bot ini punya **4 lapis proteksi** untuk cegah penyalahgunaan:

| # | Lapisan | File | Cara Kerja |
|---|---------|------|------------|
| 1 | 🚫 **Anti-Spam** | `security/rate_limiter.py` | **5 request per menit** per user. Lewat? Block **5 menit**. Peringatan cuma sekali, sisanya silent block |
| 2 | 📅 **Daily Chat Limit** | `server.py` | **100 chat per hari** per user. Reset otomatis tiap ganti hari (WIB). |
| 3 | 💬 **Session Timeout** | `security/session.py` | Session expired setelah **30 menit idle**. Watchdog scan tiap 15 detik, kirim notif Telegram otomatis pas expired |
| 4 | 👑 **Trusted User** | `security/rate_limiter.py` | User tertentu di `.env` **skip anti-spam & daily limit** |

### Detail Proteksi

| Proteksi | Untuk Siapa | Threshold | Durasi Blokir |
|----------|-------------|-----------|---------------|
| Anti-spam | Semua user non-trusted | 5 chat/menit | 5 menit |
| Daily limit | Semua user non-trusted | 100 chat/hari | Reset besok |
| Session idle | Semua user (termasuk trusted) | 30 menit | Hapus session |


### Trusted User

User di `TRUSTED_CHAT_IDS` (dari `.env`) **tidak kena**:
- Anti-spam rate limit
- Daily chat limit

Tapi tetap kena **session idle timeout** — watchdog tetap berjalan.

### Input Sanitasi (Layer Awal)

Lapisan tambahan sebelum masuk ke server:

- **Control characters** (`\x00-\x1f`) — dibuang otomatis
- **Emoji > 5** — kelebihan dihapus
- **Karakter > 500** — ditolak dengan peringatan
- **Pesan kosong** setelah filtering — ditolak

---

## 🧠 Arsitektur Modular

```
chatbot-qna/
│
├── server.py                 ← FastAPI router (tipis — delegasi ke modul lain)
├── telegram_bot.py           ← Layer Telegram (OCR, sanitasi, kirim API)
│
├── core/                     ← 🔧 Mesin utama
│   ├── database.py           ←   SQLite: init, log chat, query history
│   ├── embedder.py           ←   E5-base: load model, encode, semantic search
│   └── llm.py                ←   LLM: load multi-provider, failover chain, build prompt
│
├── security/                 ← 🔒 Lapisan pengaman
│   ├── rate_limiter.py       ←   Anti-spam (5/menit), trusted user
│   └── session.py            ←   Session: timeout 30 menit, watchdog tiap 15 detik, notif Telegram
│
├── prompts/                  ← 🎯 IDENTITAS & ATURAN (ganti untuk replikasi)
│   ├── identity.json         ←   Nama, peran, topik bot
│   ├── system.md             ←   Aturan cara menjawab
│   └── greeting.md           ←   Template sambutan /start
│
├── .env                      ← Token & API key (gitignored)
├── .env.example              ← Template env
└── chatbot.db                ← SQLite history (auto-generate, gitignored)
```

### Detail Modul

| Modul | Isi | Fungsi |
|-------|-----|--------|
| `core/database.py` | `init_db()`, `log_chat()`, `get_chat_history()`, `list_sessions()` | Semua interaksi SQLite |
| `core/embedder.py` | `init_embedder()`, `load_from_gsheet()`, `search()` | Load E5-base, encode FAQ, semantic search dengan cosine similarity |
| `core/llm.py` | `load_llm_config()`, `load_prompts()`, `build_greeting_prompt()`, `build_system_prompt()`, `call_llm()` | Panggil LLM dengan failover chain. Auto-detect Ollama lokal, max_tokens 2000 |
| `security/rate_limiter.py` | `check_api_rate_limit()`, `init_rate_limit_entry()`, `init_trusted_ids()` | Anti-spam, block user kalau 5 chat/menit, trusted user skip limit |
| `security/session.py` | `init_session()`, `cleanup_sessions()`, `session_watchdog()`, `format_durasi()` | Atur session per user, watchdog expired, notif Telegram otomatis |

---

## 🔄 Replikasi / Custom Bot

Mau bikin bot serupa tapi dengan identitas & topik berbeda? **Gak perlu edit Python sama sekali.** Cukup ganti file di `prompts/` + `.env`.

### Langkah Replikasi

#### 1. Clone repo

```bash
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

#### 2. Ganti identity.json (WAJIB)

**`prompts/identity.json`** — ini yang membedakan bot kamu.

```json
{
  "name": "Nama Bot Kamu",
  "role": "deskripsi peran bot",
  "topics": ["Topik 1", "Topik 2", "Topik 3"]
}
```

#### 3. Ganti aturan menjawab (opsional)

**`prompts/system.md`** — aturan cara LLM menjawab. Variabel `{name}`, `{role}`, `{topics}` otomatis diisi dari `identity.json`.

#### 4. Ganti sambutan (opsional)

**`prompts/greeting.md`** — template pas user menyapa.

#### 5. Isi .env

Copy `.env.example` ke `.env` dan isi:

```ini
TELEGRAM_BOT_TOKEN=***
GSHEET_CSV_URL=url_csv_google_sheets

# LLM Provider 1 — Cloud API (OpenAI-compatible)
# Contoh: DeepSeek, OpenRouter, Gemini, dll.
LLM_API_1=https://api.deepseek.com/chat/completions
LLM_API_KEY_1=***
LLM_MODEL_1=deepseek-chat

# LLM Provider 2 — Ollama lokal (opsional)
# Contoh: gemma3n:e4b, qwen2.5:1.5b, dll.
# LLM_API_2=http://localhost:11434/v1/chat/completions
# LLM_API_KEY_2=***
# LLM_MODEL_2=gemma3n:e4b

# Trusted user (opsional, pisah koma)
TRUSTED_CHAT_IDS=1267972859
```

#### 6. Jalankan

```bash
# Terminal 1 — Server API
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2 — Bot Telegram
python telegram_bot.py
```

### Yang Perlu Diubah vs Jangan Disentuh

| File | Wajib? | Fungsi |
|------|--------|--------|
| `prompts/identity.json` | ✅ WAJIB | Nama, peran, topik bot |
| `prompts/system.md` | ⬜ Opsional | Aturan cara menjawab |
| `prompts/greeting.md` | ⬜ Opsional | Template sambutan |
| `.env` | ✅ WAJIB | Token, API key, URL FAQ |
| `server.py` | ❌ **Jangan** | Kode router — tidak perlu disentuh |
| `telegram_bot.py` | ⬜ Opsional | Kode bot — fallback markdown & OCR built-in |
| `core/llm.py` | ⬜ Opsional | Auto-detect Ollama & cloud API, failover chain |
| `core/embedder.py` | ⬜ Opsional | Bisa ganti model embedder |
| `security/*.py` | ❌ **Jangan** | Pengamanan — proteksi built-in |

---

## 💻 Panduan Instalasi — Windows

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **RAM** | Minimal 4GB (8GB untuk OCR + E5) |
| **Koneksi** | Internet (download model & akses LLM API) |

### 1. Install Python

1. Buka [python.org/downloads](https://www.python.org/downloads/release/python-3119/)
2. Download **Windows installer (64-bit)**
3. ✅ Centang **Add Python to PATH** → Install Now
4. Verifikasi: `python --version`

### 2. Install Git

Download dari [git-scm.com](https://git-scm.com/download/win).

### 3. Clone & Setup

```cmd
cd C:\
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
copy .env.example .env
notepad .env
```

Isi `.env` lalu simpan.

### 4. Install Dependencies

```powershell
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

> **Catatan:** `sentence-transformers` akan download E5-base (~278MB) di first run.  
> **Opsional (Ollama):** Install dari [ollama.com/download](https://ollama.com/download), lalu `ollama pull gemma3n:e4b`.

### 5. Jalankan

**Terminal 1 — Server:**
```cmd
cd C:\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Bot:**
```cmd
cd C:\chatbot-qna
python telegram_bot.py
```

### 6. Auto-Start (Opsional)

Buat `C:\chatbot-qna\start_chatbot.bat`:

```batch
@echo off
title Cici Anova
cd /d C:\chatbot-qna
start "Server" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8000"
timeout /t 15 /nobreak >nul
start "Bot" cmd /c "python telegram_bot.py"
exit
```

---

## 🐧 Panduan Instalasi — Linux

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Ubuntu 22.04+ / Debian 11+ |
| **Python** | 3.11 atau 3.12 |
| **RAM** | Minimal 4GB |
| **Koneksi** | Internet (download model & akses LLM API) |

### 1. Install Python & Tools

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Clone & Setup

```bash
cd /home
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
python3 -m venv venv
source venv/bin/activate
cp .env.example .env
nano .env
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

### 4. Jalankan

**Terminal 1 — Server:**
```bash
cd /home/chatbot-qna
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Bot:**
```bash
cd /home/chatbot-qna
source venv/bin/activate
python telegram_bot.py
```

### 5. systemd (Production)

**`/etc/systemd/system/cici-server.service`:**
```ini
[Unit]
Description=Chatbot API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/chatbot-qna
ExecStart=/home/chatbot-qna/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/cici-bot.service`:**
```ini
[Unit]
Description=Chatbot Telegram Bot
After=network.target cici-server.service
Requires=cici-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/chatbot-qna
ExecStart=/home/chatbot-qna/venv/bin/python telegram_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cici-server cici-bot
sudo systemctl start cici-server cici-bot
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
  "total_qna": 74,
  "engine": "E5-base",
  "source": "Google Sheets",
  "active_sessions": 0
}
```

### Cek bot:
Buka Telegram, cari bot Anda, kirim pesan. Bot harus merespon dengan reply keyboard.

---

## 🔗 API Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/health` | GET | Cek status server, total Q&A, active sessions |
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
A: Ganti `prompts/identity.json` + `.env` — gak perlu edit Python sama sekali.

**Q: Chat history ilang?**
A: History tersimpan di `chatbot.db`. File ini di-ignore git, aman.

**Q: Bisa pake LLM model lain?**
A: Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env`. Support semua OpenAI-compatible endpoint.

**Q: Mau offline pake CPU doang?
A: Install Ollama, pull `gemma3n:e4b`, ubah `.env` ke `http://localhost:11434/v1/chat/completions`. Jalan di laptop biasa tanpa GPU. 🖥️

**Q: Cara reset daily limit?**
A: Otomatis reset tiap ganti hari (berdasarkan WIB). Restart server juga reset semua counter.

**Q: Siapa trusted user?**
A: User di `TRUSTED_CHAT_IDS` di `.env` — skip anti-spam & daily limit. Format: `TRUSTED_CHAT_IDS=1267972859,987654321`

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Syahrul Toha Saputra** — Pengembang & Arsitek Sistem.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
