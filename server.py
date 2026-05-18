# server.py — API Server Cici Anova
# Tugas:
#   1. Download & index database FAQ dari Google Sheets
#   2. Cari pertanyaan user ke database pake E5-base (semantic search)
#   3. Kirim konteks ke DeepSeek AI buat nulis jawaban
#   4. Anti-spam, session tracking, watchdog notif session expired
#
# Stack: FastAPI (web) + E5-base (retrieval) + DeepSeek (LLM)

import pickle
import numpy as np
import re
import time
import asyncio
import sqlite3
from difflib import SequenceMatcher
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import csv
import urllib.request
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv()  # baca .env (kalo ada)

# ===================== DATABASE SQLITE =====================
DB_PATH = os.path.join(os.path.dirname(__file__), "cici_anova.db")


def init_db():
    """Bikin tabel kalau belum ada"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            waktu TIMESTAMP NOT NULL,
            pertanyaan TEXT NOT NULL,
            jawaban TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_id ON chat_logs(chat_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waktu ON chat_logs(waktu)")
    conn.commit()
    conn.close()
    print(f"[DB] SQLite ready: {DB_PATH}")


init_db()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ===================== DATABASE FAQ (Google Sheets) =====================
# Semua pertanyaan & jawaban disimpan di Google Spreadsheet...
# ...pas server nyala, auto-download & di-index pake MiniLM
# Link ini dari menu: File → Share → Publish to web → CSV

GSHEET_CSV_URL = os.getenv("GSHEET_CSV_URL")  # WAJIB diisi di .env


def load_from_gsheet():
    """
    Download CSV dari Google Sheets, parse, encode ulang pake MiniLM
    Prioritas utama: Google Sheets. Kalau gagal, fallback ke file pickle.
    """
    global questions, answers, categories, question_vecs
    try:
        resp = urllib.request.urlopen(GSHEET_CSV_URL, timeout=30)
        raw = resp.read().decode("utf-8")
        lines = raw.splitlines()
        reader = csv.reader(lines)
        next(reader)  # skip header (baris 1: No,Kategori,Pertanyaan,Jawaban)

        qa = []
        cats = []
        for r in reader:
            if len(r) >= 4:
                k = r[1].strip()  # kolom Kategori
                q = r[2].strip()  # kolom Pertanyaan
                a = r[3].strip()  # kolom Jawaban
                if q and a:
                    qa.append((q, a))
                    cats.append(k)

        if not qa:
            raise Exception("Data kosong dari Google Sheets")

        questions = [q for q, a in qa]
        answers   = [a for q, a in qa]
        categories = cats

        # Encode ulang pake E5 — pake prefix "passage:" sesuai spesifikasi model
        print(f"[RELOAD] Encoding {len(questions)} pertanyaan...")
        question_vecs = embedder.encode(["passage: " + q for q in questions], show_progress_bar=False)

        # Backup ke file pickle (fallback kalau next startup Google Sheets error)
        with open("qna_index.pkl", "wb") as f:
            pickle.dump({"questions": questions, "answers": answers, "categories": categories}, f)


        print(f"[RELOAD] {len(questions)} Q&A loaded from Google Sheets")
        return len(questions)

    except Exception as e:
        print(f"[RELOAD] Gagal load dari Google Sheets: {e}")
        # Fallback: pake pickle yang tersimpan sebelumnya
        if not questions:
            with open("qna_index.pkl", "rb") as f:
                data = pickle.load(f)
            questions = data["questions"]
            answers = data["answers"]
            categories = data.get("categories", [""] * len(questions))
            question_vecs = embedder.encode(["passage: " + q for q in questions], show_progress_bar=False)
        return len(questions)


# Variabel global — diisi pas startup / reload
questions = []
answers = []
categories = []
question_vecs = None


# ===================== E5 ENGINE (Semantic Search) =====================
# Model E5-base (~278MB) — khusus retrieval, ngubah teks jadi vektor 768 angka
# Lebih akurat dari MiniLM karena dilatih spesifik buat Q&A matching
# Pake prefix "query:" untuk pertanyaan user, "passage:" untuk FAQ

from sentence_transformers import SentenceTransformer

print("[BOOT] Loading E5-base...")
t0 = time.time()
embedder = SentenceTransformer('intfloat/multilingual-e5-base')
print("[BOOT] Loading data...")
total = load_from_gsheet()
print(f"[BOOT] Ready! ({total} Q&A, {time.time()-t0:.1f}s)")


# ===================== LLM API (Penulis Jawaban) =====================
# Endpoint, key, model dibaca dari .env -- ganti kapan aja
# DeepSeek cuma "nulis ulang" — gak nyari data sendiri


LLM_API = os.getenv("LLM_API")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")


# ===================== TELEGRAM BOT API =====================
# Dipake watchdog buat kirim notifikasi session ended ke user

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # WAJIB diisi di .env
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ===================== ANTI-SPAM =====================
# Proteksi di layer API (backup dari anti-spam di telegram_bot.py)

RATE_LIMIT = 10             # Maks 10 pesan per menit
WINDOW = 60                  # Jendela waktu (detik)
BLOCK_DURATION = 300         # 5 menit block
SIMILARITY_THRESHOLD = 0.85  # Ambang fuzzy duplicate
SESSION_TIMEOUT = 1800       # 30 menit reset tracker
TRUSTED_IDS = {}             # User yg skip anti-spam

# Tiap chat_id punya: timestamps, blocked_until, last_text, last_active, block_notified
api_rate_limit = {}


def normalize(text):
    """Bersihin teks: lowercase, buang tanda baca, normalize spasi"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def is_duplicate(chat_id, text):
    """Cek duplikat pesan — fuzzy match + session-based"""
    now = time.time()
    entry = api_rate_limit.get(chat_id)
    if not entry or not entry["last_text"]:
        return False
    if now - entry["last_active"] > SESSION_TIMEOUT:
        entry["last_text"] = ""
        return False
    last_norm = normalize(entry["last_text"])
    curr_norm = normalize(text)
    if last_norm == curr_norm:
        return True
    ratio = SequenceMatcher(None, last_norm, curr_norm).ratio()
    return ratio >= SIMILARITY_THRESHOLD


