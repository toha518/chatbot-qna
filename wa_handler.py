# wa_handler.py — Layer WhatsApp Nara
# Tugas: nerima pesan dari WhatsApp Bridge (Node.js), kirim ke server API, balasin
# Ini cuma "jembatan" WhatsApp — logika utama tetap di server.py
#
# Cara jalanin: python wa_handler.py
# Harus bareng: server.py (di terminal lain) + node bridge.js (di terminal lain lagi)

import re
import os
import json
import tempfile
import requests
import base64
from dotenv import load_dotenv
from flask import Flask, request, jsonify

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


def _strip_markdown(text: str) -> str:
    """Konversi formatting Telegram → WhatsApp"""
    # Bold Telegram **text** → *text* (WA bold)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    # Inline code `text` → text biasa
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Strikethrough ~~text~~ → ~text~ (WA juga pake ~text~)
    text = re.sub(r'~~(.+?)~~', r'~\1~', text)
    # Heading ### → 
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text.strip()

# ===================== OCR ENGINE (EasyOCR) =====================
_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print("[OCR] Loading EasyOCR model (~500MB) — hanya sekali...")
        import easyocr
        _ocr_reader = easyocr.Reader(['id', 'en'], gpu=False)
        print("[OCR] Ready!")
    return _ocr_reader

# ===================== KONFIGURASI =====================
load_dotenv()
FLASK_PORT = int(os.getenv("WA_FLASK_PORT", "3001"))
SERVER_URL = os.getenv("CHATBOT_URL") or "http://localhost:8000"

app = Flask(__name__)

