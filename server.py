# server.py — API Server Cici Anova (Router Layer)
# Logic: core/embedder.py, core/llm.py, core/database.py
# Security: security/rate_limiter.py, security/session.py
# Prompts: prompts/identity.json, prompts/system.md, prompts/greeting.md
import re
import time
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
load_dotenv()
# ===================== MODULES =====================
from core.database import init_db, log_chat, get_chat_history, list_sessions
from core.embedder import init_data, load_from_gsheet, search, questions
from core.bm25 import check_domain, get_bm25_score
from core.query_logger import log_query, get_stats
from core.llm import (
    load_llm_config, load_prompts,
    build_greeting_prompt, build_system_prompt, call_llm
)
from security.rate_limiter import (
    check_api_rate_limit, init_rate_limit_entry, init_trusted_ids, TRUSTED_IDS, api_rate_limit
)
from security.session import (
    cleanup_sessions, init_session, session_watchdog,
    sessions, session_activity, session_start_times,
    format_durasi
)
# ===================== INIT =====================
init_db()
GSHEET_CSV_URL = os.getenv("GSHEET_CSV_URL")
if GSHEET_CSV_URL:
    total_qna = init_data(GSHEET_CSV_URL)
else:
    print("[BOOT] ⚠️ GSHEET_CSV_URL tidak di-set!")
    total_qna = 0
load_llm_config()
identity, system_template, greeting_template = load_prompts()
print(f"[BOOT] Identity: {identity['name']} — {identity['role']}")
# Init trusted IDs dari .env
init_trusted_ids(os.getenv("TRUSTED_CHAT_IDS", ""))
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# ===================== DAILY CHAT LIMIT =====================
DAILY_LIMIT = 25  # maks chat per user per hari
daily_chat_count: dict[str, dict] = {}  # {chat_id: {"date": "2026-05-20", "count": 5}}
def check_daily_limit(cid: str) -> bool:
    """Cek & increment daily chat count. Return False kalo udah > limit."""
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    entry = daily_chat_count.get(cid)
    if not entry or entry["date"] != today:
        # Reset karena udah ganti hari
        daily_chat_count[cid] = {"date": today, "count": 0}
        entry = daily_chat_count[cid]
    if entry["count"] >= DAILY_LIMIT:
        return False
    entry["count"] += 1
    return True
# ===================== REQUEST MODELS =====================
class ChatRequest(BaseModel):
    pertanyaan: str
    chat_id: str = "default"
    image_path: str = ""  # path file gambar buat OCR (dari WA bridge)
class StopRequest(BaseModel):
    chat_id: str
# ===================== BACKGROUND TASKS =====================
@app.on_event("startup")
async def start_background():
    asyncio.create_task(session_watchdog())
    if GSHEET_CSV_URL:
        asyncio.create_task(auto_reload_gsheet())
    print("[BOOT] Background tasks started")
async def auto_reload_gsheet():
    """Tiap 10 menit: download ulang database dari Google Sheets"""
    await asyncio.sleep(60)
    while True:
        await asyncio.sleep(600)
        try:
            prev = len(questions)
            total = load_from_gsheet(GSHEET_CSV_URL)
            if total != prev:
                print(f"[AUTO-RELOAD] Database: {prev} → {total} Q&A")
            else:
                print(f"[AUTO-RELOAD] Checked: {total} Q&A (no change)")
        except Exception as e:
            print(f"[AUTO-RELOAD] Error: {e}")
# ===================== API ENDPOINTS =====================
@app.get("/health")
def health():
    stats = get_stats()
    return {
        "status": "ok",
        "total_qna": len(questions),
        "engine": "E5-base",
        "source": "Google Sheets" if GSHEET_CSV_URL else "pickle",
        "active_sessions": len(sessions),
        "query_stats": stats
    }
@app.get("/log-stats")
async def query_stats():
    """Return query log statistics"""
    return get_stats()
@app.post("/reload")
async def reload_data():
    if not GSHEET_CSV_URL:
        return {"status": "error", "message": "GSHEET_CSV_URL tidak di-set"}
    total = load_from_gsheet(GSHEET_CSV_URL)
    return {"status": "ok", "total_qna": total, "source": "Google Sheets"}
@app.post("/start")
async def start_session(req: StopRequest):
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
    cid = req.chat_id
    now_stop = time.time()
    wib = timezone(timedelta(hours=7))
    now_str = datetime.fromtimestamp(now_stop, wib).strftime("%H:%M")
    start = session_start_times.pop(cid, None)
    durasi_str = format_durasi(now_stop - start) if start else "-"
    sessions.pop(cid, None)
    session_activity.pop(cid, None)
    return {
        "status": "ok",
        "message": (
            f"Sesi obrolan telah ditutup, pukul {now_str} WIB, "
            f"obrolan berlangsung selama {durasi_str}."
        )
    }
