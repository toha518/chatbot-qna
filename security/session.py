# security/session.py — Session management, watchdog, Telegram notif

import time
import asyncio
import httpx
import os
from datetime import datetime, timezone, timedelta

# ===================== KONFIGURASI =====================
SESSION_TIMEOUT = 1800      # 30 menit idle → session expired
MAX_HISTORY = 10            # Maks 10 tanya-jawab per session

# Telegram API untuk notifikasi watchdog
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN else None
)

# State per-user
sessions: dict = {}                  # {chat_id: [list of messages]}
session_activity: dict = {}          # {chat_id: timestamp_terakhir}
session_start_times: dict = {}       # {chat_id: timestamp_mulai}
session_notified: set = set()        # chat_id yang sudah dikirimin notif
session_expired_queue: list = []     # Antrian yang perlu dikirimin notif


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
    return (
        f"💬 Sesi diskusi Anda telah berakhir. "
        f"Mulai diskusi lagi jika masih ada pertanyaan. "
        f"Jika jawaban kurang memuaskan, "
        f"dapat menghubungi pegawai BPS Provinsi Kepulauan Bangka Belitung.\n\n"
        f"---\n"
        f"Sesi obrolan telah ditutup, pukul {now_str} WIB, "
        f"obrolan berlangsung selama {durasi_str}."
    )


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
    while True:
        try:
            now = time.time()
            expired = [
                cid for cid, last in list(session_activity.items())
                if now - last > SESSION_TIMEOUT
            ]
            for cid in expired:
                sessions.pop(cid, None)
                session_activity.pop(cid, None)
                end_msg = format_end_msg(cid, now)
                session_start_times.pop(cid, None)
                session_notified.discard(cid)

                # Kirim notif cuma kalo ini Telegram chat_id (numeric, bukan WA)
                if TELEGRAM_API and cid.lstrip('-').isdigit():
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            await client.post(
                                f"{TELEGRAM_API}/sendMessage",
                                json={"chat_id": int(cid), "text": end_msg}
                            )
                        print(f"[WATCHDOG] Notif session ended → {cid}")
                    except Exception as e:
                        print(f"[WATCHDOG] Gagal kirim ke {cid}: {e}")
                elif not cid.lstrip('-').isdigit():
                    print(f"[WATCHDOG] Skip notif WA: {cid}")

            # Proses antrian dari cleanup_sessions()
            while session_expired_queue:
                cid = session_expired_queue.pop(0)
                if cid not in expired and TELEGRAM_API and cid.lstrip('-').isdigit():
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            await client.post(
                                f"{TELEGRAM_API}/sendMessage",
                                json={
                                    "chat_id": int(cid),
                                    "text": format_end_msg(cid)
                                }
                            )
                        print(f"[WATCHDOG] Queue notif → {cid}")
                    except Exception as e:
                        print(f"[WATCHDOG] Gagal queue kirim ke {cid}: {e}")

        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")

        await asyncio.sleep(15)
