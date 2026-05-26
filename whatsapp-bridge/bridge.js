// bridge.js — WhatsApp Bridge Nara
// Pakai whatsapp-web.js + Express + axios
// Terima pesan WA → kirim ke Flask handler → balas ke user
//
// Cara jalanin: node bridge.js
// QR code muncul di terminal → scan pake WhatsApp

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode-terminal');

// ===================== KONFIGURASI =====================
const FLASK_URL = process.env.FLASK_URL || 'http://localhost:3001';
const PORT = process.env.PORT || 3000;
const AUTH_FOLDER = process.env.AUTH_FOLDER || './auth';

// ===================== INIT CLIENT =====================
const client = new Client({
    authStrategy: new LocalAuth({ dataPath: AUTH_FOLDER }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }
});

// ===================== QR CODE =====================
client.on('qr', (qr) => {
    console.log('\n[QR] Scan QR code ini dengan WhatsApp:');
    qrcode.generate(qr, { small: true });
    console.log('\n[QR] Belum punya QR reader di terminal? Buka gambar ini di browser:');
    console.log(`https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(qr)}\n`);
});

// ===================== READY =====================
client.on('ready', () => {
    console.log(`[READY] WhatsApp Bridge siap! Nomor: ${client.info.wid.user}`);
    console.log(`[READY] Chatbot endpoint: ${FLASK_URL}`);
});

// ===================== AUTHENTICATED =====================
client.on('authenticated', () => {
    console.log('[AUTH] WhatsApp berhasil diautentikasi!');
});

// ===================== DISCONNECTED =====================
client.on('disconnected', (reason) => {
    console.log(`[DISCONNECT] WhatsApp terputus: ${reason}`);
    console.log('[DISCONNECT] Restart bridge untuk reconnect...');
});

// ===================== PESAN MASUK =====================
client.on('message', async (msg) => {
    try {
        // Abaikan status, group chat, dan pesan dari bot sendiri
        if (msg.isStatus || msg.from.endsWith('@g.us')) return;
        if (msg.from === client.info.wid.user + '@c.us') return;

        const sender = msg.from;
        const text = msg.body ? msg.body.trim() : '';

        // Kirim typing indicator biar user tau bot lagi proses
        const chat = await msg.getChat();
        await chat.sendStateTyping();

        console.log(`[WA IN] Dari ${sender}: ${text.substring(0, 100)}`);

        // ===================== OCR UNTUK GAMBAR =====================
        let pertanyaan = text;
        let is_image = false;

        // Cek kalo ada gambar
        const isImageType = msg.type === 'image' || (msg.type === 'document' && msg.mimetype && msg.mimetype.startsWith('image/'));
        if (msg.hasMedia || isImageType) {
            // Kirim pesan sementara biar user tau lagi diproses
            await client.sendMessage(sender, '⏳ *Memproses gambar...*');
            try {
                const media = await msg.downloadMedia();
                if (media && media.mimetype && media.mimetype.startsWith('image/')) {
                    pertanyaan = JSON.stringify({
                        text: text || '[Gambar]',
                        image_base64: media.data,
                        mimetype: media.mimetype
                    });
                    is_image = true;
                    console.log(`[WA IMAGE] Dari ${sender}: ${(text || '(no caption)').substring(0, 50)}`);
                }
            } catch (e) {
                console.log(`[WA MEDIA ERROR] ${e.message}`);
            }
        }

        if (!pertanyaan) {
            console.log(`[WA SKIP] Pesan kosong dari ${sender}`);
            return;
        }

        // ===================== KIRIM KE FLASK HANDLER =====================
        const resp = await axios.post(`${FLASK_URL}/wa-message`, {
            sender: sender,
            message: pertanyaan,
            is_image: is_image
        }, { timeout: 120000 });

        const reply = resp.data?.jawaban || resp.data?.message || 'Maaf, terjadi error.';
        console.log(`[WA OUT] Ke ${sender}: ${reply.substring(0, 100)}...`);

        // ===================== BALAS PESAN =====================
        await chat.clearState();
        await client.sendMessage(sender, reply);

    } catch (err) {
        if (err.code === 'ECONNREFUSED') {
            console.error('[ERROR] Flask handler gak jalan! Jalankan: python wa_handler.py');
        } else if (err.response) {
            console.error(`[ERROR] HTTP ${err.response.status}: ${JSON.stringify(err.response.data).substring(0, 200)}`);
        } else {
            console.error(`[ERROR] ${err.message}`);
        }
    }
});

// ===================== REST API (UNTUK CONTROL) =====================
const app = express();
app.use(express.json());

// Status bridge
app.get('/status', (req, res) => {
    res.json({
        status: client.info ? 'connected' : 'connecting',
        number: client.info?.wid?.user || null,
        auth_folder: AUTH_FOLDER
    });
});

// Kirim pesan via API
app.post('/send', async (req, res) => {
    try {
        const { to, message } = req.body;
        if (!to || !message) {
            return res.status(400).json({ error: 'Parameter "to" dan "message" wajib' });
        }
        const chatId = to.includes('@c.us') ? to : `${to}@c.us`;
        console.log(`[API SEND] Ke ${chatId}: ${message.substring(0, 60)}...`);
        const sent = await client.sendMessage(chatId, message);
        console.log(`[API SEND] ✅ Berhasil (id: ${sent.id.id})`);
        res.json({ status: 'ok', id: sent.id.id });
    } catch (err) {
        console.error(`[API SEND] ❌ Gagal: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

// Logout — hapus sesi biar bisa ganti nomor
app.post('/logout', async (req, res) => {
    try {
        await client.logout();
        res.json({ status: 'ok', message: 'WhatsApp logout. Hapus folder auth/ dan restart untuk scan ulang.' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`[API] Control API jalan di http://localhost:${PORT}`);
    console.log(`[API]  GET /status     → status koneksi`);
    console.log(`[API]  POST /send      → kirim pesan {"to":"62xxx@c.us","message":"..."}`);
    console.log(`[API]  POST /logout    → logout & hapus sesi`);
});

// ===================== START =====================
console.log('=== WhatsApp Bridge Nara ===');
console.log('Scan QR code yang muncul untuk menghubungkan WhatsApp.');
console.log('Folder auth:', AUTH_FOLDER);
console.log('====================================\n');
client.initialize();
