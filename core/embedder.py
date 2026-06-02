# core/embedder.py — E5-base: load model, encode, semantic search

import pickle
import csv
import urllib.request
import os
import time
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Global state — diakses langsung dari server.py
questions: list[str] = []
answers: list[str] = []
categories: list[str] = []
question_vecs = None
embedder = None

# LRU cache — hindari encode ulang query yang sama
_query_cache: dict[str, np.ndarray] = {}
_MAX_CACHE = 128

# Domain Centroid — buat filter out-of-domain questions
_DOMAIN_THRESHOLD = 0.45  # < 0.45 = out-of-domain
domain_centroid: np.ndarray | None = None


def build_domain_centroid():
    """Bikin centroid dari semua FAQ (rata-rata vektor). Dipanggil pas startup / reload."""
    global domain_centroid, question_vecs
    if question_vecs is None or len(question_vecs) == 0:
        domain_centroid = None
        return
    domain_centroid = np.mean(question_vecs, axis=0)
    # Normalize centroid biar hasil cosine_similarity konsisten
    norm = np.linalg.norm(domain_centroid)
    if norm > 0:
        domain_centroid = domain_centroid / norm
    print(f"[DOMAIN] Centroid built from {len(question_vecs)} FAQ vectors")


def check_domain(query_vec: np.ndarray) -> float:
    """Check domain similarity. Return cosine similarity ke centroid (0-1)."""
    global domain_centroid
    if domain_centroid is None:
        return 1.0  # fallback: izinin kalo centroid belum ada
    # Normalize query vector
    norm = np.linalg.norm(query_vec)
    if norm > 0:
        query_vec = query_vec / norm
    sim = float(np.dot(query_vec, domain_centroid))
    return sim


def init_embedder():
    """Load E5-base model (~278MB)"""
    global embedder
    if embedder is None:
        print("[BOOT] Loading E5-base...")
        t0 = time.time()
        embedder = SentenceTransformer('intfloat/multilingual-e5-base')
        print(f"[BOOT] E5-base loaded ({time.time()-t0:.1f}s)")
    return embedder


def load_from_gsheet(csv_url: str) -> int:
    """
    Download CSV dari Google Sheets → parse → encode pake E5.
    Fallback ke file pickle kalo gagal.
    """
    global questions, answers, categories, question_vecs

    if not embedder:
        init_embedder()

    try:
        resp = urllib.request.urlopen(csv_url, timeout=30)
        raw = resp.read().decode("utf-8")
        lines = raw.splitlines()
        reader = csv.reader(lines)
        next(reader)  # skip header: No,Kategori,Kendala,Solusi

        qa = []
        cats = []
        for r in reader:
            if len(r) >= 4:
                k = r[1].strip()
                q = r[2].strip()
                a = r[3].strip()
                if q and a:
                    qa.append((q, a))
                    cats.append(k)

        if not qa:
            raise Exception("Data kosong dari Google Sheets")

        questions = [q for q, a in qa]
        answers = [a for q, a in qa]
        categories = cats

        print(f"[RELOAD] Encoding {len(questions)} pertanyaan...")
        # Kategori jadi metadata terpisah — gak ikut di-embedding
        # Lebih akurat karena similarity murni dari konten pertanyaan
        passage_texts = [f"passage: {q}" for q in questions]
        question_vecs = embedder.encode(
            passage_texts,
            show_progress_bar=False
        )

        # Backup ke pickle
        with open("qna_index.pkl", "wb") as f:
            pickle.dump({
                "questions": questions,
                "answers": answers,
                "categories": categories
            }, f)

        # Save FAQ → category mapping for dashboard
        try:
            import json
            with open("faq_categories.json", "w", encoding="utf-8") as f:
                json.dump(dict(zip(questions, cats)), f, ensure_ascii=False, indent=2)
            print(f"[RELOAD] Saved {len(cats)} FAQ categories to faq_categories.json")
        except Exception as e:
            print(f"[RELOAD] Gagal save FAQ categories: {e}")

        print(f"[RELOAD] {len(questions)} Q&A loaded from Google Sheets")
        _rebuild_bm25(questions)
        build_domain_centroid()
        return len(questions)

    except Exception as e:
        print(f"[RELOAD] Gagal load dari Google Sheets: {e}")
        if not questions:
            print("[RELOAD] Fallback ke pickle...")
            with open("qna_index.pkl", "rb") as f:
                data = pickle.load(f)
            questions = data["questions"]
            answers = data["answers"]
            categories = data.get("categories", [""] * len(questions))
            passage_texts = [f"passage: {q}" for q in questions]
            question_vecs = embedder.encode(
                passage_texts,
                show_progress_bar=False
            )
        _rebuild_bm25(questions)
        build_domain_centroid()
        return len(questions)


