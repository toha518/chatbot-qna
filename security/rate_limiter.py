# security/rate_limiter.py — Anti-spam & rate limiting (layer API)

import re
import time
import json
import os

# Load spam messages dari prompts/responses.json
_RESPONSES = {}
_resp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "responses.json")
if os.path.exists(_resp_path):
    with open(_resp_path, "r", encoding="utf-8") as f:
        _RESPONSES = json.load(f)

# ===================== KONFIGURASI =====================
RATE_LIMIT = 5          # Maks 5 pesan per menit
WINDOW = 60             # Jendela waktu (detik)
BLOCK_DURATION = 300    # 5 menit block
# Baca trusted chat IDs dari .env (pisah pake koma)
# Contoh: TRUSTED_CHAT_IDS=1267972859,987654321
TRUSTED_IDS: set[str] = set()

# Diisi pas startup dari server.py
TRUSTED_IDS_INITIALIZED = False


def init_trusted_ids(env_value: str):
    """Isi TRUSTED_IDS dari string .env"""
    global TRUSTED_IDS
    if env_value and env_value.strip():
        ids = [x.strip() for x in env_value.split(",") if x.strip()]
        TRUSTED_IDS.clear()
        TRUSTED_IDS.update(ids)
        print(f"[SECURITY] Trusted IDs: {TRUSTED_IDS}")
    else:
        TRUSTED_IDS.clear()
        print("[SECURITY] Trusted IDs: (kosong)")

# State per chat_id
# Format: {chat_id: {"timestamps": [], "blocked_until": 0,
#                    "last_active": 0,
#                    "block_notified": False}}
api_rate_limit: dict = {}

# ── Image rate limiter: 1 gambar per 1 menit per user ──
_image_last_time: dict[str, float] = {}
_IMAGE_COOLDOWN = 60  # 1 menit


def check_image_rate_limit(chat_id: str) -> bool:
    """
    Cek apakah user boleh kirim gambar.
    1 gambar per 60 detik per chat_id.
    Return True kalo boleh, False kalo masih cooldown.
    """
    now = time.time()
    last = _image_last_time.get(chat_id, 0)
    if now - last < _IMAGE_COOLDOWN:
        remaining = int(_IMAGE_COOLDOWN - (now - last))
        print(f"[IMAGE LIMIT] {chat_id} cooldown — tunggu {remaining}s")
        return False
    _image_last_time[chat_id] = now
    return True


def normalize(text: str) -> str:
    """Bersihin teks: lowercase, buang tanda baca, normalize spasi"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def clear_image_rate_limit(chat_id: str):
    """Reset image rate limit untuk chat_id tertentu (manual override)"""
    _image_last_time.pop(chat_id, None)


def init_rate_limit_entry(chat_id: str):
    """Pastikan entry ada di api_rate_limit"""
    if chat_id not in api_rate_limit:
        api_rate_limit[chat_id] = {
            "timestamps": [],
            "blocked_until": 0,
            "last_active": 0,
            "block_notified": False
        }


def check_api_rate_limit(chat_id: str):
    """
    Rate limiter: 5 request per menit per chat_id.
    - Kena limit → block 5 menit
    - Peringatan cuma sekali, sisanya silent
    Returns (allowed: bool, message: str)
    """
    now = time.time()
    init_rate_limit_entry(chat_id)
    entry = api_rate_limit[chat_id]

    # Lagi diblokir?
    if entry["blocked_until"] > now:
        if not entry["block_notified"]:
            entry["block_notified"] = True
            return False, _RESPONSES.get("spam_warning").format(minutes=BLOCK_DURATION // 60)
        return False, "__SILENT_BLOCK__"

    # Hapus timestamp expired (> 1 menit)
    entry["timestamps"] = [t for t in entry["timestamps"] if now - t < WINDOW]

    # Udah 5? Block!
    if len(entry["timestamps"]) >= RATE_LIMIT:
        entry["blocked_until"] = now + BLOCK_DURATION
        entry["block_notified"] = True
        return False, _RESPONSES.get("spam_warning", "").format(minutes=BLOCK_DURATION // 60)

    entry["timestamps"].append(now)
    return True, ""
