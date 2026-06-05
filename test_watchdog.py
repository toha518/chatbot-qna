"""
test_watchdog.py — Kirim notif session end langsung ke Telegram
Gunanya: ngetes apakah watchdog bisa kirim notif tanpa nunggu 30 menit

Jalankan:
  python test_watchdog.py
Atau kalo mau kirim ke chat_id lain:
  python test_watchdog.py <chat_id>
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load .env dari root project
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path))
else:
    load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = sys.argv[1] if len(sys.argv) > 1 else "1267972859"

if not TOKEN or TOKEN == "***":
    print("❌ TELEGRAM_BOT_TOKEN gak kebaca dari .env")
    exit(1)

hidden = TOKEN[:6] + "..." + TOKEN[-4:]
print(f"✅ Token: {hidden}")
print(f"📨 Ngirim test notif session end ke chat_id: {CHAT_ID}")

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        msg = (
            "💬 Sesi diskusi Anda telah berakhir.\n\n"
            "Ini adalah pesan TEST — watchdog berjalan dengan normal ✅\n\n"
            "Jika pertanyaan Anda belum terjawab dengan benar, silakan ajukan "
            "pertanyaan melalui link berikut:\n📩 http://s.bps.go.id/nara-qna\n\n"
            "---\n"
            "Sesi obrolan telah ditutup, pukul 09:00 WIB, obrolan berlangsung selama 5 menit."
        )
        resp = await client.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": int(CHAT_ID), "text": msg}
        )
        if resp.status_code == 200:
            print("✅ ✅ ✅ PESAN TEST TERKIRIM!")
            print("   Cek Telegram — harusnya dapet notif session end.")
        else:
            print(f"❌ Gagal: HTTP {resp.status_code}")
            print(f"   {resp.text[:300]}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
