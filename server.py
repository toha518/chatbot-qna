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
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
load_dotenv()
# ===================== COMPILED REGEX (module level) =====================
EMOJI_RE = re.compile(r'[\U0001F300-\U0010FFFF]')
# ===================== MODULES =====================
from core.database import init_db, get_daily_count, increment_daily_count
from core.embedder import init_data, load_from_gsheet, async_encode_query, search, hybrid_search, questions, check_domain, _DOMAIN_THRESHOLD
from sklearn.metrics.pairwise import cosine_similarity
from core.intent_classifier import init_classifier, classify as ft_classify
from core.bm25 import get_bm25_scores_all, get_bm25_score
from core.query_logger import log_query, get_stats, update_feedback_status
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
    format_durasi, session_has_forward
)
# ===================== INIT =====================
init_db()
GSHEET_CSV_URL = os.getenv("GSHEET_CSV_URL")
if GSHEET_CSV_URL:
    total_qna = init_data(GSHEET_CSV_URL)
else:
    print("[BOOT] ⚠️ GSHEET_CSV_URL tidak di-set!")
    total_qna = 0
# Init scikit-learn classifier (setelah embedder di-load)
init_classifier()
load_llm_config()
identity, system_template, greeting_template, acronyms = load_prompts()
responses = load_responses()
REJECTION_MSG = responses.get("rejection_out_of_context").format(topics_line=", ".join(identity["topics"]))
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
    is_ocr: bool = False   # flag kalo teks berasal dari OCR (Telegram)
    source: str = "api"   # "wa" | "telegram" | "api" — diisi oleh handler masing-masing
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
        await asyncio.sleep(7200)  # 2 jam
        try:
            prev = len(questions)
            total = await asyncio.to_thread(load_from_gsheet, GSHEET_CSV_URL)
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
            "footer": responses.get("session_start").format(time=now_str)
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
    session_has_forward.pop(cid, None)
    return {
        "status": "ok",
        "message": (
            responses.get("session_ended").format(time=now_str, duration=durasi_str)
        )
    }
@app.get("/history")
def list_all_history():
    """Daftar semua chat_id dari query_log.db"""
    try:
        from core.query_logger import SQLITE_FILE
        db = sqlite3.connect(str(SQLITE_FILE))
        rows = db.execute(
            "SELECT chat_id, COUNT(*), MIN(waktu) FROM logs GROUP BY chat_id ORDER BY MIN(waktu) DESC"
        ).fetchall()
        db.close()
        result = []
        for cid, total, first in rows:
            result.append({"chat_id": cid, "total_chat": total, "pertama": first})
        return {"total_sessions": len(result), "sessions": result}
    except Exception as e:
        return {"error": str(e)}

@app.get("/history/{chat_id}")
def get_one_history(chat_id: str):
    """History per user dari query_log.db"""
    try:
        from core.query_logger import SQLITE_FILE
        db = sqlite3.connect(str(SQLITE_FILE))
        rows = db.execute(
            "SELECT waktu, pertanyaan, jawaban FROM logs WHERE chat_id=? ORDER BY waktu ASC LIMIT 200",
            (chat_id,)
        ).fetchall()
        db.close()
        formatted = [{"waktu": w, "user": q, "bot": a} for w, q, a in rows]
        return {"chat_id": chat_id, "total": len(formatted), "messages": formatted}
    except Exception as e:
        return {"error": str(e)}

def _format_end_footer(cid: str) -> str:
    """Format baris penutup session (hanya bagian bawah — jam + durasi)"""
    wib = timezone(timedelta(hours=7))
    now_str = datetime.now(wib).strftime("%H:%M")
    start = session_start_times.get(cid)
    durasi_str = format_durasi(time.time() - start) if start else "-"
    return (
        f"---\n" +
        responses.get("session_ended").format(time=now_str, duration=durasi_str)
    )

