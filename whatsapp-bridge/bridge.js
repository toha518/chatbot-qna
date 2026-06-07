// bridge.js — WhatsApp Bridge Nara
// Pakai whatsapp-web.js + Express + axios
// Terima pesan WA → kirim ke Flask handler → balas ke user
//
// Cara jalanin: node bridge.js
// QR code muncul di terminal → scan pake WhatsApp

const { Client, LocalAuth, MessageMedia, Poll } = require('whatsapp-web.js');
const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode-terminal');

// Cache: mapping LID (@lid@c.us) ke nomor @c.us — diisi pas ada pesan masuk
const lidToCus = new Map();

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

        // Kalo format LID (@lid), ambil nomor asli lewat getChat()
        const isLid = sender.endsWith('@lid') || sender.endsWith('@lid@c.us');
        if (isLid && !lidToCus.has(sender)) {
            try {
                const chat = await msg.getChat();
                // chat.id._serialized usually returns the format that works
                const serialized = chat.id._serialized;
                if (serialized && serialized.includes('@c.us')) {
                    lidToCus.set(sender, serialized);
                    lidToCus.set(sender.replace('@lid@c.us', '@lid'), serialized);
                    console.log(`[LID MAP] ${sender} → ${serialized}`);
                }
            } catch (e) {
                console.log(`[LID MAP] Gagal resolve ${sender}: ${e.message}`);
            }
        }

        // ── Filter: hanya terima teks & gambar ──
        const _isText = msg.type === 'chat' || msg.type === 'buttons_response';
        const _isImage = msg.type === 'image' || (msg.type === 'document' && msg.mimetype && msg.mimetype.startsWith('image/'));
        if (!_isText && !_isImage) {
            await client.sendMessage(sender, '⚠️ Hanya menerima teks dan gambar. Silakan ketik pertanyaan Anda.');
            return;
        }

        // Dapetin chat reference
        const chat = await msg.getChat();

        // ── Keep typing alive selama proses ──
        const typingInterval = setInterval(async () => {
            try {
                await chat.sendStateTyping();
            } catch (e) {
                // ignore — chat mungkin udah closed
            }
        }, 4000);
        // Kirim typing langsung
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

        const reply = resp.data?.jawaban || resp.data?.message || '';
        // Hentikan typing loop — response udah dapet
        clearInterval(typingInterval);
        await chat.clearState();

        if (!reply) {
            console.log(`[WA OUT] Silent block — ${sender} gak dikirimi apapun`);
            return;
        }
        console.log(`[WA OUT] Ke ${sender}: ${reply.substring(0, 100)}...`);

        // ===================== KIRIM PESAN DENGAN TOMBOL FEEDBACK =====================


        const _fb_sep = '\n━━━━━━━━━━━━━━━━━━━━\n';
        if (reply.includes(_fb_sep)) {
            // Pisahkan jawaban dari footer
            const parts = reply.split(_fb_sep);
            const answerText = parts[0].trim();

            // Kirim jawaban dulu
            await client.sendMessage(sender, answerText);

            // Kirim native WA Poll — user tinggal tap ✅ atau ❌
            // otomatis dihapus pas user vote
            const pollBody = new Poll('💡 Apakah jawaban ini sudah membantu?', [
                '✅ Sudah',
                '❌ Belum'
            ], { allowMultipleAnswers: false });
            const pollMsg = await chat.sendMessage(pollBody);

            // Simpan polling message reference biar bisa dihapus nanti
            if (!global._pollMap) global._pollMap = new Map();
            const _key = sender.split('@')[0];
            global._pollMap.set(_key, pollMsg.id._serialized);
        } else {
            await client.sendMessage(sender, reply);
        }

    } catch (err) {
        // Pastiin typing loop mati walau error
        if (typeof typingInterval !== 'undefined') {
            clearInterval(typingInterval);
            try { await chat.clearState(); } catch (e) {}
        }
        if (err.code === 'ECONNREFUSED') {
            console.error('[ERROR] Flask handler gak jalan! Jalankan: python wa_handler.py');
        } else if (err.response) {
            console.error(`[ERROR] HTTP ${err.response.status}: ${JSON.stringify(err.response.data).substring(0, 200)}`);
        } else {
            console.error(`[ERROR] ${err.message}`);
        }
    }
});

