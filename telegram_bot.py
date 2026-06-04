# telegram_bot.py — Layer Telegram Bot Nara
# Tugas: nerima pesan dari Telegram, kirim ke server API, balasin ke user
# Ini cuma "jembatan" — logika utama ada di server.py

import httpx                       # HTTP client buat panggil server API
import re
import os
import io
import tempfile
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from collections import defaultdict

# Load responses + identity from prompts/
_RESPONSES = {}
_IDENTITY = {}
_base_dir = os.path.dirname(os.path.abspath(__file__))
_resp_path = os.path.join(_base_dir, "prompts", "responses.json")
_id_path = os.path.join(_base_dir, "prompts", "identity.json")
if os.path.exists(_resp_path):
    with open(_resp_path, "r", encoding="utf-8") as f:
        _RESPONSES = json.load(f)
if os.path.exists(_id_path):
    with open(_id_path, "r", encoding="utf-8") as f:
        _IDENTITY = json.load(f)
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

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

    topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(_IDENTITY.get("topics", [])))
    name = _IDENTITY.get("name", "Nara")
    role = _IDENTITY.get("role", "asisten IT")
    greeting_text = _RESPONSES.get("greeting").format(
        name=name,
        role=role,
        topics_list=topics_list
    )
    await update.message.reply_text(
        greeting_text + footer,
        reply_markup=MENU_MARKUP
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /help"""
    chat_id = str(update.effective_chat.id)
    topics_line = ", ".join(_IDENTITY.get("topics", []))
    await update.message.reply_text(
        _RESPONSES.get("help_text").format(topics_line=topics_line),
        reply_markup=MENU_MARKUP
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /topics — daftar topik"""
    chat_id = str(update.effective_chat.id)
    topics = _IDENTITY.get("topics", [])
    topics_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics))
    await update.message.reply_text(
        _RESPONSES.get("topics_text").format(topics_text=topics_text),
        reply_markup=MENU_MARKUP
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /stop — akhiri sesi diskusi"""
    chat_id = str(update.effective_chat.id)
    # Panggil server buat reset session
    end_msg = _RESPONSES.get("session_ended_fallback")
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
        _RESPONSES.get("stop_command").format(end_msg=end_msg),
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
        await update.message.reply_text(_RESPONSES.get("question_empty"))
        return

    # ===================== BATAS KARAKTER =====================
    if len(text) > 500:
        await update.message.reply_text(_RESPONSES.get("question_too_long").format(max_length=500))
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
                json={"pertanyaan": text, "chat_id": chat_id, "source": "telegram"}
            )
        data = resp.json()
        jawaban = data.get("jawaban", "Error: tidak ada jawaban")
        if not jawaban:
            # Silent block — gak kirim apapun, typing auto ilang ~5 detik
            return
        # Cek apakah jawaban mengandung feedback_footer
        # Tampilkan jawaban + pertanyaan, kirim tombol sebagai inline keyboard
        _feedback_sep = "\n━━━━━━━━━━━━━━━━━━━━\n"
        if _feedback_sep in jawaban:
            answer_text, footer_part = jawaban.split(_feedback_sep, 1)
            # Ambil baris pertanyaan dari footer (baris pertama yang bukan kosong)
            footer_lines = [l.strip() for l in footer_part.split('\n') if l.strip()]
            question_line = footer_lines[0] if footer_lines else '💡 Apakah jawaban ini sudah membantu?'
            display_text = f"{answer_text}\n\n{question_line}"
            feedback_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Sudah", callback_data="fb_yes"),
                InlineKeyboardButton("❌ Belum", callback_data="fb_no"),
            ]])
            try:
                await update.message.reply_text(display_text, reply_markup=feedback_keyboard, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(display_text, reply_markup=feedback_keyboard)
        else:
            try:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP)
    except Exception as e:
        await update.message.reply_text(f"{_RESPONSES.get('error_llm', '')} {str(e)}", reply_markup=MENU_MARKUP)


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol feedback ✅ Sudah / ❌ Belum"""
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)

    if query.data == "fb_yes":
        # Kirim positive_feedback ke server — server akan stop session
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    CHATBOT_URL,
                    json={"pertanyaan": "feedback_yes", "chat_id": chat_id, "source": "telegram"}
                )
                data = resp.json()
                jawaban = data.get("jawaban", "")
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(jawaban, reply_markup=MENU_MARKUP)
        except Exception as e:
            await query.message.reply_text(f"{_RESPONSES.get('error_llm', '')} {str(e)}", reply_markup=MENU_MARKUP)

    elif query.data == "fb_no":
        # Kirim negative_feedback ke server
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    CHATBOT_URL,
                    json={"pertanyaan": "feedback_no", "chat_id": chat_id, "source": "telegram"}
                )
                data = resp.json()
                jawaban = data.get("jawaban", "")
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(jawaban, reply_markup=MENU_MARKUP)
        except Exception as e:
            await query.message.reply_text(f"{_RESPONSES.get('error_llm', '')} {str(e)}", reply_markup=MENU_MARKUP)


# ===================== MAIN =====================

# ===================== HEALTH SERVER (port 3002) =====================
HEALTH_PORT = int(os.getenv("TELEGRAM_HEALTH_PORT", "3002"))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"telegram_bot"}')
    def log_message(self, format, *args):
        pass  # silent

def start_health_server():
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    print(f"[HEALTH] Health endpoint on http://localhost:{HEALTH_PORT}")
    server.serve_forever()


def main():
    """Set up bot dan mulai polling"""
    # Start health endpoint di background thread
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Daftarin handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(feedback_callback, pattern="^fb_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.PHOTO, handle_message))
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
                await update.message.reply_text(_RESPONSES.get("image_format"))
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
                await update.message.reply_text(_RESPONSES.get("image_no_text"))
                return

            # Kirim ke server chatbot — kasih flag is_ocr biar skip 500 char limit
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    CHATBOT_URL,
                    json={"pertanyaan": combined, "chat_id": chat_id, "is_ocr": True, "source": "telegram"}
                )
            data = resp.json()
            jawaban = data.get("jawaban", "Error: tidak ada jawaban")
            # Hapus pesan "Memproses gambar..."
            try:
                await msg_processing.delete()
            except Exception:
                pass
            if not jawaban:
                # Silent block — jangan kirim apapun
                return
            try:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(jawaban, reply_markup=MENU_MARKUP)


        except Exception as e:
            try:
                await msg_processing.delete()
            except Exception:
                pass
            await update.message.reply_text(_RESPONSES.get("image_failed").format(error=str(e)), reply_markup=MENU_MARKUP)
            print(f"[IMAGE ERROR] {e}")

    # Handler untuk foto, gambar, dokumen gambar
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & filters.ChatType.PRIVATE, handle_image))
    # Handler untuk media lain (sticker, voice, video) — tetap ditolak
    async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_RESPONSES.get("text_only"))
    app.add_handler(MessageHandler(~filters.TEXT & ~filters.PHOTO & ~filters.Document.IMAGE & filters.ChatType.PRIVATE, handle_media))

    # Daftarin command menu ke Telegram (biar muncul pas ketik /)
    try:
        httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands", json={
            "commands": [
                {"command": "start", "description": "Mulai percakapan dengan Nara"},
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