def _rebuild_bm25(questions: list):
    """Build BM25 index — robust: warning kalo rank_bm25 missing, fallback ke basic."""
    try:
        from core.bm25 import build_bm25
        build_bm25(questions)
    except ImportError:
        print("[BM25] ⚠️  rank_bm25 TIDAK DIINSTALL! Install: pip install rank-bm25")
        print("[BM25] ⚠️  BM25 scoring disabled — hanya E5 yang jalan")
    except Exception as e:
        print(f"[BM25] ⚠️  Gagal build: {e}")


def init_data(csv_url: str) -> int:
    """Panggil pas startup: load E5 + data dari Google Sheets"""
    t0 = time.time()
    init_embedder()
    total = load_from_gsheet(csv_url)
    print(f"[BOOT] Ready! ({total} Q&A, {time.time()-t0:.1f}s)")
    return total


def encode_query(query: str) -> np.ndarray:
    """Encode satu query user pake E5 — dengan LRU cache (128 query).
    Ngembaliin 768d vector — bisa dipake ulang buat filter domain & retrieval.
    """
    global embedder, _query_cache
    cached = _query_cache.get(query)
    if cached is not None:
        return cached
    if embedder is None:
        init_embedder()
    vec = embedder.encode(["query: " + query])[0]
    if len(_query_cache) >= _MAX_CACHE:
        _query_cache.pop(next(iter(_query_cache)))
    _query_cache[query] = vec
    return vec


def search(query: str, top_k: int = 3):
    """
    Cari pertanyaan paling relevan di database.
    Returns (context_string, scores_array).
    """
    global question_vecs, questions, answers, categories

    if len(questions) == 0:
        return "", np.array([])

    query_vec = embedder.encode(["query: " + query])
    scores = cosine_similarity(query_vec, question_vecs).flatten()

    best_idx = scores.argsort()[-top_k:][::-1]

    context = ""
    seen_answers = set()
    for idx in best_idx:
        if scores[idx] < 0.05:
            continue
        answer_key = answers[idx].strip()[:100]
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)

        k = ""
        if idx < len(categories) and categories[idx].strip():
            k = categories[idx].strip()

        if k:
            context += (
                f"KATEGORI: {k}\n"
                f"PERTANYAAN: {questions[idx]}\n"
                f"JAWABAN: {answers[idx]}\n\n"
            )
        else:
            context += (
                f"PERTANYAAN: {questions[idx]}\n"
                f"JAWABAN: {answers[idx]}\n\n"
            )

    # Fallback kalo semua di-skip (skor < 0.05)
    if not context and len(questions) > 0:
        idx0 = best_idx[0]
        k0 = ""
        if idx0 < len(categories) and categories[idx0].strip():
            k0 = categories[idx0].strip()
        if k0:
            context = (
                f"KATEGORI: {k0}\n"
                f"PERTANYAAN: {questions[idx0]}\n"
                f"JAWABAN: {answers[idx0]}\n\n"
            )
        else:
            context = (
                f"PERTANYAAN: {questions[idx0]}\n"
                f"JAWABAN: {answers[idx0]}\n\n"
            )

    return context, scores[best_idx], questions[best_idx[0]] if len(best_idx) > 0 else ""


