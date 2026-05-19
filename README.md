# Cici Anova — Chatbot Q&A BPS

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)

Asisten Q&A resmi **BPS Provinsi Kepulauan Bangka Belitung**. Menjawab pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026**.

> **Stack:** FastAPI + E5-base (semantic search) + LLM + SQLite (history)

---

## 📋 Daftar Isi

- [Fitur](#-fitur)
- [Pengamanan](#-pengamanan)
- [Panduan Instalasi — Windows](#-panduan-instalasi--windows)
- [Panduan Instalasi — Linux](#-panduan-instalasi--linux)
- [Verifikasi](#-verifikasi)
- [Manajemen Server](#-manajemen-server)
- [Struktur Folder](#-struktur-folder)
- [API Endpoints](#-api-endpoints)
- [FAQ](#-faq)

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|-----------|
| 🧠 **Semantic Search** | E5-base — retrieval-specialized, lebih akurat dari MiniLM |
| 🤖 **AI Answering** | LLM — jawab dengan konteks dari database FAQ |
| 🛡️ **Anti-Spam** | Rate limit (5 chat/menit) + 6 jam session rest + watchdog |
| ✂️ **Batas Karakter** | Maksimal 500 karakter per chat — tolak otomatis tanpa proses AI |
| 🧹 **Input Sanitasi** | Hapus karakter kontrol + batasi emoji maks 5 per chat |
| 🖼️ **OCR Gambar** | Screenshot/foto dibaca otomatis pake EasyOCR (lokal) |
| 📚 **Batas History** | Maks 10 chat terakhir per session — hemat token & biaya |
| 💬 **Session Management** | Auto-reset setelah 30 menit idle + notifikasi session ended |
| 📜 **Chat History** | Semua chat tersimpan di SQLite — kolom `kendala` & `solusi` (`history` endpoint) |
| 📋 **Reply Keyboard** | Tombol menu di bawah chat (Mulai, Bantuan, Topik, Berhenti) |
| 📊 **FAQ Database** | Auto-download dari Google Sheets tiap startup + reload tiap 10 menit |

---

## 🛡️ Pengamanan

Bot Cici Anova memiliki beberapa lapisan pengamanan untuk menjaga kestabilan, keamanan data, dan efisiensi biaya:

### 1. 🚦 Rate Limit (5 Chat/Menit)
Batasi maksimal **5 pesan per menit** per user. Jika terlampaui, user diblokir otomatis selama **5 menit**. Berlaku di dua layer: bot Telegram & API server.

### 2. ✂️ Batas Karakter (500 Karakter)
Setiap pertanyaan dibatasi maksimal **500 karakter**. Jika melebihi, langsung ditolak tanpa diproses oleh AI — hemat token dan biaya.

### 3. 🧹 Input Sanitasi
Sebelum diproses, teks dibersihkan dari:
- **Karakter kontrol** (NULL, ESC, backspace, dll) — mencegah injeksi
- **Emoji berlebih** — maksimal 5 emoji per chat, sisanya dihapus

### 4. 🖼️ OCR Gambar
Bot bisa membaca teks dari **screenshot atau foto** via EasyOCR (offline, gratis).
- Gambar dari kamera/gallery → **OCR otomatis** → teks digabung caption
- Stiker, voice, video → tetap ditolak
- Model EasyOCR (~500MB) di-download sekali, aktif pas ada gambar aja
- Support bahasa Indonesia + Inggris

### 5. 📚 Batas History Session
Riwayat chat yang dikirim ke LLM dibatasi **maks 10 pesan terakhir** (5 tanya + 5 jawab). Chat lama otomatis di-drop, token tetap hemat.

### 6. ⏰ Session Timeout (30 Menit)
Session otomatis berakhir setelah **30 menit** tanpa aktivitas. Watchdog mengirim notifikasi ke user dan membersihkan history.

### 7. 🛑 Session Rest (6 Jam)
Jika session berjalan lebih dari **6 jam**, user dipaksa istirahat selama **6 jam**. Session dihapus, user harus mulai dari awal.

### 8. 🔄 LLM Failover
Bot punya cadangan LLM otomatis — jika provider utama gagal atau limit, sistem akan failover ke provider berikutnya tanpa user sadari. Cukup atur beberapa API key di `.env`.

### 9. 📋 SQLite Logging
Semua chat terekam di **SQLite database** (`cici_anova.db`). Data tetap utuh meski session direset atau user /stop.

**Data Model — Chat Logs:**
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `chat_id` | TEXT | ID unik user Telegram |
| `waktu` | TIMESTAMP | Waktu chat dikirim |
| `kendala` | TEXT | Masalah/pertanyaan yang diajukan user |
| `solusi` | TEXT | Jawaban/respon yang diberikan bot |

---

## 💻 Panduan Instalasi — Windows

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
6. Verifikasi — buka **CMD/PowerShell** dan ketik:

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

Buat file `.env` di `C:\chatbot-qna\`:

```cmd
notepad .env
```

Isi dengan:

```
TELEGRAM_BOT_TOKEN=isi_token_dari_botfather
CHATBOT_URL=http://localhost:8000/chat
LLM_API_1=https://api.openai.com/v1/chat/completions
LLM_API_KEY_1=sk-isi_api_key
LLM_MODEL_1=gpt-4o-mini
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-isi_api_key_deepseek
LLM_MODEL_2=deepseek-chat
GSHEET_CSV_URL=isi_url_csv_google_sheets
```

Simpan (**Ctrl+S**) dan tutup.

> **Dapatkan token:**
> - Telegram: [@BotFather](https://t.me/botfather)
> - LLM API: daftar di provider seperti DeepSeek, OpenAI, atau OpenRouter
> - Google Sheets CSV URL: buka spreadsheet → File → Share → Publish to web → CSV

### 5. Install Dependencies

Buka **CMD** atau **PowerShell** di folder `C:\chatbot-qna\`:

```powershell
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

Proses ini mendownload E5-base (~278MB) dan EasyOCR (~500MB). Estimasi 5-10 menit.

Jika `pip` tidak ditemukan:
```powershell
python -m pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

### 6. Jalankan Server

Buka **CMD 1** (PowerShell juga bisa):

```cmd
cd C:\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Tunggu sampai muncul:
```
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

> ⏳ Loading pertama agak lama karena download model E5-base.

### 7. Jalankan Bot Telegram

Buka **CMD 2** baru (biarkan CMD 1 tetap jalan):

```cmd
cd C:\chatbot-qna
python telegram_bot.py
```

Output:
```
Bot started!
```

Selesai! Buka Telegram dan chat ke bot Anda.

### 8. Auto-Start (Opsional)

Biar gak perlu buka 2 CMD manual setiap kali:

Buat file `C:\chatbot-qna\start_chatbot.bat`:

```batch
@echo off
title Cici Anova
cd /d C:\chatbot-qna
start "Server" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8000"
timeout /t 15 /nobreak >nul
start "Bot" cmd /c "python telegram_bot.py"
exit
```

Double-click `start_chatbot.bat` untuk menjalankan keduanya.

**Auto-start saat boot:**
1. Tekan **Win + R**, ketik `shell:startup`, Enter
2. Buat shortcut `start_chatbot.bat` ke folder yang muncul

---

## 🐧 Panduan Instalasi — Linux

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

Verifikasi:
```bash
python3 --version
git --version
```

### 2. Clone Repository

```bash
cd /home
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 3. Setup Virtual Environment (Rekomendasi)

```bash
python3 -m venv venv
source venv/bin/activate
```

> Dengan virtual env, dependensi terisolasi dari sistem — aman dan rapi.

### 4. Setup Token (.env)

```bash
nano .env
```

Isi:

```
TELEGRAM_BOT_TOKEN=isi_token_dari_botfather
CHATBOT_URL=http://localhost:8000/chat
LLM_API_1=https://api.openai.com/v1/chat/completions
LLM_API_KEY_1=sk-isi_api_key
LLM_MODEL_1=gpt-4o-mini
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-isi_api_key_deepseek
LLM_MODEL_2=deepseek-chat
GSHEET_CSV_URL=isi_url_csv_google_sheets
```

Simpan: `Ctrl+X` → `Y` → `Enter`.

### 5. Install Dependencies

```bash
# Aktifkan virtual env dulu (kalau pake)
source venv/bin/activate

pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

### 6. Jalankan Server

**Terminal 1:**
```bash
cd /home/chatbot-qna
source venv/bin/activate   # skip kalo gak pake venv
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

### 7. Jalankan Bot Telegram

**Terminal 2** (biarkan terminal 1 jalan):
```bash
cd /home/chatbot-qna
source venv/bin/activate   # skip kalo gak pake venv
python telegram_bot.py
```

### 8. Manajemen dengan systemd (Production)

Biar server + bot jalan otomatis walau SSH logout atau server restart, buat 2 service systemd.

#### a) Server API — `/etc/systemd/system/cici-server.service`

```ini
[Unit]
Description=Cici Anova API Server
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

#### b) Bot Telegram — `/etc/systemd/system/cici-bot.service`

```ini
[Unit]
Description=Cici Anova Telegram Bot
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

Cek status:
```bash
sudo systemctl status cici-server
sudo systemctl status cici-bot
```

> Tanpa virtual env, ganti `ExecStart` jadi `/usr/bin/python3 -m uvicorn ...`

### 9. Alternatif: screen / tmux

Kalau gak mau pake systemd (misal VPS murah tanpa akses root), pakai `screen`:

```bash
sudo apt install screen -y

# Buat session server
screen -dmS cici-server bash -c "cd /home/chatbot-qna && source venv/bin/activate && python -m uvicorn server:app --host 0.0.0.0 --port 8000"

# Buat session bot
screen -dmS cici-bot bash -c "cd /home/chatbot-qna && source venv/bin/activate && python telegram_bot.py"

# Cek session aktif
screen -ls

# Masuk ke session
screen -r cici-server   # atau cici-bot
# Keluar: Ctrl+A, D
```

---

## ✅ Verifikasi

### Cek server:
```
http://localhost:8000/health
```

Harus muncul JSON:
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
Buka Telegram, cari bot Anda, kirim pesan. Bot harus merespon.

### Cek history:
```
http://localhost:8000/history
```

---

## 📁 Struktur Folder

```
chatbot-qna/
├── server.py            ← API server utama (E5-base + LLM)
├── telegram_bot.py      ← Layer Telegram (bot + anti-spam)
├── materi.csv           ← Backup FAQ dari Google Sheets
├── .env                 ← Token & konfigurasi (tidak di-git)
├── .env.example         ← Template konfigurasi
├── .gitignore
├── qna_index.pkl        ← Index E5-base (auto-generate)
├── cici_anova.db        ← SQLite chat history (auto-generate)
├── venv/                ← Virtual environment (Linux, opsional)
├── start_chatbot.bat    ← (Windows) one-click start
└── __pycache__/         ← Cache Python (auto-generate)
```

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
A: Bisa jadi FAQ database belum mencakup topik tersebut. Hubungi pegawai BPS untuk update database.

**Q: Error "Address already in use"?**  
A: Port 8000 masih dipakai. Cek:
```cmd
netstat -ano | findstr :8000    # Windows
sudo lsof -i :8000              # Linux
```

**Q: Kok bot offline terus?**  
A: Pastikan server (uvicorn) dan bot sama-sama jalan. Kena restart? Jalanin ulang.

**Q: Chat history ilang?**  
A: History tersimpan di `cici_anova.db` — file ini di-*ignore* git, jadi aman. Jangan dihapus.

**Q: Bisa pake LLM model lain?**  
A: Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env` sesuai provider yang dipakai.

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Chisiya** 🃏 — Lead Automation Engineer.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