# ===================== CONCURRENT REQUEST LIMITER =====================
MAX_CONCURRENT_CHATS = 4
_concurrent_chat_sem = asyncio.Semaphore(MAX_CONCURRENT_CHATS)

async def _concurrent_chat_limit():
    """Dependency: limits concurrent /chat requests. Released otomatis setelah response."""
    async with _concurrent_chat_sem:
        yield


@app.post("/chat")
async def chat(req: ChatRequest, _conc: None = Depends(_concurrent_chat_limit)):
    """
    Alur lengkap pas user chat:
      1. Batas concurrent request via Semaphore(Depends)
      2. Bersihin session expired
      3. Anti-spam
      4. Cek greeting → langsung LLM (tanpa retrieval)
      5. E5 retrieval: cari data relevan
      6. Cek top score — tolak kalo di luar domain BPS
      7. Multi-part split kalo perlu
      8. LLM: tulis jawaban dari konteks
      9. Simpan history
      10. Return jawaban
    """
    cleanup_sessions()
    cid = req.chat_id
    # ===================== INPUT SANITASI =====================
    # Simpan query asli untuk logging (sebelum normalisasi apapun)
    _display_query = str(req.pertanyaan)
    req.pertanyaan = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', req.pertanyaan)
    # Simpan query dengan koma untuk multi-part detection
    _raw_query = req.pertanyaan
    # Normalisasi untuk consistency: koma → spasi (biar E5 embedding stabil)
    req.pertanyaan = req.pertanyaan.replace(',', ' ').replace(';', ' ')
    req.pertanyaan = re.sub(r'\s+', ' ', req.pertanyaan).strip()
    emojis = EMOJI_RE.findall(req.pertanyaan)
    if len(emojis) > 5:
        for em in set(emojis[5:]):
            req.pertanyaan = req.pertanyaan.replace(em, '')
    if len(req.pertanyaan.strip()) == 0:
        return {"jawaban": responses.get("question_empty"), "skor": 0}
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
    # Character limit — skip kalo dari OCR
    if not req.is_ocr and not req.image_path:
        if len(req.pertanyaan) > 500:
            return {"jawaban": responses.get("question_too_long").format(max_length=500), "skor": 0}
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
                    "jawaban": responses.get("daily_limit_reached").format(limit=DAILY_LIMIT),
                    "skor": 0
                }
            return {"jawaban": "", "skor": 0}
    # ===================== SESSION =====================
    history, session_baru = init_session(cid)

    # Synthetic feedback button callbacks (dari Telegram inline keyboard / WA Poll)
    if req.pertanyaan == "feedback_yes":
        if session_has_forward.get(cid, False):
            update_feedback_status(cid, "positive")
            jawaban = responses.get("positive_feedback")
            jawaban += "\n\n" + _format_end_footer(cid)
            sessions.pop(cid, None)
            session_activity.pop(cid, None)
            session_has_forward.pop(cid, None)
            return {"jawaban": jawaban, "skor": 1.0}
        else:
            jawaban = responses.get("error_llm")
            return {"jawaban": jawaban, "skor": 1.0}

    if req.pertanyaan == "feedback_no":
        if session_has_forward.get(cid, False):
            update_feedback_status(cid, "negative")
            jawaban = responses.get("negative_feedback")
            return {"jawaban": jawaban, "skor": 1.0}
        else:
            # Treat sebagai forward
            pass

    # ===================== DOMAIN FILTER: FASTTEXT → HYBRID =====================
    ft_domain, ft_conf = ft_classify(req.pertanyaan)
    centroid_sim = 0.0  # di-update pas domain check
    from core.intent_classifier import _ready, _using_fallback
    _clf_mode = "keyword_fallback" if _using_fallback else ("none" if not _ready else "scikit-learn")
    print(f"[DOMAIN] '{_display_query[:60]}' → {ft_domain} ({ft_conf:.3f})")

    # Greeting — respon langsung, skip retrieval
    if ft_domain == "greeting":
        # Cek BM25: kalo ada keyword BPS di balik sapaan → treat sebagai forward
        _greeting_bm25 = get_bm25_score(req.pertanyaan)
        if _greeting_bm25 >= 3.0:
            print(f"[DOMAIN] greeting ({_greeting_bm25:.1f}) tapi ada isi BPS → forward")
            ft_domain = "forward"
            ft_conf = 1.0
            session_has_forward[cid] = True
            # Skip ke BM25 gate
        else:
            messages = build_greeting_prompt(greeting_template, identity, req.pertanyaan, acronyms)
            jawaban, llm_model, llm_provider, llm_time = await call_llm(messages, timeout=30)
            if not jawaban:
                jawaban = responses.get("error_llm")
            api_rate_limit[cid]["last_active"] = time.time()
            if session_baru:
                wib = timezone(timedelta(hours=7))
                now = datetime.now(wib).strftime("%H:%M")
                jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
            log_query(_display_query, cid, source=req.source,
                      centroid_sim=centroid_sim,
                      clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                      gate="CLF_GREETING", dijawab=True, jawaban=jawaban,
                      session_baru=session_baru, llm_model=llm_model, llm_provider=llm_provider, llm_time_ms=llm_time)
            return {"jawaban": jawaban, "skor": 1.0}

    # Capability — respon langsung, skip retrieval
    if ft_domain == "capability":
        # Cek BM25: kalo ada keyword BPS di balik pertanyaan → treat sebagai forward
        _cap_bm25 = get_bm25_score(req.pertanyaan)
        if _cap_bm25 >= 3.0:
            print(f"[DOMAIN] capability ({_cap_bm25:.1f}) tapi ada isi BPS → forward")
            ft_domain = "forward"
            ft_conf = 1.0
            session_has_forward[cid] = True
            # Skip ke BM25 gate
        else:
            # Template statis — gak panggil LLM (cegah ngarang definisi)
            topics_list = "\n".join(f"  {t}" for t in identity['topics'])
            jawaban = responses.get("capability").format(
                name=identity['name'],
                role=identity['role'],
                topics_list=topics_list
            )
            api_rate_limit[cid]["last_active"] = time.time()
            if session_baru:
                wib = timezone(timedelta(hours=7))
                now = datetime.now(wib).strftime("%H:%M")
                jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
            log_query(_display_query, cid, source=req.source,
                      centroid_sim=centroid_sim,
                      clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                      gate="CLF_CAPABILITY", dijawab=True, jawaban=jawaban,
                      session_baru=session_baru)
            return {"jawaban": jawaban, "skor": 1.0}

    # Acknowledgment — respon langsung (makasih, ok, sip, dll)
    if ft_domain == "positive_feedback":
        if session_has_forward.get(cid, False):
            # Ada interaksi sebelumnya → balas feedback + stop session
            update_feedback_status(cid, "positive")
            jawaban = responses.get("positive_feedback")
            jawaban += "\n\n" + _format_end_footer(cid)
            # Stop session internal
            sessions.pop(cid, None)
            session_activity.pop(cid, None)
            session_has_forward.pop(cid, None)
            api_rate_limit[cid]["last_active"] = time.time()
            log_query(_display_query, cid, source=req.source,
                      centroid_sim=centroid_sim,
                      clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                      gate="CLF_POSITIVE_FEEDBACK", dijawab=True, jawaban=jawaban)
            return {"jawaban": jawaban, "skor": 1.0}
        else:
            # Tanpa konteks → treat sebagai greeting
            print(f"[DOMAIN] positive_feedback tanpa konteks → greeting")
            messages = build_greeting_prompt(greeting_template, identity, req.pertanyaan, acronyms)
            jawaban, llm_model, llm_provider, llm_time = await call_llm(messages, timeout=30)
            if not jawaban:
                jawaban = responses.get("error_llm")
            if session_baru:
                wib = timezone(timedelta(hours=7))
                now = datetime.now(wib).strftime("%H:%M")
                jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
            log_query(_display_query, cid, source=req.source,
                      centroid_sim=centroid_sim,
                      clf_domain="greeting", clf_confidence=0.0, clf_mode=_clf_mode,
                      gate="CLF_GREETING", dijawab=True, jawaban=jawaban,
                      session_baru=session_baru, llm_model=llm_model, llm_provider=llm_provider, llm_time_ms=llm_time)
            return {"jawaban": jawaban, "skor": 1.0}

    # Negative feedback — respon langsung (kamu tidak membantu, dll)
    if ft_domain == "negative_feedback":
        if session_has_forward.get(cid, False):
            # Ada interaksi sebelumnya → balas feedback
            update_feedback_status(cid, "negative")
            jawaban = responses.get("negative_feedback")
            api_rate_limit[cid]["last_active"] = time.time()
            log_query(_display_query, cid, source=req.source,
                      centroid_sim=centroid_sim,
                      clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                      gate="CLF_NEGATIVE_FEEDBACK", dijawab=True, jawaban=jawaban)
            return {"jawaban": jawaban, "skor": 1.0}
        else:
            # Tanpa konteks → treat sebagai forward (biar kena domain check normal)
            print(f"[DOMAIN] negative_feedback tanpa konteks → forward")

    # Tandai session — CLF return forward, ada interaksi
    if ft_domain == "forward":
        session_has_forward[cid] = True

    # ── DOMAIN FILTER: BM25 threshold check (3-tier) ──
    query_vec = await async_encode_query(req.pertanyaan)
    centroid_sim = check_domain(query_vec)  # logged for analytics
    bm25_top = get_bm25_score(req.pertanyaan)
    print(f"[DOMAIN] BM25={bm25_top:.1f} (gate: ≥5=lolos, 3-4.9=QNA, <3=tolak, centroid={centroid_sim:.4f})")
    api_rate_limit[cid]["last_active"] = time.time()

    # ── CASCADE: concat prev query kalo BM25 < 5 ──
    prev_queries = [msg["content"] for msg in reversed(history) if msg["role"] == "user"]
    cascade_used = False
    _cascade_query = None
    if bm25_top < 5.0 and prev_queries:
        for depth in range(1, min(4, len(prev_queries) + 1)):
            context_parts = list(reversed(prev_queries[:depth])) + [req.pertanyaan]
            enhanced_query = " — ".join(context_parts)
            bm25_cascade = get_bm25_score(enhanced_query)
            print(f"[QUERY] Cascade depth={depth}: BM25 {bm25_top:.1f} → {bm25_cascade:.1f}")
            if bm25_cascade >= 5.0:
                # E5 similarity guard: pattern sama kayak multi-part split
                _prev_vec = await async_encode_query(prev_queries[0])
                _curr_vec = query_vec
                if _prev_vec.ndim == 1: _prev_vec = _prev_vec.reshape(1, -1)
                if _curr_vec.ndim == 1: _curr_vec = _curr_vec.reshape(1, -1)
                _e5_sim = float(cosine_similarity(_prev_vec, _curr_vec).flatten()[0])
                _e5_threshold = 0.78  # sama kayak multi-part merge
                if _e5_sim >= _e5_threshold:
                    bm25_top = bm25_cascade
                    _cascade_query = enhanced_query
                    _display_query += f" [cascade depth={depth}]"
                    cascade_used = True
                    print(f"[QUERY] Cascade depth={depth} berhasil! BM25={bm25_cascade:.1f}, E5 sim={_e5_sim:.2f}")
                    break
                else:
                    print(f"[QUERY] Cascade depth={depth} E5 sim terlalu rendah ({_e5_sim:.2f}) — topic drift, skip cascade")
        if not cascade_used:
            print(f"[QUERY] Cascade gagal di semua depth — BM25 max {bm25_cascade if 'bm25_cascade' in dir() else bm25_top:.1f}")

    if not cascade_used and bm25_top < 3.0:
        # Tier 1: out-of-domain — tolak total
        jawaban = responses.get("rejection_out_of_context", REJECTION_MSG).format(topics_line=", ".join(identity["topics"]))
        log_query(_display_query, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="OOC_BM25", dijawab=False, jawaban=jawaban,
                  bm25_gate=bm25_top)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
        return {"jawaban": jawaban, "skor": 0}

    if 3.0 <= bm25_top < 5.0:
        # Tier 2: borderline — domain BPS possible tapi gak match FAQ → QNA link
        jawaban = responses.get("rejection_no_answer", REJECTION_MSG)
        log_query(_display_query, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="BM25_BORDERLINE", dijawab=False, jawaban=jawaban,
                  bm25_gate=bm25_top)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
        return {"jawaban": jawaban, "skor": 0}

    # Tier 3: BM25 ≥ 5.0 — keyword BPS jelas → hybrid search → LLM
    # ── HYBRID SEARCH (pake _cascade_query kalo ada, original req.pertanyaan kalo tidak) ──
    _search_query = _cascade_query if _cascade_query is not None else req.pertanyaan
    context, scores, best_q, top5_all = await asyncio.to_thread(
        hybrid_search, _search_query, 5,
        query_vec if _cascade_query is None else None
    )
    top_rrf = float(scores[2]) if len(scores) > 2 else 0
    print(f"[QUERY] RRF={top_rrf:.4f} (hybrid E5+BM25 — ranking only)")

    # ── MULTI-PART SPLIT (E5 Semantic Boundary) ──
    _SPLIT_PATTERN = re.compile(
        r'\s+(?:dan|serta|sedangkan|namun|tetapi|tapi)\s+'
        r'|(?<=\?)\s+(?=[A-Za-z])'
        r'|\.\s+'
        r'|,\s*'
    )
    parts = _SPLIT_PATTERN.split(_raw_query.strip())
    parts = [re.sub(r'\s+', ' ', p.replace(',', ' ').replace(';', ' ')).strip().rstrip('?.').strip() for p in parts if p.strip()]

    if len(parts) > 1:
        _SEMANTIC_MERGE_THRESHOLD = 0.78
        merged_parts = [parts[0]]
        for i in range(1, len(parts)):
            prev_vec = await async_encode_query(merged_parts[-1])
            curr_vec = await async_encode_query(parts[i])
            if prev_vec.ndim == 1: prev_vec = prev_vec.reshape(1, -1)
            if curr_vec.ndim == 1: curr_vec = curr_vec.reshape(1, -1)
            sim = float(cosine_similarity(prev_vec, curr_vec).flatten()[0])
            if sim >= _SEMANTIC_MERGE_THRESHOLD:
                merged_parts[-1] = merged_parts[-1] + " " + parts[i]
                print(f"[MERGE] Part {i-1}+{i}: sim={sim:.3f} -> '{merged_parts[-1][:60]}'")
            else:
                merged_parts.append(parts[i])
                print(f"[SPLIT] Part {i-1} vs {i}: sim={sim:.3f} -> separate intents")
        parts = merged_parts

    if len(parts) > 1:
        relevant_answers = []
        ooc_parts = []  # BM25 < 3.0 → out of context
        borderline_parts = []  # BM25 3.0-4.9 → no answer in DB
        for part in parts:
            p_bm25 = get_bm25_score(part)
            if p_bm25 < 5.0:
                if p_bm25 < 3.0:
                    ooc_parts.append(part)
                else:
                    borderline_parts.append(part)
                print(f"[SPLIT] Skip part (BM25={p_bm25:.1f}): '{part[:60]}'")
                continue
            p_ctx, p_scores, _, p_top5 = await asyncio.to_thread(hybrid_search, part, 5)
            _system = build_system_prompt(system_template, identity, acronyms)
            _msgs = [{"role": "system", "content": _system}]
            _msgs.append({"role": "system", "content": f"📚 Data Referensi (diurutkan dari paling relevan):\n\n{p_ctx}"})
            _msgs.append({"role": "user", "content": part})
            _jawaban, _llm_model, _llm_provider, _llm_time = await call_llm(_msgs, timeout=30)
            if not _jawaban:
                _jawaban = p_ctx
                _llm_model = _llm_provider = ""; _llm_time = 0
            relevant_answers.append(_jawaban)

        # All parts skipped — pilih rejection sesuai jenis part
        if not relevant_answers:
            if borderline_parts and not ooc_parts:
                # Semua borderline (3.0-4.9) → no answer
                jawaban = responses.get("rejection_no_answer", REJECTION_MSG)
                gate_label = "NOANSWER_MULTI_PART"
                print(f"[SPLIT] Semua bagian borderline ({len(borderline_parts)}) — rejection_no_answer")
            else:
                # Ada OOC (< 3.0) — out of context
                jawaban = responses.get("rejection_out_of_context").format(topics_line=", ".join(identity["topics"]))
                gate_label = "OOC_MULTI_PART"
                print(f"[SPLIT] Ada OOC ({len(ooc_parts)} part) — rejection_out_of_context")
            _dijawab = False
        else:
            jawaban = '\n\n---\n\n'.join(relevant_answers)
            skipped_parts = ooc_parts + borderline_parts
            if skipped_parts:
                jawaban += '\n\n' + responses.get("multi_part_note").format(skipped_parts="; ".join(skipped_parts))
                # Ada borderline → no answer (user bisa ajukan via form)
                # Murni OOC → out of context
                if borderline_parts:
                    jawaban += '\n\n' + responses.get("rejection_no_answer")
                else:
                    jawaban += '\n\n' + responses.get("rejection_out_of_context").format(topics_line=", ".join(identity["topics"]))
            gate_label = "MULTI_PART"
            _dijawab = True
            _feedback_eligible = True
        total_skipped = len(ooc_parts) + len(borderline_parts)
        print(f"[QUERY] Multi-part: {len(relevant_answers)}/{len(parts)} bagian dijawab, {total_skipped} di-skip")
    else:
        # Single question — langsung LLM dengan context
        system_prompt = build_system_prompt(system_template, identity, acronyms)
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "system", "content": f"📚 Data Referensi (diurutkan dari paling relevan):\n\n{context}"})
        for msg in history:
            messages.append(msg)
        messages.append({"role": "user", "content": req.pertanyaan})
        jawaban, llm_model, llm_provider, llm_time = await call_llm(messages, timeout=30)
        if not jawaban:
            llm_model = llm_provider = ""; llm_time = 0
            jawaban = responses.get("error_llm")
            _feedback_eligible = False
        else:
            _feedback_eligible = True
        gate_label = "ANSWER"
        _dijawab = True

    # Feedback footer — cuma untuk jawaban LLM beneran (forward pipeline)
    if _dijawab and _feedback_eligible:
        jawaban += responses.get("feedback_footer")
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
    log_query(_display_query, cid, source=req.source,
              centroid_sim=centroid_sim,
              clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
              rrf_score=top_rrf, e5_top=float(scores[0]) if len(scores) > 0 else 0,
              bm25_raw=float(scores[1]) if len(scores) > 1 else 0,
              top5_faq=top5_all,
              gate=gate_label, dijawab=_dijawab, jawaban=jawaban,
              bm25_gate=bm25_top,
              multi_part=bool(len(parts) > 1), session_baru=session_baru,
              llm_model=llm_model if 'llm_model' in dir() else "",
              llm_provider=llm_provider if 'llm_provider' in dir() else "",
              llm_time_ms=llm_time if 'llm_time' in dir() else 0)
    if session_baru and _dijawab:
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib).strftime("%H:%M")
        jawaban += "\n\n---\n" + responses.get("session_new").format(time=now)
    return {"jawaban": jawaban, "skor": 1.0 if _dijawab else 0}
