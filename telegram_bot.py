# telegram_bot.py — Layer Telegram Bot Cici Anova
# Tugas: nerima pesan dari Telegram, kirim ke server API, balasin ke user
# Ini cuma "jembatan" — logika utama ada di server.py

import httpx                       # HTTP client buat panggil server API
import re
import os
import io
import tempfile
from dotenv import load_dotenv
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===================== OCR ENGINE (EasyOCR) =====================
# Model ~500MB, di-load pas pertama kali ada gambar masuk
# Support bahasa Indonesia + Inggris
_ocr_reader = None


def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print("[OCR] Loading EasyOCR model (~500MB)...")
        import easyocr
        _ocr_reader = easyocr.Reader(['id', 'en'], gpu=False)
        print("[OCR] Ready!")
    return _ocr_reader

# ===================== KONFIGURASI =====================
load_dotenv()  # baca .env (kalo ada)

# Kalo .env gak ada (misal masih jalan di VPS), fallback ke hardcoded
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # WAJIB diisi di .env
CHATBOT_URL = os.getenv("CHATBOT_URL") or "http://localhost:8000/chat"  # aman, URL publik lokal

def normalize(text):
    """Normalisasi teks: lower case, hapus tanda baca, rapihin spasi"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # hapus tanda baca
    text = re.sub(r'\s+', ' ', text)     # normalize spasi
    return text




# ===================== MENU KEYBOARD =====================
# Tombol permanen di bawah chat — biar user gak perlu hafal command

MENU_KEYS = [
    [KeyboardButton("🏠 Mulai"), KeyboardButton("📖 Bantuan")],
    [KeyboardButton("📋 Daftar Topik"), KeyboardButton("⏹ Berhenti")],
]
MENU_MARKUP = ReplyKeyboardMarkup(MENU_KEYS, resize_keyboard=True)

# ===================== HANDLER PERINTAH =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start — sambutan pertama kali user chat"""
    chat_id = str(update.effective_chat.id)

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
    await update.message.reply_text(
        "Cukup ketik pertanyaan Anda, saya akan cari jawabannya "
        "dari database mengenai SOBAT, GC PBI, GC PLN, FASIH, "
        "dan Pengolahan SE2026.",
        reply_markup=MENU_MARKUP
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /topics — daftar topik"""
    chat_id = str(update.effective_chat.id)
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
    # Panggil server buat reset session
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

    chat_id = str(update.effective_chat.id)  # ID unik percakapan
    text = update.message.text.strip()

    if not text:
        return

    # ===================== INPUT SANITASI =====================
    # Hapus karakter kontrol (kecuali newline)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # Hapus emoji berlebih (maks 5)
    emoji_pattern = re.compile(r'[\U0001F300-\U0010FFFF]')
    emojis = emoji_pattern.findall(text)
    if len(emojis) > 5:
        for em in set(emojis[5:]):
            text = text.replace(em, '')

    if len(text.strip()) == 0:
        await update.message.reply_text("⚠️ Pesan kosong setelah penyaringan.")
        return

    # ===================== BATAS KARAKTER =====================
    if len(text) > 500:
        await update.message.reply_text("⚠️ Pertanyaan terlalu panjang. Maksimal 500 karakter.")
        return

    # ===================== TOMBOL MENU =====================
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
        try:
            await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            # Fallback: kalo markdown error, kirim plain text
            await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP)
    except Exception as e:
        await update.message.reply_text(f"Maaf, terjadi error: {str(e)}", reply_markup=MENU_MARKUP)





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
    # Tolak sticker, gambar, voice dll
    async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler gambar: download → OCR → gabung caption → kirim ke server"""
        chat_id = str(update.effective_chat.id)

        # Kirim pesan sementara biar user tau lg diproses
        msg_processing = await update.message.reply_text("⏳ Memproses gambar...", reply_markup=MENU_MARKUP)

        try:
            # Ambil foto resolusi tertinggi
            if update.message.photo:
                file_id = update.message.photo[-1].file_id
            elif update.message.document and update.message.document.mime_type.startswith('image/'):
                file_id = update.message.document.file_id
            else:
                try:
                    await msg_processing.delete()
                except Exception:
                    pass
                await update.message.reply_text("⚠️ Format tidak didukung. Kirim screenshot atau foto.")
                return

            # Download gambar
            file = await context.bot.get_file(file_id)
            image_bytes = io.BytesIO()
            await file.download_to_memory(image_bytes)
            image_bytes.seek(0)

            # OCR
            reader = get_ocr_reader()
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(image_bytes.read())
                tmp_path = tmp.name

            result = reader.readtext(tmp_path)
            os.unlink(tmp_path)

            # Ambil teks dengan confidence > 0.3
            ocr_text = ' '.join([item[1] for item in result if item[2] > 0.3])

            # Gabung caption (kalo ada) + OCR
            caption = update.message.caption or ''
            if caption and ocr_text:
                combined = f"{caption}\n\n[Gambar: {ocr_text}]"
            elif ocr_text:
                combined = f"[Gambar: {ocr_text}]"
            else:
                combined = caption

            if not combined.strip():
                await update.message.reply_text("⚠️ Tidak bisa membaca teks dari gambar. Silakan ketik manual.")
                return

            # Kirim ke server chatbot kayak chat biasa
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    CHATBOT_URL,
                    json={"pertanyaan": combined, "chat_id": chat_id}
                )
            data = resp.json()
            jawaban = data.get("jawaban", "Error: tidak ada jawaban")
            # Hapus pesan "Memproses gambar..."
            try:
                await msg_processing.delete()
            except Exception:
                pass
            try:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP)


        except Exception as e:
            try:
                await msg_processing.delete()
            except Exception:
                pass
            await update.message.reply_text(f"⚠️ Gagal memproses gambar: {str(e)}", reply_markup=MENU_MARKUP)
            print(f"[IMAGE ERROR] {e}")

    # Handler untuk foto, gambar, dokumen gambar
    app.add_handler(MessageHandler(filters.PHOTO | (filters.Document.IMAGE), handle_image))
    # Handler untuk media lain (sticker, voice, video) — tetap ditolak
    async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⚠️ Hanya menerima teks dan gambar. Silakan ketik pertanyaan Anda.")
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.PHOTO & ~filters.Document.IMAGE, handle_media))

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
