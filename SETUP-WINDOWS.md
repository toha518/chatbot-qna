# Setup WhatsApp untuk Cici Anova — PC Windows

## 📦 Yang Perlu Diinstall

### 1. Node.js 18+
Download: https://nodejs.org (ambil LTS version)
- Install seperti biasa, next-next aja
- **Restart PC** setelah install biar PATH kebaca

Cek udah keinstall:
```cmd
node --version
npm --version
```

### 2. Python packages tambahan
Buka **Command Prompt** di folder `chatbot-qna/`, jalankan:
```cmd
pip install flask requests easyocr
```

---

## 🚀 Cara Jalanin (3 Terminal)

Karena kita punya 3 process yang jalan bareng, buka **3 jendela Command Prompt** terpisah.

### Terminal 1: Server API (server.py — Core)
```cmd
cd chatbot-qna
python server.py
```
Diamkan — jangan ditutup. Harus jalan duluan sebelum yang lain.

### Terminal 2: WhatsApp Handler (Flask)
```cmd
cd chatbot-qna
python wa_handler.py
```
Diamkan juga. Ini jembatan WhatsApp → server.py.

### Terminal 3: WhatsApp Bridge (Node.js + whatsapp-web.js)
```cmd
cd chatbot-qna\whatsapp-bridge
npm install
node bridge.js
```
**Scan QR code** yang muncul di terminal pake WhatsApp lo.

---

## 📱 Cara Scan QR

1. Buka WhatsApp di HP
2. Tap **⋮ (3 titik)** → **Perangkat tertaut** → **Tautkan perangkat**
3. Arahin kamera ke QR code di terminal
4. Selesai! Chatbot udah nyambung ke WhatsApp lo

**Kalau gak muncul QR**, cek terminal 3 — harusnya ada kotak QR atau link buat buka QR di browser.

---

## 🔄 Cara Ganti Nomor WA

1. Tutup **Terminal 3** (Ctrl+C)
2. Hapus folder `chatbot-qna\whatsapp-bridge\auth\`
3. Jalanin `node bridge.js` lagi
4. Scan QR baru

---

## 🛑 Cara Matiin Semua

Tinggal tutup aja 3 terminalnya — urutan gak masalah.

Atau kalau pake **start-all.bat**, tutup jendela cmd-nya.

---

## ⚠️ Catatan Penting

| Hal | Keterangan |
|-----|-----------|
| **Pake nomor baru!** | Jangan pake nomor utama — resiko kena banned |
| **QR cuma sekali** | Sesi tersimpan di folder `auth/`, gak perlu scan ulang |
| **Ekstra RAM** | ~200-300 MB tambahan (karena Chromium Puppeteer) |
| **OCR gambar?** | Support screenshot error — EasyOCR otomatis jalan |
| **Anti-spam & daily limit** | Sama kayak Telegram — ngikut `server.py` |

---

## ✅ Cek Semuanya Jalan

Kirim pesan ke nomor WhatsApp lo. Harusnya dibales sama Cici Anova kayak di Telegram.

Kalau error:
- **"Server tidak merespon"** → Terminal 1 (server.py) belum jalan
- **"WhatsApp terputus"** → Cek koneksi internet, restart Terminal 3
- **QR gak muncul** → `npm install` dulu di folder `whatsapp-bridge/`