# ===================== ENDPOINT UTAMA =====================
@app.route("/wa-message", methods=["POST"])
def wa_message():
    """
    Dipanggil oleh bridge.js setiap ada pesan WhatsApp masuk.
    """
    data = request.json
    if not data:
        return jsonify({"error": "no data"}), 400

    sender = data.get("sender", "default")
    message = data.get("message", "")
    is_image = data.get("is_image", False)

    # ===================== PROSES GAMBAR =====================
    if is_image:
        try:
            payload = json.loads(message)
            caption = payload.get("text", "")
            image_b64 = payload.get("image_base64", "")
            mimetype = payload.get("mimetype", "image/jpeg")

            if image_b64:
                image_bytes = base64.b64decode(image_b64)
                reader = get_ocr_reader()
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp.write(image_bytes)
                    tmp_path = tmp.name

                result = reader.readtext(tmp_path)
                os.unlink(tmp_path)

                ocr_text = ' '.join([item[1] for item in result if item[2] > 0.3])
                if caption and ocr_text:
                    pertanyaan = f"{caption}\n\n[Gambar: {ocr_text}]"
                elif ocr_text:
                    pertanyaan = f"[Gambar: {ocr_text}]"
                else:
                    pertanyaan = caption

                if not pertanyaan.strip():
                    return jsonify({"jawaban": _RESPONSES.get("image_no_text", "⚠️ Tidak bisa membaca teks dari gambar. Silakan ketik manual.")})
            else:
                pertanyaan = caption
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WA OCR ERROR] {e}")
            pertanyaan = message
    else:
        pertanyaan = message

    # ===================== COMMAND HANDLER (seperti /start di Telegram) =====================
    cmd = pertanyaan.strip().lower()

    # Feedback button dari WhatsApp (user pencet tombol ✅ Sudah / ❌ Belum)
    if cmd in ['✅ sudah', 'sudah']:
        payload = {"pertanyaan": "feedback_yes", "chat_id": sender, "source": "wa"}
        try:
            api_url = SERVER_URL if SERVER_URL.endswith('/chat') else f"{SERVER_URL}/chat"
            resp = requests.post(api_url, json=payload, timeout=30)
            data = resp.json()
            return jsonify({"jawaban": _strip_markdown(data.get("jawaban", ""))})
        except Exception as e:
            print(f"[WA FB] Error: {e}")

    if cmd in ['❌ belum', 'belum']:
        payload = {"pertanyaan": "feedback_no", "chat_id": sender, "source": "wa"}
        try:
            api_url = SERVER_URL if SERVER_URL.endswith('/chat') else f"{SERVER_URL}/chat"
            resp = requests.post(api_url, json=payload, timeout=30)
            data = resp.json()
            return jsonify({"jawaban": _strip_markdown(data.get("jawaban", ""))})
        except Exception as e:
            print(f"[WA FB] Error: {e}")

    if cmd == '/start':
        topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(_IDENTITY.get("topics", [])))
        name = _IDENTITY.get("name", "Nara")
        role = _IDENTITY.get("role", "asisten IT")
        return jsonify({
            "jawaban": _RESPONSES.get("greeting", "").format(
                name=name,
                role=role,
                topics_list=topics_list
            )
        })
    if cmd == '/help':
        topics_line = ", ".join(_IDENTITY.get("topics", []))
        return jsonify({
            "jawaban": (
                "Cukup ketik pertanyaan Anda, saya akan bantu cari solusinya "
                f"dari database mengenai {topics_line}."
            )
        })
    if cmd == '/topics':
        topics = _IDENTITY.get("topics", [])
        topics_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics))
        return jsonify({
            "jawaban": f"Topik permasalahan IT yang saya kuasai:\n{topics_text}"
        })
    if cmd == '/stop':
        # Ambil base URL (strip /chat kalau ada)
        base_url = SERVER_URL.replace('/chat', '')
        try:
            resp = requests.post(f"{base_url}/stop", json={"chat_id": sender}, timeout=10)
            data = resp.json()
            end_msg = data.get("message", "Sesi diskusi telah diakhiri.")
        except Exception:
            end_msg = "Sesi diskusi telah diakhiri."
        return jsonify({
            "jawaban": f"{end_msg}\n\nSilakan kirim /start untuk memulai lagi."
        })

    # ===================== INPUT SANITASI =====================
    pertanyaan = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', pertanyaan)
    emoji_pattern = re.compile(r'[\U0001F300-\U0010FFFF]')
    emojis = emoji_pattern.findall(pertanyaan)
    if len(emojis) > 5:
        for em in set(emojis[5:]):
            pertanyaan = pertanyaan.replace(em, '')

    if len(pertanyaan.strip()) == 0:
        return jsonify({"jawaban": _RESPONSES.get("question_empty", "⚠️ Pesan kosong setelah penyaringan.")})

    # Character limit hanya untuk teks biasa (bukan OCR)
    if not is_image:
        if len(pertanyaan) > 500:
            return jsonify({"jawaban": _RESPONSES.get("question_too_long", "⚠️ Pertanyaan terlalu panjang. Maksimal {max_length} karakter.").format(max_length=500)})

    # ===================== PANGGIL SERVER API =====================
    try:
        # CHATBOT_URL udah include /chat, jadi jangan ditambahin lagi
        api_url = SERVER_URL if SERVER_URL.endswith('/chat') else f"{SERVER_URL}/chat"
        payload = {"pertanyaan": pertanyaan, "chat_id": sender, "source": "wa"}
        if is_image:
            payload["is_ocr"] = True
        resp = requests.post(
            api_url,
            json=payload,
            timeout=120
        )
        data = resp.json()
        jawaban = data.get("jawaban", "Error: tidak ada jawaban")
        # Strip markdown — WA gak support formatting
        return jsonify({"jawaban": _strip_markdown(jawaban)})

    except requests.exceptions.ConnectionError:
        return jsonify({
            "jawaban": _RESPONSES.get("server_down", "⚠️ Server Nara tidak merespon.")
        }), 503
    except Exception as e:
        print(f"[WA ERROR] Panggil server.py gagal: {e}")
        return jsonify({"jawaban": _RESPONSES.get("image_failed", "⚠️ Error: {error}").format(error=str(e))}), 500


# ===================== HEALTH CHECK =====================
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "wa-handler", "server_url": SERVER_URL})


# ===================== MAIN =====================
if __name__ == "__main__":
    print(f"[BOOT] WhatsApp Handler Nara")
    print(f"[BOOT] Server API: {SERVER_URL}")
    print(f"[BOOT] Flask port: {FLASK_PORT}")
    print(f"[BOOT] Jalanin 3 terminal:")
    print(f"       1. python server.py")
    print(f"       2. python wa_handler.py")
    print(f"       3. cd whatsapp-bridge && node bridge.js")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