def check_api_rate_limit(chat_id):
    """
    Rate limiter: 20 request per menit
    - Kalau kena limit → block 5 menit
    - Peringatan cuma sekali, sisanya silent
    """
    now = time.time()
    if chat_id not in api_rate_limit:
        api_rate_limit[chat_id] = {"timestamps": [], "blocked_until": 0,
                                   "last_text": "", "last_active": 0, "block_notified": False,
                                   "rest_until": 0}
    entry = api_rate_limit[chat_id]

    # Lagi diblokir?
    if entry["blocked_until"] > now:
        if not entry["block_notified"]:
            entry["block_notified"] = True
            return False, f"⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam {BLOCK_DURATION // 60} menit!"
        return False, "__SILENT_BLOCK__"

    # Hapus timestamp yg udah expired (lebih dari 1 menit)
    entry["timestamps"] = [t for t in entry["timestamps"] if now - t < WINDOW]

    # Udah 20? Block!
    if len(entry["timestamps"]) >= RATE_LIMIT:
        entry["blocked_until"] = now + BLOCK_DURATION
        entry["block_notified"] = True
        return False, f"⚠️ Kamu terdeteksi melakukan spam. Coba lagi dalam {BLOCK_DURATION // 60} menit!"

    entry["timestamps"].append(now)
    return True, ""


# ===================== SESSION MANAGEMENT =====================
# Session: kumpulan chat history per user
# - Setiap user punya 1 session
# - Session expired setelah 30 menit gak ada chat
# - Kalau expired: watchdog kirim notif Telegram + history dihapus

sessions = {}
SESSION_TIMEOUT_HISTORY = 1800
session_activity = {}       # {chat_id: timestamp_terakhir_chat}
session_start_times = {}    # {chat_id: timestamp_mulai_session}
session_notified = set()    # chat_id yang udah dikirimin notif
# chat_history pake SQLite — file cici_anova.db


def format_durasi(detik):
    """Format durasi: X jam Y menit / X menit / kurang dari 1 menit"""
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


def format_end_msg(cid, now_ts=None):
    """Format pesan penutup session dengan jam & durasi"""
    if now_ts is None:
        now_ts = time.time()
    wib = timezone(timedelta(hours=7))
    now_str = datetime.fromtimestamp(now_ts, wib).strftime("%H:%M")
    start = session_start_times.get(cid)
    if start:
        durasi_str = format_durasi(now_ts - start)
    else:
        durasi_str = "-"
    return (
        f"💬 Sesi diskusi Anda telah berakhir. "
        f"Mulai diskusi lagi jika masih ada pertanyaan. "
        f"Jika jawaban kurang memuaskan, "
        f"dapat menghubungi pegawai BPS Provinsi Kepulauan Bangka Belitung.\n\n"
        f"---\n"
        f"Sesi obrolan telah ditutup, pukul {now_str} WIB, "
        f"obrolan berlangsung selama {durasi_str}."
    )


