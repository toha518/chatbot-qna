# security/rate_limiter.py — Anti-spam & rate limiting (layer API)

import re
import time

# ===================== KONFIGURASI =====================
RATE_LIMIT = 5          # Maks 5 pesan per menit
WINDOW = 60             # Jendela waktu (detik)
BLOCK_DURATION = 300    # 5 menit block
TRUSTED_IDS: set[str] = set()

# State per chat_id
# Format: {chat_id: {"timestamps": [], "blocked_until": 0,
#                    "rest_until": 0, "last_active": 0,
#                    "block_notified": False}}
api_rate_limit: dict = {}


def normalize(text: str) -> str:
    """Bersihin teks: lowercase, buang tanda baca, normalize spasi"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def init_rate_limit_entry(chat_id: str):
    """Pastikan entry ada di api_rate_limit"""
    if chat_id not in api_rate_limit:
        api_rate_limit[chat_id] = {
            "timestamps": [],
            "blocked_until": 0,
            "rest_until": 0,
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
            return False, (
                f"⚠️ Kamu terdeteksi melakukan spam. "
                f"Coba lagi dalam {BLOCK_DURATION // 60} menit!"
            )
        return False, "__SILENT_BLOCK__"

    # Hapus timestamp expired (> 1 menit)
    entry["timestamps"] = [t for t in entry["timestamps"] if now - t < WINDOW]

    # Udah 5? Block!
    if len(entry["timestamps"]) >= RATE_LIMIT:
        entry["blocked_until"] = now + BLOCK_DURATION
        entry["block_notified"] = True
        return False, (
            f"⚠️ Kamu terdeteksi melakukan spam. "
            f"Coba lagi dalam {BLOCK_DURATION // 60} menit!"
        )

    entry["timestamps"].append(now)
    return True, ""
