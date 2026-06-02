# Setup NARA — PC Windows

## 📦 Installing Dependencies

### 1. Python 3.11+
Download: https://www.python.org/downloads/release/python-3119/
✅ **Centang "Add Python to PATH"** → Install Now
Cek: `python --version`

### 2. Node.js v20 LTS
Download: https://nodejs.org/ (pilih v20 LTS)
**Restart PC** setelah install.
Cek: `node --version` dan `npm --version`

### 3. Git
```cmd
winget install git.git
```

### 4. Clone Repository
```cmd
cd C:\Proyek
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 5. Buat File `.env`
Simpan di `chatbot-qna\.env`:
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

# LLM 3 — Cadangan lokal (Ollama)
LLM_API_3=http://localhost:11434/v1/chat/completions
LLM_API_KEY_3=***
LLM_MODEL_3=qwen2.5:1.5b

# Admin — skip anti-spam & daily limit
TRUSTED_CHAT_IDS=1267972859
```

### 6. Install Python Packages
```cmd
pip install -r requirements.txt
```
> E5-base (~278MB) akan terdownload di first run.

### 7. Install WhatsApp Bridge
```cmd
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
cd ..
```

---

## 🚀 Cara Jalanin

### Opsi A: 1 Klik
Double-click `start-all.bat` — otomatis buka 5 terminal + dashboard.

### Opsi B: Manual (4 Terminal)

**Terminal 1 — Server API (port 8000):**
```cmd
cd chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Dashboard (port 8001):**
```cmd
cd chatbot-qna
python dashboard.py
```

**Terminal 3 — WhatsApp Bridge (port 3000):**
```cmd
cd chatbot-qna\whatsapp-bridge
node bridge.js
```
Scan QR code yang muncul.

**Terminal 4 — Telegram Bot:**
```cmd
cd chatbot-qna
python telegram_bot.py
```

---

## 📱 Scan QR WhatsApp

1. Buka WhatsApp di HP
2. Tap **⋮ (3 titik)** → **Perangkat tertaut** → **Tautkan perangkat**
3. Arahkan kamera ke QR code di **Terminal 3**

---

## 🔄 Pindah ke PC Baru (Full Steps)

```cmd
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
pip install -r requirements.txt
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
```

Buat `.env`, lalu `start-all.bat`. Selesai.

---

## ⚠️ Catatan Penting

| Hal | Keterangan |
|-----|-----------|
| **Nomor WA baru!** | Jangan pake nomor utama — resiko banned |
| **RAM** | Minimal 8GB (16GB kalau + Ollama) |
| **QR sekali saja** | Session tersimpan di `auth/` folder |
| **E5 download** | ~278MB first run |
| **EasyOCR lazy load** | ~500MB, jalan pas ada gambar |

---

## ❓ Error umum

- **`ModuleNotFoundError`** → `pip install -r requirements.txt`
- **`No such file`** → cek lokasi `cd chatbot-qna`
- **QR tidak muncul** → `npm install` dulu di `whatsapp-bridge/`
- **Server 500** → cek terminal 1 ada error atau gak