class ChatRequest(BaseModel):
    """Struktur request POST /chat"""
    pertanyaan: str
    chat_id: str = "default"


class StopRequest(BaseModel):
    """Struktur request POST /stop"""
    chat_id: str


def cleanup_sessions():
    """Panggil tiap ada request chat: hapus session yg expired >30 menit"""
    now = time.time()
    expired = [cid for cid, last in session_activity.items() if now - last > SESSION_TIMEOUT_HISTORY]
    for cid in expired:
        sessions.pop(cid, None)
        session_activity.pop(cid, None)
        session_start_times.pop(cid, None)
        session_notified.discard(cid)
        session_expired_queue.append(cid)


# Antrian session expired — diproses watchdog
session_expired_queue = []
_watchdog_task = None


# ===================== BACKGROUND TASKS =====================
# Watchdog: jalan tiap 15 detik, cek session yg expired, kirim notif Telegram
# Auto-reload: tiap 10 menit, cek Google Sheets ada update

@app.on_event("startup")
async def start_watchdog():
    global _watchdog_task
    _watchdog_task = asyncio.create_task(session_watchdog())
    _reload_task = asyncio.create_task(auto_reload_gsheet())
    print("[BOOT] Watchdog + auto-reload started")


async def auto_reload_gsheet():
    """Tiap 10 menit: download ulang database dari Google Sheets"""
    await asyncio.sleep(60)  # kasih waktu server stabil dulu
    while True:
        await asyncio.sleep(600)  # 10 menit
        try:
            prev = len(questions)
            total = load_from_gsheet()
            if total != prev:
                print(f"[AUTO-RELOAD] Database updated: {prev} → {total} Q&A")
            else:
                print(f"[AUTO-RELOAD] Checked: {total} Q&A (no change)")
        except Exception as e:
            print(f"[AUTO-RELOAD] Error: {e}")


async def session_watchdog():
    """
    Background task: tiap 15 detik scan session_activity
    Kalau ada yg expired → hapus session + kirim pesan Telegram
    """
    await asyncio.sleep(10)
    while True:
        try:
            now = time.time()
            expired = [cid for cid, last in list(session_activity.items())
                       if now - last > SESSION_TIMEOUT_HISTORY]
            now_wd = time.time()
            expired = [cid for cid, last in list(session_activity.items())
                       if now_wd - last > SESSION_TIMEOUT_HISTORY]
            for cid in expired:
                sessions.pop(cid, None)
                session_activity.pop(cid, None)
                end_msg = format_end_msg(cid, now_wd)
                session_start_times.pop(cid, None)
                session_notified.discard(cid)
                # Kirim notif lewat Telegram
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(
                            f"{TELEGRAM_API}/sendMessage",
                            json={"chat_id": int(cid), "text": end_msg}
                        )
                    print(f"[WATCHDOG] Session ended notif sent to {cid}")
                except Exception as e:
                    print(f"[WATCHDOG] Failed to send to {cid}: {e}")

            # Juga proses antrian dari cleanup_sessions
            while session_expired_queue:
                cid = session_expired_queue.pop(0)
                if cid not in expired:
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            await client.post(
                                f"{TELEGRAM_API}/sendMessage",
                                json={"chat_id": int(cid), "text": format_end_msg(cid)}
                            )
                        print(f"[WATCHDOG] Queue notif sent to {cid}")
                    except Exception as e:
                        print(f"[WATCHDOG] Failed queue send to {cid}: {e}")
        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")

        await asyncio.sleep(15)


# ===================== API ENDPOINTS =====================

