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

        print(f"[RELOAD] {len(questions)} Q&A loaded from Google Sheets")
        from core.bm25 import build_bm25; build_bm25(questions)
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
        from core.bm25 import build_bm25; build_bm25(questions)
        return len(questions)


def init_data(csv_url: str) -> int:
    """Panggil pas startup: load E5 + data dari Google Sheets"""
    t0 = time.time()
    init_embedder()
    total = load_from_gsheet(csv_url)
    print(f"[BOOT] Ready! ({total} Q&A, {time.time()-t0:.1f}s)")
    return total


def encode_query(query: str) -> np.ndarray:
    """Encode satu query user pake E5.
    Ngembaliin 768d vector — bisa dipake ulang buat filter domain & retrieval.
    """
    global embedder
    if embedder is None:
        init_embedder()
    return embedder.encode(["query: " + query])[0]


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
    rrf_scores = np.zeros(len(questions))
    for i, idx in enumerate(e5_rank):
        rrf_scores[idx] += 1.0 / (i + K)
    for i, idx in enumerate(bm25_rank):
        rrf_scores[idx] += 1.0 / (i + K)

    # ── Top-K by RRF ──
    best_idx = np.argsort(-rrf_scores)[:top_k]

    # ── Format konteks ──
    context = ""
    seen_answers = set()
    for idx in best_idx:
        if rrf_scores[idx] < 0.001:
            continue
        answer_key = answers[idx].strip()[:100]
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)

        k = categories[idx].strip() if idx < len(categories) and categories[idx].strip() else ""
        if k:
            context += (f"KATEGORI: {k}\n"
                        f"PERTANYAAN: {questions[idx]}\n"
                        f"JAWABAN: {answers[idx]}\n\n")
        else:
            context += (f"PERTANYAAN: {questions[idx]}\n"
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

    # ── Return E5 top score sebagai skor utama ──
    # (threshold 0.82 tetap relevan karena E5 skor asli)
    best_q = questions[best_idx[0]] if len(best_idx) > 0 else ""
    top_e5 = float(e5_scores[best_idx[0]]) if len(best_idx) > 0 else 0
    return context, np.array([top_e5]), best_q
