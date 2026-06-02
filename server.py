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
# ===================== COMPILED REGEX (module level) =====================
EMOJI_RE = re.compile(r'[\U0001F300-\U0010FFFF]')
# ===================== MODULES =====================
from core.database import init_db, get_daily_count, increment_daily_count
from core.embedder import init_data, load_from_gsheet, encode_query, search, hybrid_search, questions, check_domain, _DOMAIN_THRESHOLD
from core.intent_classifier import init_classifier, classify as ft_classify
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
# Init scikit-learn classifier (setelah embedder di-load)
init_classifier()
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
        await asyncio.sleep(600)
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
    # Simpan query asli untuk multi-part detection (sebelum normalisasi koma)
    _raw_query = req.pertanyaan
    # Normalisasi untuk consistency: koma → spasi (biar E5 embedding stabil)
    req.pertanyaan = req.pertanyaan.replace(',', ' ').replace(';', ' ')
    req.pertanyaan = re.sub(r'\s+', ' ', req.pertanyaan).strip()
    emojis = EMOJI_RE.findall(req.pertanyaan)
    if len(emojis) > 5:
        for em in set(emojis[5:]):
            req.pertanyaan = req.pertanyaan.replace(em, '')
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
    # Character limit — skip kalo dari OCR
    if not req.is_ocr and not req.image_path:
        if len(req.pertanyaan) > 500:
            return {"jawaban": responses.get("question_too_long", "⚠️ Pertanyaan terlalu panjang. Maksimal {max_length} karakter.").format(max_length=500), "skor": 0}
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
    # ===================== DOMAIN FILTER: FASTTEXT → HYBRID =====================
    ft_domain, ft_conf = ft_classify(req.pertanyaan)
    centroid_sim = 0.0  # di-update pas domain check
    from core.intent_classifier import _ready, _using_fallback
    _clf_mode = "keyword_fallback" if _using_fallback else ("none" if not _ready else "scikit-learn")
    print(f"[DOMAIN] '{req.pertanyaan[:60]}' → {ft_domain} ({ft_conf:.3f})")

    # Greeting — respon langsung, skip retrieval
    if ft_domain == "greeting":
        messages = build_greeting_prompt(greeting_template, identity, req.pertanyaan, acronyms)
        jawaban, llm_model, llm_provider, llm_time = await call_llm(messages, timeout=30)
        if not jawaban:
            topics_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(identity['topics']))
            jawaban = responses.get("greeting", "").format(name=identity['name'], role=identity['role'], topics_list=topics_list)
        api_rate_limit[cid]["last_active"] = time.time()
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="CLF_GREETING", dijawab=True, jawaban=jawaban,
                  session_baru=session_baru, llm_model=llm_model, llm_provider=llm_provider, llm_time_ms=llm_time)
        return {"jawaban": jawaban, "skor": 1.0}

    # Capability — respon langsung, skip retrieval
    if ft_domain == "capability":
        # Template statis — gak panggil LLM (cegah ngarang definisi)
        topics_list = "\n".join(f"  {t}" for t in identity['topics'])
        jawaban = responses.get("capability", "").format(
            name=identity['name'],
            role=identity['role'],
            topics_list=topics_list
        )
        api_rate_limit[cid]["last_active"] = time.time()
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="CLF_CAPABILITY", dijawab=True, jawaban=jawaban,
                  session_baru=session_baru)
        return {"jawaban": jawaban, "skor": 1.0}

    # Acknowledgment — respon langsung (makasih, ok, sip, dll)
    if ft_domain == "positive_feedback":
        jawaban = responses.get("positive_feedback", "Sama-sama! 😊")
        api_rate_limit[cid]["last_active"] = time.time()
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="CLF_POSITIVE_FEEDBACK", dijawab=True, jawaban=jawaban)
        return {"jawaban": jawaban, "skor": 1.0}

    # Negative feedback — respon langsung (kamu tidak membantu, dll)
    if ft_domain == "negative_feedback":
        jawaban = responses.get("negative_feedback", "Maaf ya... 🙏")
        api_rate_limit[cid]["last_active"] = time.time()
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="CLF_NEGATIVE_FEEDBACK", dijawab=True, jawaban=jawaban)
        return {"jawaban": jawaban, "skor": 1.0}

    # ── DOMAIN FILTER: BM25 threshold check ──
    query_vec = encode_query(req.pertanyaan)
    centroid_sim = check_domain(query_vec)  # logged for analytics
    from core.bm25 import get_bm25_score
    bm25_top = get_bm25_score(req.pertanyaan)
    _BM25_THRESHOLD = 3.0  # BM25 < 3.0 = gak ada keyword BPS signifikan
    print(f"[DOMAIN] BM25={bm25_top:.1f} (threshold={_BM25_THRESHOLD}, centroid={centroid_sim:.4f})")
    if bm25_top < _BM25_THRESHOLD:
        jawaban = REJECTION_MSG
        api_rate_limit[cid]["last_active"] = time.time()
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  gate="OOC_BM25", dijawab=False, jawaban=jawaban,
                  bm25_gate=bm25_top)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": 0}

    # ── HYBRID SEARCH (gak ada domain filter terpisah — BM25=0 udah ditolak di atas) ──
    context, scores, best_q, top5_all = hybrid_search(req.pertanyaan, top_k=5)
    top_rrf = float(scores[2]) if len(scores) > 2 else 0
    print(f"[QUERY] RRF={top_rrf:.4f} (hybrid E5+BM25)")

    # Gate 0: out-of-context (BM25=0 → RRF ≤ 0.0164, ga mungkin ≥ 0.018)
    _OOC_THRESHOLD = 0.018   # < 0.018 = out of context total
    _ANSWER_THRESHOLD = 0.025  # ≥ 0.025 = ada FAQ match yang jelas

    # ── MULTI-PART SPLIT (Enhanced: E5 Semantic Boundary) ──
    _SPLIT_PATTERN = re.compile(
        r'\s+(?:dan|serta|sedangkan|namun|tetapi|tapi)\s+'
        r'|(?<=\?)\s+(?=[A-Za-z])'
        r'|\.\s+'
        r'|,\s*'
    )
    parts = _SPLIT_PATTERN.split(_raw_query.strip())
    # Normalize tiap part (hapus koma, collapse spaces) biar E5 konsisten
    parts = [re.sub(r'\s+', ' ', p.replace(',', ' ').replace(';', ' ')).strip().rstrip('?.').strip() for p in parts if p.strip()]

    if len(parts) > 1:
        from sklearn.metrics.pairwise import cosine_similarity
        _SEMANTIC_MERGE_THRESHOLD = 0.78
        merged_parts = [parts[0]]
        for i in range(1, len(parts)):
            prev_vec = encode_query(merged_parts[-1])
            curr_vec = encode_query(parts[i])
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
        skipped_parts = []
        for part in parts:
            p_ctx, p_scores, p_best_q, _ = hybrid_search(part, top_k=1)
            p_rrf = float(p_scores[2]) if len(p_scores) > 2 else 0
            if p_rrf < _ANSWER_THRESHOLD:
                print(f"[QUERY] Part '{part[:30]}...' skip (RRF={p_rrf:.4f})")
                skipped_parts.append(part)
                continue
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
            if top_rrf < _OOC_THRESHOLD:
                jawaban = responses.get("rejection_out_of_context", REJECTION_MSG).format(topics_line=", ".join(identity["topics"]))
            else:
                jawaban = responses.get("rejection_no_answer", REJECTION_MSG)
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  rrf_score=top_rrf, top5_faq=top5_all,
                  gate="MULTI_PART" if relevant_answers else "MULTI_PART_QNA",
                  bm25_gate=bm25_top,
                  dijawab=bool(relevant_answers), jawaban=jawaban,
                  multi_part=True, session_baru=session_baru)
        if session_baru:
            wib = timezone(timedelta(hours=7))
            now = datetime.now(wib).strftime("%H:%M")
            jawaban += f"\n\n---\nSesi obrolan baru telah dibuka — pukul {now} WIB"
        return {"jawaban": jawaban, "skor": top_rrf}

    # ── SINGLE QUESTION: gate out-of-context / cascade / answer ──
    # Gate 1: out-of-context total → tolak
    if top_rrf < _OOC_THRESHOLD:
        print(f"[QUERY] Out of context (RRF={top_rrf:.4f})")
        jawaban = responses.get("rejection_out_of_context", REJECTION_MSG).format(topics_line=", ".join(identity["topics"]))
        history.append({"role": "user", "content": req.pertanyaan})
        history.append({"role": "assistant", "content": jawaban})
        log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                  clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                  rrf_score=top_rrf,
                  gate="OUT_OF_CONTEXT", dijawab=False, jawaban=jawaban,
                  bm25_gate=bm25_top,
                  session_baru=session_baru)
        return {"jawaban": jawaban, "skor": top_rrf}

    # Gate 2: RRF rendah tapi ada sinyal → cascade dulu, kalo gagal → QNA
    if top_rrf < _ANSWER_THRESHOLD:
        prev_queries = [msg["content"] for msg in reversed(history) if msg["role"] == "user"]
        cascade_ok = False
        for depth in range(1, min(3, len(prev_queries) + 1)):
            context_parts = list(reversed(prev_queries[:depth])) + [req.pertanyaan]
            enhanced_query = " — ".join(context_parts)
            print(f"[QUERY] Cascade depth={depth}: '{enhanced_query[:120]}'")
            ctx2, scores2, bq2 = hybrid_search(enhanced_query, top_k=5)
            ts2 = float(scores2[2]) if len(scores2) > 2 else 0
            if ts2 >= _ANSWER_THRESHOLD:
                print(f"[QUERY] Cascade depth={depth} berhasil: RRF {top_rrf:.4f} → {ts2:.4f}")
                top_rrf = ts2
                context = ctx2
                best_q = bq2
                cascade_ok = True
                break
        if not cascade_ok:
            print(f"[QUERY] Cascade gagal → QNA link (RRF={top_rrf:.4f})")
            jawaban = responses.get("rejection_no_answer", REJECTION_MSG)
            history.append({"role": "user", "content": req.pertanyaan})
            history.append({"role": "assistant", "content": jawaban})
            log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
                      clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
                      rrf_score=top_rrf,
                      gate="CASCADE_QNA", dijawab=False, jawaban=jawaban,
                      bm25_gate=bm25_top,
                      session_baru=session_baru)
            if session_baru:
                wib = timezone(timedelta(hours=7))
                now = datetime.now(wib).strftime("%H:%M")
                jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
            return {"jawaban": jawaban, "skor": top_rrf}

    # Gate 3: RRF ≥ ANSWER threshold → jawab pake LLM
    system_prompt = build_system_prompt(system_template, identity, acronyms)
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "system", "content": responses.get("context_header", "Data referensi:\n{context}").format(context=context)})
    for msg in history:
        messages.append(msg)
    messages.append({"role": "user", "content": req.pertanyaan})
    jawaban, llm_model, llm_provider, llm_time = await call_llm(messages, timeout=30)
    if not jawaban:
        llm_model = llm_provider = ""; llm_time = 0
        jawaban = responses.get("error_llm", "Maaf, terjadi error. Silakan coba lagi.")
    history.append({"role": "user", "content": req.pertanyaan})
    history.append({"role": "assistant", "content": jawaban})
    top_faq = best_q if len(scores) > 0 else ""
    log_query(req.pertanyaan, cid, source=req.source,
                  centroid_sim=centroid_sim,
              clf_domain=ft_domain, clf_confidence=ft_conf, clf_mode=_clf_mode,
              rrf_score=top_rrf, e5_top=float(scores[0]) if len(scores)>0 else 0,
              bm25_raw=float(scores[1]) if len(scores)>1 else 0,
              top5_faq=top5_all,
              gate="ANSWER", dijawab=True, jawaban=jawaban,
              bm25_gate=bm25_top,
              multi_part=False, session_baru=session_baru,
              llm_model=llm_model, llm_provider=llm_provider, llm_time_ms=llm_time)
    if session_baru:
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib).strftime("%H:%M")
        jawaban += f"\n\n---\n🆕 Sesi obrolan baru telah dibuka — pukul {now} WIB"
    return {"jawaban": jawaban, "skor": top_rrf}
