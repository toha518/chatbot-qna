# Cici Anova — Chatbot Q&A BPS

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)

Asisten Q&A resmi **BPS Provinsi Kepulauan Bangka Belitung**. Menjawab pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026**.

> **Stack:** FastAPI + E5-base (semantic search) + DeepSeek (LLM) + SQLite (history)

---

## 📋 Daftar Isi

- [Fitur](#-fitur)
- [Kebutuhan Sistem](#-kebutuhan-sistem)
- [Instalasi Python](#️-instalasi-python)
- [Clone Repository](#-clone-repository)
- [Setup Token (.env)](#-setup-token-env)
- [Instal Dependencies](#-instal-dependencies)
- [Jalankan Server](#-jalankan-server)
- [Jalankan Bot Telegram](#-jalankan-bot-telegram)
- [Verifikasi](#-verifikasi)
- [Auto-Start (Opsional)](#-auto-start-opsional)
- [Struktur Folder](#-struktur-folder)
- [FAQ](#-faq)

---

## ✨ Fitur

| Fitur | Keterangan |
|-------|-----------|
| 🧠 **Semantic Search** | E5-base — retrieval-specialized, lebih akurat dari MiniLM |
| 🤖 **AI Answering** | DeepSeek LLM — jawab dengan konteks dari database FAQ |
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

### 8. 🔄 LLM Failover (3 Provider)
Bot punya **3 cadangan LLM** secara berurutan:
1. **OpenCode Go** ($10/bulan) — utama
2. **DeepSeek langsung** — failover kalo OpenCode limit/error
3. **Ollama lokal** — failover terakhir kalo internet mati

Failover otomatis — user gak ngerasa perbedaan. Cukup atur di `.env`.

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

## 💻 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 ([Download](https://python.org/downloads)) |
| **RAM** | Minimal 4GB (E5-base ~278MB + sisanya untuk OS) |
| **Koneksi** | Internet (DeepSeek API + download model pertama kali) |

---

## 🛠️ Instalasi Python

1. Buka [python.org/downloads](https://www.python.org/downloads/release/python-3119/)
2. Scroll ke bawah, download **Windows installer (64-bit)**
3. Jalankan installer
4. ✅ **WAJIB centang** `Add Python to PATH`
5. Klik **Install Now**
6. Setelah selesai, buka **CMD** dan verifikasi:

```cmd
python --version
```

Output yang diharapkan:
```
Python 3.11.9
```

---

## 📦 Clone Repository

```cmd
cd C:\
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

Jika `git` belum terinstall, download dari [git-scm.com](https://git-scm.com/).

---

## 🔐 Setup Token (.env)

Buat file `.env` di folder `C:\chatbot-qna\`:

```cmd
notepad .env
```

Salin isi berikut:

```
TELEGRAM_BOT_TOKEN=isi_token_dari_botfather
CHATBOT_URL=http://localhost:8000/chat
DEEPSEEK_API_KEY=sk-isi_api_key_dari_deepseek
DEEPSEEK_API=https://api.deepseek.com/chat/completions
GSHEET_CSV_URL=isi_url_csv_google_sheets
```

Simpan (**Ctrl+S**) dan tutup notepad.

> **Butuh token?** Dapatkan dari [@BotFather](https://t.me/botfather) (Telegram) dan [platform.deepseek.com](https://platform.deepseek.com) (DeepSeek).

---

## 📥 Instal Dependencies

```cmd
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

Proses ini akan mendownload **E5-base model (~278MB)** + **EasyOCR (~500MB)** — butuh koneksi stabil, estimasi 5-10 menit.

> ⚠️ **Khusus pertama kali:** pas `uvicorn` jalan, model E5-base di-download dari HuggingFace (~278MB). Pas pertama kali ada gambar masuk, EasyOCR di-download (~500MB).

Jika muncul error `pip not found`, gunakan:
```cmd
python -m pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr
```

---

## 🚀 Jalankan Server

Kita butuh **2 jendela CMD** terpisah.

### CMD 1 — Server API

```cmd
cd C:\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Tunggu hingga muncul:
```
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

> ⏳ Loading E5-base + Google Sheets butuh beberapa saat (~10-30 detik). Pertama kali lebih lama karena download model.

---

## 🤖 Jalankan Bot Telegram

Buka **CMD baru** (biarkan CMD 1 tetap berjalan):

```cmd
cd C:\chatbot-qna
python telegram_bot.py
```

Output yang diharapkan:
```
Menu commands registered!
Bot started!
```

---

## ✅ Verifikasi

### Cek server (via browser):
Buka `http://localhost:8000/health`

Harus muncul JSON seperti:
```json
{
  "status": "ok",
  "total_qna": 74,
  "engine": "E5-base",
  "source": "Google Sheets",
  "active_sessions": 0
}
```

### Cek bot (via Telegram):
Buka Telegram, cari bot Anda, kirim pesan. Bot harus merespon.

### Cek history (via browser):
Buka `http://localhost:8000/history` — akan menampilkan daftar sesi chat yang sudah terjadi.

---

## 🔄 Auto-Start (Opsional)

Agar tidak perlu membuka 2 CMD setiap kali:

### 1. Buat file `start_chatbot.bat`

Buka notepad, salin kode berikut, simpan sebagai `C:\chatbot-qna\start_chatbot.bat`:

```batch
@echo off
title Cici Anova
cd /d C:\chatbot-qna
start "Server" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8000"
timeout /t 15 /nobreak >nul
start "Bot" cmd /c "python telegram_bot.py"
exit
```

Double-click `start_chatbot.bat` untuk menjalankan keduanya sekaligus.

### 2. Auto-start saat boot Windows

1. Tekan **Win + R**, ketik `shell:startup`, Enter
2. Buat shortcut dari `start_chatbot.bat` ke folder tersebut

---

## 📁 Struktur Folder

```
C:\chatbot-qna\
├── server.py            ← API server utama (E5-base + DeepSeek)
├── telegram_bot.py      ← Layer Telegram (bot + anti-spam)
├── materi.csv           ← Backup FAQ dari Google Sheets
├── .env                 ← Token & konfigurasi (tidak di-git)
├── .env.example         ← Template konfigurasi
├── .gitignore
├── qna_index.pkl        ← Index E5-base (auto-generate)
├── cici_anova.db        ← SQLite chat history (auto-generate)
├── start_chatbot.bat    ← (opsional) one-click start
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
A: Port 8000 masih dipakai program lain. Cek dengan:
```cmd
netstat -ano | findstr :8000
taskkill /PID <angka> /F
```

**Q: Kok bot offline terus?**  
A: Pastikan 2 CMD masih terbuka (server + bot). Kena restart komputer? Jalanin ulang.

**Q: Chat history ilang?**  
A: History tersimpan di `cici_anova.db` — file ini di-*ignore* git, jadi aman. Jangan dihapus.

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Chisiya** 🃏 — Lead Automation Engineer.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
