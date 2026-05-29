# server.py — API Server Nara (Router Layer)
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
from core.database import init_db, log_chat, get_chat_history, list_sessions, get_daily_count, increment_daily_count
from core.embedder import init_data, load_from_gsheet, encode_query, search, hybrid_search, questions
import core.embedder as _embedder_module
from core.domain_filter import init_templates, classify
from core.bm25 import get_bm25_scores_all
from core.query_logger import log_query, get_stats
from core.llm import (
    load_llm_config, load_prompts, load_responses,
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
# Init E5 domain filter templates (setelah embedder di-load)
if _embedder_module.embedder is not None:
    init_templates(_embedder_module.embedder)
load_llm_config()
identity, system_template, greeting_template, acronyms = load_prompts()
responses = load_responses()
REJECTION_MSG = responses.get("rejection", "").format(topics_line=", ".join(identity["topics"]))
print(f"[BOOT] Identity: {identity['name']} — {identity['role']}")
# Init trusted IDs dari .env
init_trusted_ids(os.getenv("TRUSTED_CHAT_IDS", ""))
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# ===================== DAILY CHAT LIMIT =====================
DAILY_LIMIT = 25  # maks chat per user per hari
daily_limit_notified: dict[str, str] = {}  # {clean_cid: tanggal_notif}

def check_daily_limit(cid: str) -> bool:
    """
    Cek & increment daily chat count di SQLite (persistent).
    Return False kalo udah > limit.
    """
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    # Normalisasi: WA pake @lid/@c.us → ambil angka aja
    clean_cid = cid.split('@')[0] if cid and '@' in cid else cid
    count = get_daily_count(clean_cid, today)
    if count >= DAILY_LIMIT:
        return False
    increment_daily_count(clean_cid, today)
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
        "engine": "hybrid (E5+BM25)",
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
        return {"jawaban": responses.get("question_too_long", "⚠️ Pertanyaan terlalu panjang. Maksimal {max_length} karakter.").format(max_length=500), "skor": 0}
    if len(req.pertanyaan.strip()) == 0:
        return {"jawaban": responses.get("question_empty", "⚠️ Pesan kosong setelah penyaringan."), "skor": 0}
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
            # Notif sekali, lalu silent
            today = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
            clean_cid = cid.split('@')[0] if cid and '@' in cid else cid
            last_notified = daily_limit_notified.get(clean_cid)
            if last_notified != today:
                daily_limit_notified[clean_cid] = today
                return {
                    "jawaban": responses.get("daily_limit_reached", "").format(limit=DAILY_LIMIT),
                    "skor": 0
                }
            return {"jawaban": "", "skor": 0}
    # ===================== SESSION =====================
    history, session_baru = init_session(cid)
    # ===================== E5 DOMAIN FILTER =====================
    # Encode query SEKALI, reuse buat domain filter + hybrid retrieval
    query_vec = encode_query(req.pertanyaan)
    domain, domain_conf = classify(query_vec, query_text=req.pertanyaan)
    print(f"[DOMAIN] '{req.pertanyaan[:50]}' → {domain} (conf={domain_conf:.3f})")

    # Greeting — jawab langsung dengan template
    if domain == "greeting":
        messages = build_greeting_prompt(
            greeting_template, identity, req.pertanyaan, acronyms
        )
        jawaban = await call_llm(messages, timeout=30)
        if not jawaban:
            topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(identity['topics']))
            jawaban = responses.get("greeting", "").format(name=identity['name'], role=identity['role'], topics_list=topics_list)
        api_rate_limit[cid]["last_active"] = time.time()
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=domain_conf,
                  bm25_status="GREETING", dijawab=True, greeting=True,
                  jawaban=jawaban)
        return {"jawaban": jawaban, "skor": 1.0}

    # Capability — sama, langsung LLM pake greeting prompt
    if domain == "capability":
        messages = build_greeting_prompt(
            greeting_template, identity, req.pertanyaan, acronyms
        )
        jawaban = await call_llm(messages, timeout=30)
        if not jawaban:
            topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(identity['topics']))
            jawaban = responses.get("greeting", "").format(name=identity['name'], role=identity['role'], topics_list=topics_list)
        api_rate_limit[cid]["last_active"] = time.time()
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=domain_conf,
                  bm25_status="CAPABILITY", dijawab=True, greeting=True,
                  jawaban=jawaban)
        return {"jawaban": jawaban, "skor": 1.0}

    # Out-of-context — tolak langsung, skip retrieval
    if domain == "out_of_context":
        print(f"[QUERY] Luar domain BPS — tolak (conf={domain_conf:.3f})")
        jawaban = REJECTION_MSG
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_chat(cid, req.pertanyaan, jawaban)
        log_query(req.pertanyaan, cid, bm25_score=domain_conf,
                  bm25_status="REJECT", dijawab=False)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": 0.0}

    # ===================== FAQ → HYBRID RETRIEVAL (reuse embedding) =====================
    context, scores, best_q = hybrid_search(req.pertanyaan, top_k=5, query_vec=query_vec)
    top_score = float(scores[0]) if len(scores) > 0 else 0
    print(f"[QUERY] top_score={top_score:.3f} (hybrid E5+BM25, domain={domain})")
    bm25_score = domain_conf
    # ===================== MULTI-PART SPLIT =====================
    parts = re.split(r'\s+(?:dan|serta|sedangkan|lalu|terus|trus)\s+|[,;]\s*', req.pertanyaan.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 1:
        relevant_answers = []
        skipped_parts = []
        for part in parts:
            part_vec = encode_query(part)
            part_domain, part_conf = classify(part_vec, query_text=part)
            if part_domain != "faq":
                print(f"[QUERY] Part '{part[:30]}...' skip (domain={part_domain}, conf={part_conf:.3f})")
                skipped_parts.append(part)
                continue
            p_ctx, p_scores, p_best_q = hybrid_search(part, top_k=1, query_vec=part_vec)
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
            jawaban = REJECTION_MSG
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
    # Single question — cek E5 top score dulu
    if top_score < 0.82:
        # ── Cascade Fallback ──
        # Kalo hybrid score rendah, coba concat 1-2 query user sebelumnya
        # Biar follow-up pendek kayak "di dtsen juga udah sesuai" tetap ke-dapet konteks
        prev_queries = [msg["content"] for msg in reversed(history) if msg["role"] == "user"]
        fallback_success = False

        for depth in range(1, min(3, len(prev_queries) + 1)):
            # depth=1: concat 1 query sebelumnya
            # depth=2: concat 2 query sebelumnya
            context_parts = list(reversed(prev_queries[:depth])) + [req.pertanyaan]
            enhanced_query = " — ".join(context_parts)

            print(f"[QUERY] Cascade depth={depth}: '{enhanced_query[:120]}'")
            ctx2, scores2, bq2 = hybrid_search(enhanced_query, top_k=5)
            ts2 = float(scores2[0]) if len(scores2) > 0 else 0

            if ts2 >= 0.82:
                print(f"[QUERY] Cascade depth={depth} berhasil: {top_score:.3f} → {ts2:.3f}")
                top_score = ts2
                context = ctx2
                best_q = bq2
                fallback_success = True
                break

        if not fallback_success:
            # Semua cascade gagal — reject
            if prev_queries:
                print(f"[QUERY] Cascade tetap rendah — tolak")
            else:
                print(f"[QUERY] Hybrid score terlalu rendah ({top_score:.3f}) — tolak")
            jawaban = REJECTION_MSG
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

    system_prompt = build_system_prompt(system_template, identity, acronyms)
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "system", "content": responses.get("context_header", "Data referensi:\n{context}").format(context=context)})
    for msg in history:
        messages.append(msg)
    messages.append({"role": "user", "content": req.pertanyaan})
    jawaban = await call_llm(messages, timeout=30)
    if not jawaban:
        jawaban = responses.get("error_llm", "Maaf, terjadi error. Silakan coba lagi.")
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
