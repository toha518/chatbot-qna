# security/session.py — Session management, watchdog, Telegram notif

import time
import asyncio
import httpx
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load .env — cari dari directory file ini, naik ke project root
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path))
else:
    load_dotenv()  # fallback ke CWD

# ===================== KONFIGURASI =====================
SESSION_TIMEOUT = 3600      # 1 jam idle → session expired
MAX_HISTORY = 10            # Maks 10 tanya-jawab per session

# Load responses.json untuk template
_RESPONSES_DIR = Path(__file__).parent.parent / "prompts" / "responses.json"
_RESPONSES = {}
if _RESPONSES_DIR.exists():
    try:
        with open(_RESPONSES_DIR, "r", encoding="utf-8") as f:
            _RESPONSES = json.load(f)
    except Exception as e:
        print(f"[WATCHDOG] ⚠️ Gagal load responses.json: {e}")
if not _RESPONSES.get("session_ending_idle"):
    print(f"[WATCHDOG] ⚠️ session_ending_idle kosong di responses.json")

# Watchdog toggle — notif session ended
WATCHDOG_ENABLED = os.getenv("WATCHDOG_ENABLED", "true").lower() in ("true", "1", "yes")
print(f"[WATCHDOG] WATCHDOG_ENABLED={'true' if WATCHDOG_ENABLED else 'false'} — {'notif aktif' if WATCHDOG_ENABLED else 'notif dimatikan'}")

# Telegram API untuk notifikasi watchdog
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN else None
)
# Debug token
if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "***":
    hidden = TELEGRAM_BOT_TOKEN[:6] + "..." + TELEGRAM_BOT_TOKEN[-4:]
    print(f"[WATCHDOG] TELEGRAM_BOT_TOKEN loaded ({hidden})")
else:
    print(f"[WATCHDOG] ⚠️ TELEGRAM_BOT_TOKEN tidak terbaca! Notif session expired gak akan dikirim.")
    print(f"[WATCHDOG]    Cek .env: pastikan TELEGRAM_BOT_TOKEN diisi dengan token asli dari @BotFather")

# WhatsApp Bridge URL untuk notifikasi session expired
WA_BRIDGE_URL = os.getenv("WA_BRIDGE_URL", "http://localhost:3000")

# ── Shared httpx client buat watchdog ──
_watchdog_client: httpx.AsyncClient | None = None
async def _get_watchdog_client():
    global _watchdog_client
    if _watchdog_client is None:
        _watchdog_client = httpx.AsyncClient(timeout=10, limits=httpx.Limits(max_keepalive_connections=5))
    return _watchdog_client

# State per-user
sessions: dict = {}                  # {chat_id: [list of messages]}
session_activity: dict = {}          # {chat_id: timestamp_terakhir}
session_start_times: dict = {}       # {chat_id: timestamp_mulai}
session_notified: set = set()        # chat_id yang sudah dikirimin notif
session_expired_queue: list = []     # Antrian yang perlu dikirimin notif
session_has_forward: dict[str, bool] = {}  # {chat_id: pernah dapat forward?}


def format_durasi(detik: float) -> str:
    """Format durasi: '2 jam 15 menit' / '5 menit' / 'kurang dari 1 menit'"""
    total_menit = int(detik / 60)
    if total_menit < 1:
        return "kurang dari 1 menit"
    jam = total_menit // 60
    menit = total_menit % 60
    if jam > 0 and menit > 0:
        return f"{jam} jam {menit} menit"
    elif jam > 0:
        return f"{jam} jam"
    else:
        return f"{menit} menit"


def format_end_msg(cid: str, now_ts: float = None) -> str:
    """Format pesan penutup session dengan jam & durasi"""
    if now_ts is None:
        now_ts = time.time()
    wib = timezone(timedelta(hours=7))
    now_str = datetime.fromtimestamp(now_ts, wib).strftime("%H:%M")
    start = session_start_times.get(cid)
    durasi_str = format_durasi(now_ts - start) if start else "-"
    # Fallback hardcoded — jaga-jaga kalo responses.json gagal di-load
    _fb_ended = _RESPONSES.get("session_ended", "")
    if not _fb_ended:
        _fb_ended = "Sesi obrolan telah ditutup, pukul {time} WIB, obrolan berlangsung selama {duration}."
    _fb_idle = _RESPONSES.get("session_ending_idle", "")
    if not _fb_idle:
        _fb_idle = "💬 Sesi diskusi Anda telah berakhir."
    ended_part = _fb_ended.format(time=now_str, duration=durasi_str)
    return _fb_idle.format(ended=ended_part)


def cleanup_sessions():
    """Hapus session yang udah expired (>30 menit idle)"""
    now = time.time()
    expired = [
        cid for cid, last in list(session_activity.items())
        if now - last > SESSION_TIMEOUT
    ]
    for cid in expired:
        sessions.pop(cid, None)
        session_activity.pop(cid, None)
        session_start_times.pop(cid, None)
        session_notified.discard(cid)
        session_has_forward.pop(cid, None)
        session_expired_queue.append(cid)