// ===================== HANDLE POLL VOTE =====================
client.on('vote_update', async (vote) => {
    try {
        // Ambil voter dan opsi yang dipilih
        const voter = vote.voter;
        if (!voter) return;

        const selected = vote.selectedOptions;
        if (!selected || selected.length === 0) return;

        const optionName = selected[0].name;
        const pollMsg = vote.parentMessage;

        // Cek apakah ini poll feedback punya kita (dari _pollMap)
        const _key = voter.split('@')[0];
        if (global._pollMap && global._pollMap.get(_key)) {
            // Hapus poll dari chat
            try {
                await pollMsg.delete(true);
            } catch (delErr) {
                console.log(`[POLL] Gagal hapus: ${delErr.message}`);
            }
            global._pollMap.delete(_key);

            // Kirim feedback ke server
            const isPositive = optionName.includes('✅');
            const feedbackQuery = isPositive ? 'feedback_yes' : 'feedback_no';

            const resp = await axios.post(`${FLASK_URL}/wa-message`, {
                sender: voter,
                message: feedbackQuery,
                is_image: false
            }, { timeout: 30000 });

            const reply = resp.data?.jawaban || '';
            if (reply) {
                await client.sendMessage(voter, reply);
            }
        }
    } catch (err) {
        if (err.code !== 'ECONNREFUSED') {
            console.error(`[POLL ERROR] ${err.message}`);
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

// Kirim pesan via API (dipanggil watchdog server.py)
app.post('/send', async (req, res) => {
    try {
        const { to, message } = req.body;
        if (!to || !message) {
            return res.status(400).json({ error: 'Parameter "to" dan "message" wajib' });
        }

        // Normalisasi: @lid@c.us → @lid (soalnya msg.from pake @lid biar work)
        let targetId = to;
        if (to.endsWith('@lid@c.us')) {
            targetId = to.replace('@lid@c.us', '@lid');
            console.log(`[API SEND] ${to} → ${targetId} (normalized)`);
        }

        // Cek LID cache
        if (lidToCus.has(targetId)) {
            const cached = lidToCus.get(targetId);
            if (cached.includes('@c.us')) {
                targetId = cached;
                console.log(`[API SEND] Cache hit: ${to} → ${targetId}`);
            }
        }

        console.log(`[API SEND] ${targetId}: ${message.substring(0, 80)}...`);
        const sent = await client.sendMessage(targetId, message);
        console.log(`[API SEND] ✅ Berhasil (id: ${sent.id.id})`);
        return res.json({ status: 'ok', id: sent.id.id });

    } catch (err) {
        const errStr = err.stack ? err.stack.substring(0, 500) : (err.message || JSON.stringify(err));
        console.error(`[API SEND] ❌ Gagal: ${errStr}`);

        // Fallback 1: coba @lid kalo tadi pake @lid@c.us
        try {
            const fbTo = req.body?.to;
            const altId = fbTo.endsWith('@lid@c.us') ? fbTo.replace('@lid@c.us', '@lid') : null;
            if (altId && altId !== targetId) {
                console.log(`[API SEND] 🔄 Fallback @lid: ${fbTo} → ${altId}...`);
                const sent = await client.sendMessage(altId, req.body.message);
                console.log(`[API SEND] ✅ via @lid fallback`);
                return res.json({ status: 'ok', id: sent.id.id });
            }
        } catch (fbErr) {
            console.error(`[API SEND] ❌ @lid fallback: ${fbErr.message}`);
        }

        // Fallback 2: getChatById + chat.sendMessage
        try {
            console.log(`[API SEND] 🔄 Fallback getChatById...`);
            const chat = await client.getChatById(req.body.to);
            const sent = await chat.sendMessage(req.body.message);
            console.log(`[API SEND] ✅ via getChatById`);
            return res.json({ status: 'ok', id: sent.id.id });
        } catch (fbErr) {
            console.error(`[API SEND] ❌ getChatById: ${fbErr.message}`);
        }

        res.status(500).json({ error: err.message, stack: err.stack?.substring(0, 300) });
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
