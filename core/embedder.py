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
        question_vecs = embedder.encode(
            ["passage: " + q for q in questions],
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
            question_vecs = embedder.encode(
                ["passage: " + q for q in questions],
                show_progress_bar=False
            )
        return len(questions)


def init_data(csv_url: str) -> int:
    """Panggil pas startup: load E5 + data dari Google Sheets"""
    t0 = time.time()
    init_embedder()
    total = load_from_gsheet(csv_url)
    print(f"[BOOT] Ready! ({total} Q&A, {time.time()-t0:.1f}s)")
    return total


def classify_domain(query: str, threshold: float = 0.20) -> tuple[bool, float]:
    """
    Cek apakah pertanyaan masih relevan dengan domain FAQ BPS.
    Returns (in_domain, confidence_score).
    - in_domain = True kalau skor >= threshold
    - in_domain = False kalau terlalu beda dari semua FAQ
    """
    global question_vecs, questions

    if len(questions) == 0 or question_vecs is None:
        return True, 1.0  # fallback: izinin aja

    query_vec = embedder.encode(["query: " + query])
    scores = cosine_similarity(query_vec, question_vecs).flatten()
    best_score = float(scores.max())

    if best_score >= threshold:
        return True, best_score
    else:
        return False, best_score


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

    return context, scores[best_idx]