def hybrid_search(query: str, top_k: int = 5, query_vec: np.ndarray = None):
    """
    Hybrid search: E5 (semantic) + BM25 (keyword) via RRF fusion.
    
    Args:
        query: teks pertanyaan user
        top_k: jumlah FAQ yang direturn
        query_vec: E5 embedding yang SUDAH di-compute (optional).
                   Kalau None, compute ulang dari query.
    
    Returns:
        (context_string, e5_top_score_array, best_question)
    """
    global question_vecs, questions, answers, categories

    if len(questions) == 0:
        return "", np.array([]), ""

    # ── E5 semantic scores ──
    if query_vec is not None:
        # Reuse embedding dari filter domain (hemat 1 encode!)
        if query_vec.ndim == 1:
            qv = query_vec.reshape(1, -1)
        else:
            qv = query_vec
    else:
        qv = embedder.encode(["query: " + query])
    e5_scores = cosine_similarity(qv, question_vecs).flatten()

    # ── BM25 keyword scores ──
    from core.bm25 import get_bm25_scores_all
    bm25_scores = np.array(get_bm25_scores_all(query))

    # ── Rank positions ──
    e5_rank = np.argsort(-e5_scores)       # descending
    bm25_rank = np.argsort(-bm25_scores)

    # ── RRF fusion ──
    K = 60  # smoothing constant
    bm25_max = float(np.max(bm25_scores))
    rrf_scores = np.zeros(len(questions))
    for i, idx in enumerate(e5_rank):
        rrf_scores[idx] += 1.0 / (i + K)
    # JANGAN tambah BM25 ke RRF kalo BM25=0 (arbitrary ranking noise)
    if bm25_max > 0:
        for i, idx in enumerate(bm25_rank):
            rrf_scores[idx] += 1.0 / (i + K)

    # ── Top-K by RRF ──
    best_idx = np.argsort(-rrf_scores)[:top_k]

    # ── Format konteks ──
    context = ""
    seen_answers = set()
    # ── Format konteks dengan peringkat ──
    rank_labels = ["⭐️ PERINGKAT 1 (JAWABAN UTAMA)", "PERINGKAT 2", "PERINGKAT 3", "PERINGKAT 4", "PERINGKAT 5"]
    rank_idx = 0
    for idx in best_idx:
        if rrf_scores[idx] < 0.001:
            continue
        answer_key = answers[idx].strip()[:100]
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)

        label = rank_labels[min(rank_idx, len(rank_labels)-1)]
        rank_idx += 1
        k = categories[idx].strip() if idx < len(categories) and categories[idx].strip() else ""
        if k:
            context += (f"{label}\n"
                        f"KATEGORI: {k}\n"
                        f"PERTANYAAN: {questions[idx]}\n"
                        f"JAWABAN: {answers[idx]}\n\n")
        else:
            context += (f"{label}\n"
                        f"PERTANYAAN: {questions[idx]}\n"
                        f"JAWABAN: {answers[idx]}\n\n")

    # ── Fallback ──
    if not context and len(questions) > 0:
        idx0 = best_idx[0]
        k0 = categories[idx0].strip() if idx0 < len(categories) and categories[idx0].strip() else ""
        if k0:
            context = (f"KATEGORI: {k0}\n"
                       f"PERTANYAAN: {questions[idx0]}\n"
                       f"JAWABAN: {answers[idx0]}\n\n")
        else:
            context = (f"PERTANYAAN: {questions[idx0]}\n"
                       f"JAWABAN: {answers[idx0]}\n\n")

    # ── Return: scores array [E5, BM25, RRF] + top-5 FAQ list ──
    best_q = questions[best_idx[0]] if len(best_idx) > 0 else ""
    top5 = [questions[i] for i in best_idx[:5]]  # semua 5 FAQ
    top_e5 = float(e5_scores[best_idx[0]]) if len(best_idx) > 0 else 0
    top_bm25 = float(bm25_scores[best_idx[0]]) if len(best_idx) > 0 else 0
    top_rrf = float(rrf_scores[best_idx[0]]) if len(best_idx) > 0 else 0
    return context, np.array([top_e5, top_bm25, top_rrf]), best_q, top5