def init_session(cid: str):
    """
    Init atau resume session untuk user.
    Returns (history_list, is_session_baru: bool).
    """
    session_baru = False
    if cid not in sessions:
        sessions[cid] = []
        session_start_times[cid] = time.time()
        session_baru = True

    history = sessions[cid]
    session_activity[cid] = time.time()

    if cid not in session_has_forward:
        session_has_forward[cid] = False

    # Batasi history — maks 10 tanya-jawab
    while len(history) > MAX_HISTORY * 2:
        history.pop(0)
        history.pop(0)

    return history, session_baru


async def session_watchdog():
    """
    Background task: tiap 15 detik scan session_activity.
    Kalau ada yang expired → hapus session + kirim notif Telegram.
    """
    await asyncio.sleep(10)
    print("[WATCHDOG] 🟢 Started!")
    while True:
        try:
            now = time.time()
            # print(f"[WATCHDOG] Scan: {len(session_activity)} sessions active")  # di-spam, hidden
            expired = [
                cid for cid, last in list(session_activity.items())
                if now - last > SESSION_TIMEOUT
            ]
            if expired:
                print(f"[WATCHDOG] 🔴 {len(expired)} expired: {expired}")
            for cid in expired:
                sessions.pop(cid, None)
                session_activity.pop(cid, None)
                end_msg = format_end_msg(cid, now)
                session_start_times.pop(cid, None)
                session_notified.discard(cid)
                session_has_forward.pop(cid, None)

                if not WATCHDOG_ENABLED:
                    print(f"[WATCHDOG] ⏭️ Skip notif {cid} — watchdog dimatikan (.env)")
                    continue

                if cid.lstrip('-').isdigit():
                    # Telegram — kirim via Bot API
                    if TELEGRAM_API and TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != '***':
                        try:
                            client = await _get_watchdog_client()
                            resp = await client.post(
                                f"{TELEGRAM_API}/sendMessage",
                                json={"chat_id": int(cid), "text": end_msg}
                            )
                            if resp.status_code == 200:
                                print(f"[WATCHDOG] ✅ Notif session ended → {cid}")
                            else:
                                body = resp.text[:200]
                                print(f"[WATCHDOG] Gagal kirim TG {cid}: HTTP {resp.status_code} — {body}")
                        except Exception as e:
                            print(f"[WATCHDOG] Gagal kirim TG {cid}: {e}")
                    else:
                        print(f"[WATCHDOG] TELEGRAM_BOT_TOKEN gak di-set atau masih placeholder '***' — skip notif ke {cid}")
                else:
                    # WhatsApp — kirim via bridge /send
                    try:
                        client = await _get_watchdog_client()
                        resp = await client.post(
                            f"{WA_BRIDGE_URL}/send",
                            json={"to": cid, "message": end_msg}
                        )
                        if resp.status_code == 200:
                            print(f"[WATCHDOG] ✅ Notif session ended → {cid} (WA)")
                        else:
                            print(f"[WATCHDOG] Gagal kirim WA {cid}: HTTP {resp.status_code} — {resp.text[:200]}")
                    except Exception as e:
                        print(f"[WATCHDOG] Gagal kirim WA {cid}: {e}")

            # Proses antrian dari cleanup_sessions()
            while session_expired_queue:
                cid = session_expired_queue.pop(0)
                if cid in expired:
                    continue
                end_msg = format_end_msg(cid)
                if not WATCHDOG_ENABLED:
                    print(f"[WATCHDOG] ⏭️ Skip queue notif {cid} — watchdog dimatikan (.env)")
                    continue
                if cid.lstrip('-').isdigit():
                    # Telegram
                    if TELEGRAM_API and TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != '***':
                        try:
                            client = await _get_watchdog_client()
                            resp = await client.post(
                                f"{TELEGRAM_API}/sendMessage",
                                json={"chat_id": int(cid), "text": end_msg}
                            )
                            if resp.status_code == 200:
                                print(f"[WATCHDOG] ✅ Queue notif TG → {cid}")
                            else:
                                print(f"[WATCHDOG] Queue gagal kirim TG {cid}: HTTP {resp.status_code}")
                        except Exception as e:
                            print(f"[WATCHDOG] Gagal queue kirim TG {cid}: {e}")
                else:
                    # WhatsApp
                    try:
                        client = await _get_watchdog_client()
                        resp = await client.post(
                            f"{WA_BRIDGE_URL}/send",
                            json={"to": cid, "message": end_msg}
                        )
                        if resp.status_code == 200:
                            print(f"[WATCHDOG] ✅ Queue notif WA → {cid}")
                        else:
                            print(f"[WATCHDOG] Gagal kirim WA {cid}: HTTP {resp.status_code} — {resp.text[:200]}")
                    except Exception as e:
                        print(f"[WATCHDOG] Gagal queue kirim WA {cid}: {e}")

        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")

        await asyncio.sleep(15)