@app.get("/history")
def list_all_history():
    try:
        rows = list_sessions()
        wib = timezone(timedelta(hours=7))
        result = []
        for cid, total, first_ts in rows:
            first_time = datetime.fromtimestamp(first_ts, wib).strftime("%Y-%m-%d %H:%M:%S")
            result.append({"chat_id": cid, "total_chat": total, "pertama": first_time})
        return {"total_sessions": len(result), "sessions": result}
    except Exception as e:
        return {"error": str(e)}
@app.get("/history/{chat_id}")
def get_one_history(chat_id: str):
    try:
        rows = get_chat_history(chat_id)
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
@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Alur lengkap pas user chat:
      1. Bersihin session expired
      2. Anti-spam
      3. Cek greeting → langsung LLM (tanpa retrieval)
      4. E5 retrieval: cari data relevan
      5. Cek top score — tolak kalo di luar domain BPS
      6. Multi-part split kalo perlu
      7. LLM: tulis jawaban dari konteks
      8. Simpan history
      9. Return jawaban
    """
    cleanup_sessions()
    cid = req.chat_id
    # ===================== INPUT SANITASI =====================
    req.pertanyaan = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', req.pertanyaan)
    emoji_pattern = re.compile(r'[\U0001F300-\U0010FFFF]')
    emojis = emoji_pattern.findall(req.pertanyaan)
    if len(emojis) > 5:
        for em in set(emojis[5:]):
            req.pertanyaan = req.pertanyaan.replace(em, '')
    if len(req.pertanyaan) > 500:
        return {"jawaban": "⚠️ Pertanyaan terlalu panjang. Maksimal 500 karakter.", "skor": 0}
    if len(req.pertanyaan.strip()) == 0:
        return {"jawaban": "⚠️ Pesan kosong setelah penyaringan.", "skor": 0}
    # ===================== OCR GAMBAR (dari WA bridge / eksternal) =====================
    if req.image_path:
        try:
            import sys
            # Lazy load EasyOCR khusus pas ada gambar (mirip telegram_bot.py)
            if '_ocr_reader' not in globals() or globals()['_ocr_reader'] is None:
                print("[OCR] Loading EasyOCR model (~500MB)...")
                import easyocr
                globals()['_ocr_reader'] = easyocr.Reader(['id', 'en'], gpu=False)
                print("[OCR] Ready!")
            result = globals()['_ocr_reader'].readtext(req.image_path)
            ocr_text = ' '.join([item[1] for item in result if item[2] > 0.3])
            caption = req.pertanyaan if req.pertanyaan != "[Gambar]" else ""
            if caption and ocr_text:
                req.pertanyaan = f"{caption}\n\n[Gambar: {ocr_text}]"
            elif ocr_text:
                req.pertanyaan = f"[Gambar: {ocr_text}]"
            # kalo gak ada ocr_text, pertanyaan tetap caption
            print(f"[OCR] Image processed: {len(ocr_text)} chars extracted")
        except Exception as e:
            print(f"[OCR] Error processing image: {e}")
            # Fallback — proceed with original question
    # ===================== ANTI-SPAM =====================
    init_rate_limit_entry(cid)
    if cid not in TRUSTED_IDS:
        allowed, msg = check_api_rate_limit(cid)
        if not allowed:
            if msg == "__SILENT_BLOCK__":
                return {"jawaban": "", "skor": 0}
            return {"jawaban": msg, "skor": 0}
        api_rate_limit[cid]["last_active"] = time.time()
    # ===================== DAILY CHAT LIMIT =====================
    if cid not in TRUSTED_IDS:
        if not check_daily_limit(cid):
            return {
                "jawaban": f"⚠️ Anda sudah mencapai batas chat harian ({DAILY_LIMIT} chat). Silakan coba lagi besok! 🙏",
                "skor": 0
            }
    # ===================== SESSION =====================
    history, session_baru = init_session(cid)
    # ===================== GREETING DETECTION =====================
    greeting_set = {
        "halo", "hai", "hey", "hi", "pagi", "siang", "sore", "malam",
        "assalamualaikum", "assalamu'alaikum", "hello", "hallo", "helo"
    }
    multi_greetings = [
        "selamat pagi", "selamat siang",
        "selamat sore", "selamat malam"
    ]
    words_lower = req.pertanyaan.lower().strip().split()
    is_greeting = (
        bool(greeting_set & set(words_lower)) or
        any(g in req.pertanyaan.lower().strip() for g in multi_greetings)
    )
    if is_greeting and len(words_lower) <= 3:
        messages = build_greeting_prompt(
            greeting_template, identity, req.pertanyaan
        )
        jawaban = await call_llm(messages, timeout=30)
        if not jawaban:
            jawaban = f"Halo! Saya {identity['name']}, {identity['role']}..."
        api_rate_limit[cid]["last_active"] = time.time()
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=get_bm25_score(req.pertanyaan),
                  bm25_status="GREETING", dijawab=True, greeting=True,
                  jawaban=jawaban)
        return {"jawaban": jawaban, "skor": 1.0}
    # ===================== E5 RETRIEVAL =====================
    context, scores, best_q = search(req.pertanyaan, top_k=5)
    top_score = float(scores[0]) if len(scores) > 0 else 0
    print(f"[QUERY] top_score={top_score:.3f}")
    # ===================== DOMAIN CHECK (BM25) =====================
    # BM25 based on keyword overlap. Out-of-domain questions like "presiden"
    # have ZERO keyword overlap with BPS FAQ → BM25 score ~0.
    bm25_score = get_bm25_score(req.pertanyaan)
    if not check_domain(req.pertanyaan):
        print(f"[QUERY] Luar domain BPS — tolak (BM25={bm25_score:.2f})")
        jawaban = (
            "Maaf, saya tidak dapat menjawab pertanyaan tersebut. "
            "Saya hanya dapat membantu pertanyaan seputar SOBAT, GC PBI, GC PLN, FASIH, dan Pengolahan SE2026. "
            "Silakan hubungi pegawai BPS Provinsi Kepulauan Bangka Belitung untuk informasi lebih lanjut."
        )
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=bm25_score,
                  bm25_status="REJECT", dijawab=False)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": top_score}
    # ===================== MULTI-PART SPLIT =====================
    parts = re.split(r'\s+(?:dan|serta|sedangkan|lalu|terus|trus)\s+|[,;]\s*', req.pertanyaan.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 1:
        relevant_answers = []
        skipped_parts = []
        for part in parts:
            if not check_domain(part):
                print(f"[QUERY] Part '{part[:30]}...' skip (BM25)")
                skipped_parts.append(part)
                continue
            p_ctx, p_scores, p_best_q = search(part, top_k=1)
            for line in p_ctx.split('\n'):
                if line.startswith('JAWABAN:'):
                    relevant_answers.append(line.replace('JAWABAN: ', '').strip())
                    break
        if relevant_answers:
            jawaban = '\n\n'.join(relevant_answers)
            if skipped_parts:
                jawaban += "\n\n---\nℹ️ *Catatan:* Bagian pertanyaan yang tidak dapat saya jawab: " + ', '.join(skipped_parts)
            print(f"[QUERY] Multi-part: {len(relevant_answers)}/{len(parts)} bagian terjawab")
        else:
            jawaban = (
                "Maaf, saya tidak dapat menjawab pertanyaan tersebut. "
                "Saya hanya dapat membantu pertanyaan seputar SOBAT, GC PBI, GC PLN, FASIH, dan Pengolahan SE2026. "
                "Silakan hubungi pegawai BPS Provinsi Kepulauan Bangka Belitung untuk informasi lebih lanjut."
            )
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=bm25_score,
                  bm25_status="ACCEPT", top_score=top_score,
                  top_faq="", dijawab=bool(relevant_answers),
                  multi_part=True, jawaban=jawaban)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\nSesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": top_score}
    # ===================== LLM ANSWER =====================
    # Single question — cek E5 score dulu, tolak kalo terlalu rendah
    if top_score < 0.82:
        print(f"[QUERY] E5 score terlalu rendah ({top_score:.3f}) — tolak")
        jawaban = (
            "Maaf, saya tidak dapat menjawab pertanyaan tersebut. "
            "Saya hanya dapat membantu pertanyaan seputar SOBAT, GC PBI, GC PLN, FASIH, dan Pengolahan SE2026. "
            "Silakan hubungi pegawai BPS Provinsi Kepulauan Bangka Belitung untuk informasi lebih lanjut."
        )
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=bm25_score,
                  bm25_status="ACCEPT", top_score=top_score,
                  top_faq=best_q, dijawab=False, jawaban=jawaban)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": top_score}

    system_prompt = build_system_prompt(system_template, identity)
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "system", "content": f"Data referensi:\n{context}"})
    for msg in history:
        messages.append(msg)
    messages.append({"role": "user", "content": req.pertanyaan})
    jawaban = await call_llm(messages, timeout=30)
    if not jawaban:
        jawaban = "Maaf, terjadi error. Silakan coba lagi."
    # ===================== SAVE =====================
    history.append({"role": "user", "content": req.pertanyaan})
    history.append({"role": "assistant", "content": jawaban})
    log_chat(cid, req.pertanyaan, jawaban)
    # Log query — ambil top FAQ dari scores
    top_faq = best_q if len(scores) > 0 else ""
    log_query(req.pertanyaan, cid, bm25_score=bm25_score,
              bm25_status="ACCEPT", top_score=top_score,
              top_faq=top_faq, dijawab=True, jawaban=jawaban)
    if session_baru:
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib).strftime("%H:%M")
        jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
    return {"jawaban": jawaban, "skor": top_score}