@app.get("/history")
def list_history():
    """Daftar semua chat_id yang punya history (dari SQLite)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chat_id, COUNT(*) as total, MIN(waktu) as pertama
            FROM chat_logs
            GROUP BY chat_id
            ORDER BY pertama DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        wib = timezone(timedelta(hours=7))
        result = []
        for cid, total, first_ts in rows:
            first_time = datetime.fromtimestamp(first_ts, wib).strftime("%Y-%m-%d %H:%M:%S")
            result.append({
                "chat_id": cid,
                "total_chat": total,
                "pertama": first_time
            })
        return {"total_sessions": len(result), "sessions": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/history/{chat_id}")
def get_history(chat_id: str):
    """History chat per chat_id (dari SQLite)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT waktu, pertanyaan, jawaban FROM chat_logs WHERE chat_id = ? ORDER BY waktu ASC",
            (chat_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return {"chat_id": chat_id, "total": 0, "messages": []}
        wib = timezone(timedelta(hours=7))
        formatted = []
        for ts, user_q, bot_a in rows:
            t = datetime.fromtimestamp(ts, wib).strftime("%Y-%m-%d %H:%M:%S")
            formatted.append({"waktu": t, "user": user_q, "bot": bot_a})
        return {"chat_id": chat_id, "total": len(formatted), "messages": formatted}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    """Cek status server"""
    return {
        "status": "ok",
        "total_qna": len(questions),
        "engine": "E5-base",
        "source": "Google Sheets",
        "active_sessions": len(sessions)
    }


@app.post("/reload")
async def reload_data():
    """Panggil ini kalau udah edit Google Sheets — langsung update database"""
    total = load_from_gsheet()
    return {"status": "ok", "total_qna": total, "source": "Google Sheets"}


@app.post("/start")
async def start_session(req: StopRequest):
    """Init session baru — dipanggil pas user kirim /start"""
    cid = req.chat_id
    if cid not in sessions:
        sessions[cid] = []
        session_start_times[cid] = time.time()
        session_activity[cid] = time.time()
        wib = timezone(timedelta(hours=7))
        now_str = datetime.now(wib).strftime("%H:%M")
        return {
            "status": "session_baru",
            "footer": f"Sesi obrolan baru telah dibuka — pukul {now_str} WIB"
        }
    return {"status": "session_ada"}


@app.post("/stop")
async def stop_session(req: StopRequest):
    """Akhiri sesi diskusi — hapus semua tracking & session user"""
    cid = req.chat_id
    now_stop = time.time()
    wib = timezone(timedelta(hours=7))
    now_str = datetime.fromtimestamp(now_stop, wib).strftime("%H:%M")
    start = session_start_times.pop(cid, None)
    if start:
        durasi_str = format_durasi(now_stop - start)
    else:
        durasi_str = "-"
    sessions.pop(cid, None)
    session_activity.pop(cid, None)
    # api_rate_limit sengaja gak dihapus — biar rate limit tetap jalan
    return {
        "status": "ok",
        "message": f"Sesi obrolan telah ditutup, pukul {now_str} WIB, obrolan berlangsung selama {durasi_str}."
    }


# ===================== ENDPOINT UTAMA: CHAT =====================

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Alur lengkap pas user chat:
      1. Bersihin session expired
      2. Anti-spam (duplicate + rate limit)
      3. Cek greeting → langsung DeepSeek (lewat MiniLM)
      4. MiniLM: cari 5 pertanyaan paling relevan di database
      5. DeepSeek: tulis jawaban dari konteks
      6. Simpan history
      7. Return jawaban
    """
    cleanup_sessions()
    cid = req.chat_id

    # ===================== ANTI-SPAM =====================
    if cid not in api_rate_limit:
        api_rate_limit[cid] = {"timestamps": [], "blocked_until": 0,
                               "last_text": "", "last_active": 0, "block_notified": False,
                               "rest_until": 0}

    if cid not in TRUSTED_IDS:
        allowed, msg = check_api_rate_limit(cid)
        if not allowed:
            if msg == "__SILENT_BLOCK__":
                return {"jawaban": "", "skor": 0}
            return {"jawaban": msg, "skor": 0}

    api_rate_limit[cid]["last_text"] = req.pertanyaan
    api_rate_limit[cid]["last_active"] = time.time()

    # ===================== SESSION INIT / RESUME =====================
    session_baru = False
    if cid not in sessions:
        sessions[cid] = []
        session_start_times[cid] = time.time()
        session_baru = True
    history = sessions[cid]
    session_activity[cid] = time.time()

    # ===================== LONG SESSION REST (6 JAM) =====================
    # Kalo session udah berjalan > 6 jam, paksa istirahat 6 jam
    if cid not in TRUSTED_IDS:
        now_rest = time.time()
        entry_rest = api_rate_limit.get(cid)
        rest_until = entry_rest.get("rest_until", 0) if entry_rest else 0

        # Masih dalam masa istirahat?
        if rest_until > now_rest:
            sisa_menit = int((rest_until - now_rest) / 60)
            return {"jawaban": f"⛔ Anda terlalu lama mengobrol dengan Cici Anova, silahkan istirahat {sisa_menit} menit lagi!", "skor": 0}

        # Session udah > 6 jam? Blokir 6 jam
        start_rest = session_start_times.get(cid)
        if start_rest and (now_rest - start_rest) > 21600:
            api_rate_limit[cid]["rest_until"] = now_rest + 21600
            # Hapus session biar mulai dari awal setelah istirahat
            sessions.pop(cid, None)
            session_activity.pop(cid, None)
            session_start_times.pop(cid, None)
            return {"jawaban": "⛔ Anda terlalu lama mengobrol dengan Cici Anova, silahkan istirahat selama 6 jam!", "skor": 0}

    # ===================== GREETING DETECTION =====================
    # Kalau user cuma "halo" / "pagi" — langsung perkenalan via DeepSeek
    # Gak perlu MiniLM + database — lebih cepat & hemat

    greeting_set = {"halo", "hai", "hey", "hi", "pagi", "siang", "sore", "malam",
                    "assalamualaikum", "assalamu'alaikum",
                    "hello", "hallo", "helo"}
    multi_greetings = ["selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    words_lower = req.pertanyaan.lower().strip().split()
    is_greeting = bool(greeting_set & set(words_lower)) or \
                  any(g in req.pertanyaan.lower().strip() for g in multi_greetings)

    if is_greeting and len(words_lower) <= 3:
        greetings_only = [
            {"role": "system",
             "content": "Kamu adalah Cici Anova, asisten Q&A resmi BPS Provinsi "
                        "Kepulauan Bangka Belitung. Pengguna menyapa kamu. Jawab dengan "
                        "ramah, perkenalkan diri kamu sebagai Cici Anova, dan sebutkan "
                        "bahwa kamu bisa membantu menjawab pertanyaan seputar SOBAT, GC PBI, "
                        "GC PLN, FASIH, dan Pengolahan SE2026. Jawab dengan bahasa Indonesia "
                        "yang natural. Gunakan emoji secukupnya (👋😊📊) biar hangat dan bersahabat. "
                        "JANGAN gunakan **bold** atau *miring* atau formatting apapun."},
            {"role": "user", "content": req.pertanyaan}
        ]
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    LLM_API,
                    json={"model": LLM_MODEL, "messages": greetings_only, "max_tokens": 300},
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"}
                )
            jawaban = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            jawaban = ("Halo! Saya Cici Anova, asisten Q&A resmi BPS Provinsi "
                       "Kepulauan Bangka Belitung...")
        api_rate_limit[cid]["last_text"] = req.pertanyaan
        api_rate_limit[cid]["last_active"] = time.time()
        # Footer session baru (greeting)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        # Log ke SQLite
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_logs (chat_id, waktu, pertanyaan, jawaban) VALUES (?, ?, ?, ?)",
                (cid, time.time(), req.pertanyaan, jawaban)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] Gagal log chat: {e}")
        return {"jawaban": jawaban, "skor": 1.0}

    # ===================== E5 RETRIEVAL =====================
    # 1. Ubah pertanyaan user → vektor (768 angka) via E5-base
    # 2. Hitung cosine similarity dengan vektor FAQ
    # 3. Ambil top 5 kandidat
    #
    # Catatan: E5 pake prefix "query:" untuk pertanyaan user,
    # dan "passage:" untuk data FAQ (udah dipasang pas encoding)

    query_vec = embedder.encode(["query: " + req.pertanyaan])
    scores = cosine_similarity(query_vec, question_vecs).flatten()

    # Ambil top 7 kandidat — lebih banyak konteks buat DeepSeek milih sendiri
    # Daripada cuma 2, dengan 7 DeepSeek bisa bandingin mana yg paling cocok
    TOP_K = 5
    best_idx = scores.argsort()[-TOP_K:][::-1]

    context = ""
    seen_answers = set()
    for idx in best_idx:
        if scores[idx] < 0.05:
            continue  # skip yg bener-bener gak relevan
        # Deduplikasi: skip kalau jawabannya sama persis
        answer_key = answers[idx].strip()[:100]
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)
        k = categories[idx].strip() if idx < len(categories) and categories[idx].strip() else ""
        if k:
            context += f"KATEGORI: {k}\nPERTANYAAN: {questions[idx]}\nJAWABAN: {answers[idx]}\n\n"
        else:
            context += f"PERTANYAAN: {questions[idx]}\nJAWABAN: {answers[idx]}\n\n"

    if not context and len(questions) > 0:
        # Daripada kosong, ambil top 1 aja walau skornya rendah
        idx0 = best_idx[0]
        k0 = categories[idx0].strip() if idx0 < len(categories) and categories[idx0].strip() else ""
        if k0:
            context = f"KATEGORI: {k0}\nPERTANYAAN: {questions[idx0]}\nJAWABAN: {answers[idx0]}\n\n"
        else:
            context = f"PERTANYAAN: {questions[idx0]}\nJAWABAN: {answers[idx0]}\n\n"

    # ===================== LLM (Penulis Jawaban) =====================
    # System prompt: ngasih tau LLM perannya sebagai Cici Anova
    # Konteks dari E5 dikasih sebagai "Data referensi"
    # DeepSeek cuma nulis ulang — gak ngarang di luar konteks

    system = """Kamu adalah Cici Anova, asisten Q&A resmi BPS Provinsi Kepulauan Bangka Belitung.
Tugasmu membantu menjawab pertanyaan tentang SOBAT, GC PBI, GC PLN, FASIH, dan Pengolahan SE2026.

Kamu akan menerima beberapa data referensi beserta kategorinya. Pilih dan gunakan yang PALING RELEVAN dengan pertanyaan user.

PENTING — Cara menjawab:
1. Gunakan data referensi sebagai BAHAN, jangan copy-paste mentah
2. Jawab dengan bahasa Indonesia yang natural dan mudah dipahami — seperti orang ngobrol
3. Susun ulang informasinya dengan kata-katamu sendiri, jangan seperti membaca template
4. Jika datanya kurang, kombinasikan beberapa referensi yang saling melengkapi
5. Jika benar-benar tidak ada data relevan, katakan: Maaf, saya tidak menemukan jawaban yang sesuai.
6. Gunakan emoji SECUKUPNYA untuk membuat jawaban lebih hidup dan bersahabat:
   - ✅ Emoji di tempat yang pas: 📊 untuk data, 📝 untuk pendaftaran, 📞 untuk kontak, ✅ untuk konfirmasi, ❌ untuk penolakan, ⏰ untuk waktu, 💡 untuk tips
   - ✅ Maksimal 2 emoji per jawaban — jangan berlebihan
   - ✅ Hanya pake emoji yang relevan sama konteks, jangan dipaksakan
   - ❌ Jangan pake **bold** atau *miring* atau formatting apapun"""

    messages = [{"role": "system", "content": system}]
    messages.append({"role": "system", "content": f"Data referensi:\n{context}"})

    for msg in history:   # riwayat chat sebelumnya (konteks percakapan)
        messages.append(msg)

    messages.append({"role": "user", "content": req.pertanyaan})

    # Panggil LLM — retry 1x kalau gagal
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                LLM_API,
                json={"model": LLM_MODEL, "messages": messages, "max_tokens": 500, "thinking": {"type": "disabled"}},
                headers={"Authorization": f"Bearer {LLM_API_KEY}"}
            )
        result = resp.json()
        jawaban = result["choices"][0]["message"]["content"]
    except Exception as e:
        try:
            await asyncio.sleep(1)
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    LLM_API,
                    json={"model": LLM_MODEL, "messages": messages, "max_tokens": 500, "thinking": {"type": "disabled"}},
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"}
                )
            result = resp.json()
            jawaban = result["choices"][0]["message"]["content"]
        except:
            jawaban = "Maaf, terjadi error. Silakan coba lagi."

    # Simpan ke history percakapan
    history.append({"role": "user", "content": req.pertanyaan})
    history.append({"role": "assistant", "content": jawaban})
    # Log ke SQLite
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_logs (chat_id, waktu, pertanyaan, jawaban) VALUES (?, ?, ?, ?)",
            (cid, time.time(), req.pertanyaan, jawaban)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] Gagal log chat: {e}")

    # Footer session baru (kalau ini pesan pertama di session)
    if session_baru:
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib).strftime("%H:%M")
        jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"

    return {"jawaban": jawaban, "skor": float(scores[best_idx[0]])}
