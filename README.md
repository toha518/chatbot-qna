# Cici Anova - Chatbot Q&A BPS

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)

Asisten Q&A resmi **BPS Provinsi Kepulauan Bangka Belitung**. Menjawab pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026**.

> **Stack:** FastAPI + E5-base (semantic search) + LLM (DeepSeek / Ollama) + SQLite (history)
> **Fitur Baru:** Auto-detect Ollama lokal + fallback markdown Telegram + logging provider

---

## 📋 Daftar Isi

- [Fitur](#-fitur)
- [Arsitektur Modular](#-arsitektur-modular)
- [Replikasi / Custom Bot](#-replikasi--custom-bot)
- [Panduan Instalasi - Windows](#-panduan-instalasi--windows)
- [Panduan Instalasi - Linux](#-panduan-instalasi--linux)
- [Verifikasi](#-verifikasi)
- [Manajemen Server](#-manajemen-server)
- [API Endpoints](#-api-endpoints)
- [FAQ](#-faq)

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|-----------|
| 🧠 **Semantic Search** | E5-base - retrieval-specialized, lebih akurat dari MiniLM |
| 🤖 **AI Answering** | LLM - jawab dengan konteks dari database FAQ. Support DeepSeek & Ollama lokal |
| 🧠 **Semantic Search** | E5-base - retrieval-specialized, lebih akurat dari MiniLM |
| 🤖 **AI Answering** | LLM - jawab dengan konteks dari database FAQ. Support DeepSeek & Ollama lokal |
| 🔒 **Security** | Anti-spam, sanitasi input, session timeout, markdown fallback, dll |
| 🖼️ **OCR Gambar** | Screenshot/foto dibaca otomatis pake EasyOCR (lokal) |
| 📜 **Chat History** | Semua chat tersimpan di SQLite - kolom `kendala` & `solusi` |
| 📋 **Reply Keyboard** | Tombol menu di bawah chat (Mulai, Bantuan, Topik, Berhenti) |
| 📊 **Provider Logging** | Log sukses/gagal tiap provider - tau model mana yang dipake |
| 📊 **FAQ Database** | Auto-download dari Google Sheets tiap startup + reload tiap 10 menit |

---

## 🔒 Security

| Fitur | Lapisan | Keterangan |
|-------|---------|-----------|
| 🚫 **Anti-Spam (Telegram)** | `telegram_bot.py` | Rate limit 20 chat/menit — block 5 menit. Trusted user bypass |
| 🚫 **Anti-Spam (API)** | `security/rate_limiter.py` | Rate limit **5 request/menit** per session — block 5 menit. Silent block setelah warning pertama |
| ✂️ **Batas Karakter** | `telegram_bot.py` | Maksimal **500 karakter** per chat. Tolak otomatis tanpa proses AI |
| 🧹 **Input Sanitasi** | `telegram_bot.py` | Hapus karakter kontrol (`\x00-\x1f`) + batasi emoji maks **5 per chat** |
| 📚 **Batas History** | `security/session.py` | Maks **10 tanya-jawab** terakhir per session — hemat token & biaya |
| 💬 **Session Timeout** | `security/session.py` | Auto-reset setelah **30 menit idle**. Watchdog scan tiap 15 detik |
| 🔔 **Notifikasi Session** | `security/session.py` | Kirim pesan otomatis ke Telegram pas session expired (isi jam & durasi) |
| 🛡️ **Markdown Fallback** | `telegram_bot.py` | Kalo parsing Markdown error, fallback ke **plain text** |
| 🔑 **Auth Header Safe** | `core/llm.py` | API Key **tidak dikirim** kalo bernilai `***` — aman buat Ollama lokal |
| 🧠 **Conditional Thinking** | `core/llm.py` | Param `thinking` **hanya dikirim** kalo model mengandung `deepseek` — kompatibel dengan Ollama |
| 📊 **Provider Logging** | `core/llm.py` | Log ✅ sukses / ❌ gagal tiap provider — tau persis model mana yang dipake |

---

## 🧠 Arsitektur Modular

Kode chatbot ini dipisah ke modul-modul terpisah biar gampang di-*maintain* dan di-*replikasi*:

```
chatbot-qna/
│
├── server.py                 ← Router FastAPI (tipis, delegasi ke modul lain)
├── telegram_bot.py           ← Layer Telegram (OCR, anti-spam, kirim API)
│
├── core/                     ← 🔧 Mesin utama (jarang diubah)
│   ├── database.py           ←   SQLite: init, log chat, query history
│   ├── embedder.py           ←   E5-base: load model, encode, semantic search
│   └── llm.py                ←   LLM: load config, failover chain, builder prompt
│
├── prompts/                  ← 🎯 IDENTITAS & ATURAN (ganti total utk replikasi)
│   ├── identity.json         ←   Nama, peran, topik bot
│   ├── system.md             ←   Aturan cara menjawab
│   └── greeting.md           ←   Template sambutan /start
│
├── security/                 ← 🔒 Lapisan pengaman
│   ├── rate_limiter.py       ←   Anti-spam: limit 5 chat/menit, block 5 menit
│   └── session.py            ←   Session: timeout, watchdog, notif Telegram
│
├── .env                      ← Token & API key (tidak di-git)
├── .env.example              ← Template env
└── chatbot.db                ← SQLite history (auto-generate)
```

### Detail per Modul

| Module | Isi | Fungsi |
|--------|-----|--------|
| `core/database.py` | `init_db()`, `log_chat()`, `get_chat_history()`, `list_sessions()` | Semua interaksi ke SQLite |
| `core/embedder.py` | `init_embedder()`, `load_from_gsheet()`, `search()` | Load E5-base, encode FAQ, cari pertanyaan relevan |
| `core/llm.py` | `load_llm_config()`, `load_prompts()`, `build_greeting_prompt()`, `build_system_prompt()`, `call_llm()` | Panggil LLM + failover chain. Auto-detect Ollama lokal, `thinking` disabled otomatis untuk DeepSeek, max_tokens 2000 |
| `security/rate_limiter.py` | `check_api_rate_limit()`, `init_rate_limit_entry()` | Proteksi spam, block user kalau 5 chat/menit |
| `security/session.py` | `init_session()`, `cleanup_sessions()`, `session_watchdog()` | Atur session per user, watchdog expired |

---

## 🔄 Replikasi / Custom Bot

Mau bikin bot serupa tapi dengan identitas & topik berbeda? **Gak perlu edit kode Python sama sekali.** Cukup ganti file di folder `prompts/` + `.env`.

### Langkah Replikasi

#### 1. Clone repo

```bash
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

#### 2. Ganti identity.json (WAJIB)

File: **`prompts/identity.json`** - ini yang membedakan bot kamu dengan aslinya.

```json
{
  "name": "Nama Bot Kamu",
  "role": "deskripsi peran bot",
  "topics": ["Topik 1", "Topik 2", "Topik 3"]
}
```

Apa yang berubah:
- `name` → Nama bot (dipakai di greeting & perkenalan)
- `role` → Deskripsi peran (dipakai di system prompt)
- `topics` → Daftar topik (dipakai di greeting & system prompt)

#### 3. Ganti aturan menjawab (opsional)

File: **`prompts/system.md`** - aturan cara LLM menjawab pertanyaan.

Template yang bisa diisi:
```markdown
Kamu adalah {name}, {role}.

Tugasmu membantu menjawab pertanyaan tentang {topics}.

Kamu akan menerima beberapa data referensi beserta kategorinya. Pilih dan gunakan yang PALING RELEVAN dengan pertanyaan user.

PENTING - Cara menjawab:
1. [Aturan 1]
2. [Aturan 2]
...
```

Variabel `{name}`, `{role}`, `{topics}` otomatis diisi dari `identity.json`.

#### 4. Ganti sambutan (opsional)

File: **`prompts/greeting.md`** - template pas user bilang "halo".

```markdown
Kamu adalah {name}, {role}.

Pengguna menyapa kamu. Jawab dengan ramah, perkenalkan diri kamu sebagai {name}...
```

#### 5. Isi .env dengan data kamu

```ini
TELEGRAM_BOT_TOKEN=token_bot_baru
GSHEET_CSV_URL=url_faq_baru

# Provider 1 - Ollama lokal (gratis, offline)
LLM_API_1=http://localhost:11434/v1/chat/completions
LLM_API_KEY_1=***
LLM_MODEL_1=gemma3n:e4b

# Provider 2 - DeepSeek API (cadangan)
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-api-key-deepseek
LLM_MODEL_2=deepseek-chat
```

#### 6. Selesai! Jalankan server & bot

```bash
# Windows
python -m uvicorn server:app --host 0.0.0.0 --port 8000
python telegram_bot.py

# Linux
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
python telegram_bot.py
```

### Ringkasan - Apa yang Perlu Diubah

| File | Wajib? | Fungsi |
|------|--------|--------|
| `prompts/identity.json` | ✅ WAJIB | Nama, peran, topik bot |
| `prompts/system.md` | ⬜ Opsional | Aturan cara menjawab |
| `prompts/greeting.md` | ⬜ Opsional | Template sambutan |
| `.env` | ✅ WAJIB | Token bot, API key, URL FAQ |
| `materi.csv` | ✅ WAJIB | Data FAQ (Google Sheets CSV) |
| `server.py` | ❌ Jangan | Kode router - gak perlu disentuh |
| `telegram_bot.py` | ⬜ Optional | Kode bot - fallback markdown sudah built-in |
| `core/llm.py` | ⬜ Optional | Sudah auto-detect Ollama & DeepSeek |
| `core/embedder.py` | ⬜ Optional | Bisa ganti model embedder |
| `security/*.py` | ❌ Jangan | Pengamanan - gak perlu disentuh |

---

## 💻 Panduan Instalasi - Windows

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **RAM** | Minimal 4GB |
| **Koneksi** | Internet (download model & akses LLM API) |

---

### 1. Install Python

1. Buka [python.org/downloads](https://www.python.org/downloads/release/python-3119/)
2. Scroll ke bawah, download **Windows installer (64-bit)**
3. Jalankan installer
4. ✅ **WAJIB centang** `Add Python to PATH`
5. Klik **Install Now**
6. Verifikasi:

```cmd
python --version
```

Output:
```
Python 3.11.9
```

### 2. Install Git

Download dari [git-scm.com](https://git-scm.com/download/win), install dengan default setting.

### 3. Clone Repository

```cmd
cd C:\
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 4. Setup Token (.env)

```cmd
notepad .env
```

Isi dengan:

```ini
TELEGRAM_BOT_TOKEN=isi_token_dari_botfather
CHATBOT_URL=http://localhost:8000/chat
GSHEET_CSV_URL=isi_url_csv_google_sheets

# LLM 1 - Ollama Lokal (rekomendasi untuk offline)
LLM_API_1=http://localhost:11434/v1/chat/completions
LLM_API_KEY_1=***
LLM_MODEL_1=gemma3n:e4b

# LLM 2 - DeepSeek Langsung (cadangan)
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-isi_deepseek
LLM_MODEL_2=deepseek-chat

# LLM 3 - OpenCode Go (cadangan)
LLM_API_3=https://opencode.ai/zen/go/v1/chat/completions
LLM_API_KEY_3=sk-isi_opencode
LLM_MODEL_3=deepseek-v4-flash
```

Simpan (**Ctrl+S**) dan tutup.

> **Dapatkan token:**
> - Telegram → [@BotFather](https://t.me/botfather)
> - LLM API → daftar di DeepSeek, OpenRouter, atau provider lain
> - Google Sheets CSV URL → File → Share → Publish to web → CSV

### 5. Install Dependencies

Buka **CMD** atau **PowerShell** di folder proyek:

```powershell
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr ollama
```

Jika `pip` tidak ditemukan:
```powershell
python -m pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr ollama
```

> **Catatan:** Library `ollama` opsional - hanya diperlukan jika pakai Ollama lokal. Install Ollama dari [ollama.com/download](https://ollama.com/download).

### 5b. Setup Ollama (Opsional - untuk offline)

```cmd
# Install Ollama → https://ollama.com/download
# Pull model gemma3n (ringan, tanpa thinking)
ollama pull gemma3n:e4b

# Test
ollama run gemma3n:e4b
```

Rekomendasi model gratis tanpa thinking:
- `gemma3n:e4b` (4B) - recommended
- `ministral-3:8b` (8B) - alternatif
- `gemma3:12b` (12B) - lebih kuat

### 6. Jalankan Server (CMD 1)

```cmd
cd C:\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Tunggu sampai muncul:
```
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

### 7. Jalankan Bot (CMD 2)

```cmd
cd C:\chatbot-qna
python telegram_bot.py
```

Output:
```
Bot started!
```

### 8. Auto-Start (Opsional)

Buat `C:\chatbot-qna\start_chatbot.bat`:

```batch
@echo off
title Chatbot
cd /d C:\chatbot-qna
start "Server" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8000"
timeout /t 15 /nobreak >nul
start "Bot" cmd /c "python telegram_bot.py"
exit
```

Double-click untuk jalan.

**Auto-start saat boot:** `Win+R` → `shell:startup` → buat shortcut `.bat` di situ.

---

## 🐧 Panduan Instalasi - Linux

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Ubuntu 22.04+ / Debian 11+ |
| **Python** | 3.11 atau 3.12 |
| **RAM** | Minimal 4GB |
| **Koneksi** | Internet (download model & akses LLM API) |

---

### 1. Install Python & Tools

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Clone Repository

```bash
cd /home
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 3. Virtual Environment (Rekomendasi)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Setup Token (.env)

```bash
nano .env
```

Isi (sama seperti Windows), simpan `Ctrl+X` → `Y` → `Enter`.

### 5. Install Dependencies

```bash
source venv/bin/activate   # skip kalo gak pake venv
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

### 6. Jalankan Server (Terminal 1)

```bash
cd /home/chatbot-qna
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

### 7. Jalankan Bot (Terminal 2)

```bash
cd /home/chatbot-qna
source venv/bin/activate
python telegram_bot.py
```

### 8. systemd (Production - auto-start)

#### `/etc/systemd/system/cici-server.service`

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

#### `/etc/systemd/system/cici-bot.service`

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
```
http://localhost:8000/health
```

Output:
```json
{
  "status": "ok",
  "total_qna": 74,
  "engine": "E5-base",
  "active_sessions": 0
}
```

### Cek bot:
Buka Telegram, cari bot Anda, kirim pesan. Bot harus merespon.

---

## 🔗 API Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/health` | GET | Cek status server |
| `/chat` | POST | Kirim pertanyaan ke bot |
| `/stop` | POST | Akhiri sesi chat |
| `/start` | POST | Inisialisasi sesi baru |
| `/reload` | POST | Reload FAQ dari Google Sheets |
| `/history` | GET | Daftar semua sesi chat |
| `/history/{chat_id}` | GET | Detail chat per user |

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
A: Ganti `prompts/identity.json` + `.env` — gak perlu edit kode Python.

**Q: Chat history ilang?**
A: History tersimpan di `chatbot.db`. File ini di-*ignore* git, jadi aman.

**Q: Bisa pake LLM model lain?**
A: Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env` sesuai provider.

**Q: Mau offline pake CPU doang?**
A: Install Ollama, pull `gemma3n:e4b`, ubah `.env` ke `http://localhost:11434/v1/chat/completions`. Jalan di laptop/PC biasa tanpa GPU. 🖥️

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Syahrul Toha Saputra** - Pengembang & Arsitek Sistem.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 - Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
