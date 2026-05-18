# telegram_bot.py — Layer Telegram Bot Cici Anova
# Tugas: nerima pesan dari Telegram, kirim ke server API, balasin ke user
# Ini cuma "jembatan" — logika utama ada di server.py

import asyncio
import httpx                       # HTTP client buat panggil server API
import time
import re
import os
from dotenv import load_dotenv
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===================== KONFIGURASI =====================
load_dotenv()  # baca .env (kalo ada)

# Kalo .env gak ada (misal masih jalan di VPS), fallback ke hardcoded
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # WAJIB diisi di .env
CHATBOT_URL = os.getenv("CHATBOT_URL") or "http://localhost:8000/chat"  # aman, URL publik lokal

# ===================== ANTI-SPAM (Bot Layer) =====================
# Proteksi sebelum request dikirim ke server API
RATE_LIMIT = 5             # Maks 5 pesan per menit per user
WINDOW = 60                  # Jendela waktu (detik)
BLOCK_DURATION = 300         # Durasi block setelah kena limit (5 menit)
TRUSTED_USERS = {}           # User yg skip anti-spam (kosong = semua kena)


user_tracking = {}


def normalize(text):
    """Normalisasi teks: lower case, hapus tanda baca, rapihin spasi"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # hapus tanda baca
    text = re.sub(r'\s+', ' ', text)     # normalize spasi
    return text




def check_rate_limit(chat_id, text=""):
    """Cek apakah user udah mencapai batas 20 pesan per menit"""
    now = time.time()

    if chat_id not in user_tracking:
        user_tracking[chat_id] = {"timestamps": [], "blocked_until": 0,
                                  "last_active": 0, "block_notified": False}

    entry = user_tracking[chat_id]

    # Masih dalam masa block?
    if entry["blocked_until"] > now:
        if not entry["block_notified"]:
            entry["block_notified"] = True
            return False, f"⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam {BLOCK_DURATION // 60} menit!"
        return False, "__SILENT_BLOCK__"  # dah pernah dikasih tau, diem aja

    # Hapus timestamp yang udah lewat 1 menit
    entry["timestamps"] = [t for t in entry["timestamps"] if now - t < WINDOW]

    # Udah 20 pesan dalam 1 menit?
    if len(entry["timestamps"]) >= RATE_LIMIT:
        entry["blocked_until"] = now + BLOCK_DURATION
        entry["block_notified"] = True
        return False, f"⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam {BLOCK_DURATION // 60} menit!"

    entry["timestamps"].append(now)
    return True, ""


# ===================== MENU KEYBOARD =====================
# Tombol permanen di bawah chat — biar user gak perlu hafal command

MENU_KEYS = [
    [KeyboardButton("🏠 Mulai"), KeyboardButton("📖 Bantuan")],
    [KeyboardButton("📋 Daftar Topik"), KeyboardButton("⏹ Berhenti")],
]
MENU_MARKUP = ReplyKeyboardMarkup(MENU_KEYS, resize_keyboard=True)

# ===================== HANDLER PERINTAH =====================

def is_blocked(chat_id):
    """Cek apakah user sedang dalam masa block"""
    entry = user_tracking.get(chat_id)
    if entry and entry["blocked_until"] > time.time():
        return True
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start — sambutan pertama kali user chat"""
    chat_id = str(update.effective_chat.id)
    if is_blocked(chat_id):
        await update.message.reply_text("⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam 5 menit!")
        return

    # Init session di server — sekalian dapetin footer kalau session baru
    footer = ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://localhost:8000/start",
                json={"chat_id": chat_id}
            )
            data = resp.json()
            if data.get("status") == "session_baru" and data.get("footer"):
                footer = f"\n\n---\n{data['footer']}"
    except:
        pass

    await update.message.reply_text(
        "Halo! Saya Cici Anova, asisten Q&A BPS Provinsi Kepulauan Bangka Belitung.\n\n"
        "Saya bisa bantu menjawab pertanyaan seputar:\n"
        "1. SOBAT\n"
        "2. GC PBI\n"
        "3. GC PLN\n"
        "4. FASIH\n"
        "5. Pengolahan SE2026\n\n"
        "Silakan ketik pertanyaan atau gunakan menu di bawah!"
        f"{footer}",
        reply_markup=MENU_MARKUP
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help"""
    chat_id = str(update.effective_chat.id)
    if is_blocked(chat_id):
        await update.message.reply_text("⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam 5 menit!")
        return
    await update.message.reply_text(
        "Cukup ketik pertanyaan Anda, saya akan cari jawabannya "
        "dari database mengenai SOBAT, GC PBI, GC PLN, FASIH, "
        "dan Pengolahan SE2026.",
        reply_markup=MENU_MARKUP
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /topics — daftar topik"""
    chat_id = str(update.effective_chat.id)
    if is_blocked(chat_id):
        await update.message.reply_text("⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam 5 menit!")
        return
    await update.message.reply_text(
        "Topik yang saya kuasai:\n"
        "1. SOBAT\n"
        "2. GC PBI\n"
        "3. GC PLN\n"
        "4. FASIH\n"
        "5. Pengolahan SE2026",
        reply_markup=MENU_MARKUP
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /stop — akhiri sesi diskusi"""
    chat_id = str(update.effective_chat.id)
    if is_blocked(chat_id):
        await update.message.reply_text("⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam 5 menit!")
        return
    # Reset tracking lokal
    user_tracking.pop(chat_id, None)
    # Panggil server buat reset session juga
    end_msg = "Sesi diskusi telah diakhiri."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://localhost:8000/stop",
                json={"chat_id": chat_id}
            )
            data = resp.json()
            if data.get("message"):
                end_msg = data["message"]
    except:
        pass
    await update.message.reply_text(
        f"{end_msg}\n\n"
        "Silakan kirim pesan atau tap Mulai untuk memulai lagi.",
        reply_markup=MENU_MARKUP
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler utama — semua pesan teks masuk sini"""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)  # ID unik percakapan
    text = update.message.text.strip()

    if not text:
        return

    # ===================== ANTI-SPAM =====================
    init_entry(chat_id)
    entry = user_tracking[chat_id]

    if user_id not in TRUSTED_USERS:

        allowed, msg = check_rate_limit(chat_id, text)
        if not allowed:
            if msg != "__SILENT_BLOCK__":
                await update.message.reply_text(msg)
            return

    # Simpan tracking
    entry["last_active"] = time.time()

    # ===================== TOMBOL MENU (Bahasa Indonesia) =====================
    # User yg sedang diblokir gak bisa akses menu manapun
    if is_blocked(chat_id):
        await update.message.reply_text("⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam 5 menit!")
        return
    if text in ["🏠 Mulai", "Mulai"]:
        await start(update, context)
        return
    if text in ["📖 Bantuan", "Bantuan"]:
        await help_command(update, context)
        return
    if text in ["📋 Daftar Topik", "Daftar Topik"]:
        await topics_command(update, context)
        return
    if text in ["⏹ Berhenti", "Berhenti"]:
        await stop_command(update, context)
        return

    # Kirim typing indicator biar user tau bot lagi mikir
    await update.message.chat.send_action("typing")

    # ===================== PANGGIL SERVER API =====================
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                CHATBOT_URL,
                json={"pertanyaan": text, "chat_id": chat_id}
            )
        data = resp.json()
        jawaban = data.get("jawaban", "Error: tidak ada jawaban")
        await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP)
    except Exception as e:
        await update.message.reply_text(f"Maaf, terjadi error: {str(e)}", reply_markup=MENU_MARKUP)


def init_entry(chat_id):
    """Inisialisasi tracking buat chat_id baru"""
    if chat_id not in user_tracking:
        user_tracking[chat_id] = {"timestamps": [], "blocked_until": 0,
                                  "last_active": 0}


# ===================== MAIN =====================

def main():
    """Set up bot dan mulai polling"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Daftarin handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daftarin command menu ke Telegram (biar muncul pas ketik /)
    try:
        httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands", json={
            "commands": [
                {"command": "start", "description": "Mulai percakapan dengan Cici Anova"},
                {"command": "help",  "description": "Panduan cara menggunakan bot"},
                {"command": "topics", "description": "Topik yang saya kuasai"},
                {"command": "stop",   "description": "Akhiri sesi diskusi"},
            ]
        })
        print("Menu commands registered!")
    except Exception as e:
        print(f"Gagal register commands: {e}")

    print("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
