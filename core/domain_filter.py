"""
E5-based domain/intent classifier — Nara
Membedakan: greeting, capability, faq, out_of_context.
Menggunakan E5 embedding + cosine similarity ke template queries.
Gak perlu model tambahan — reuse E5 yang udah ada di pipeline.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

DOMAIN_TEMPLATES = {
    "greeting": [
        "halo", "hai", "pagi", "siang", "sore", "malam",
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
        "permisi", "tes", "test", "hey", "hi", "hy", "assalamualaikum",
        "apa kabar", "good morning", "good afternoon", "good evening",
        "p", "test aja", "coba", "coba dulu",
    ],
    "capability": [
        "kamu bisa apa", "fitur apa saja", "apa yang kamu bisa",
        "apa saja yang kamu bisa", "kamu bisa bantu apa",
        "fungsi kamu", "tugas kamu", "peran kamu",
        "kamu bisa melakukan apa", "ada yang bisa kamu lakukan",
        "bantuan apa yang kamu berikan", "kamu bisa apa aja",
        "what can you do", "kegunaan kamu", "keahlian kamu",
        "siapa kamu", "kamu siapa", "nama kamu", "nama kamu siapa",
        "perkenalkan", "kenalan", "kenalin",
        "how are you", "kabar", "lagi apa",
    ],
    "faq": [
        "cara daftar", "lupa password", "syarat ketentuan",
        "persyaratan", "dokumen apa saja", "berapa biaya",
        "dimana lokasi", "jam operasional", "cara bayar",
        "cara mengisi", "tata cara", "bagaimana cara",
        "ketentuan", "langkah langkah", "prosedur",
        "apa itu", "what is", "how to", "how do i",
        "apakah bisa", "apakah harus", "apakah perlu",
        "dimana", "kapan", "mengapa", "kenapa",
        "cara pakai", "cara menggunakan", "cara aktivasi",
        "pendaftaran", "pendaftar", "mendaftar",
        "login", "log in", "masuk akun",
        "sim", "syarat", "dokumen", "berkas",
        "waktu", "batas waktu", "deadline",
        "gagal", "error", "tidak bisa", "masalah",
        "update", "versi", "perubahan", "info terbaru",
        "cara aktivasi sim", "aktivasi akun",
        "data tidak sesuai", "kesalahan data",
    ],
}

# Threshold cosine similarity — di bawah ini = out_of_context
DOMAIN_THRESHOLD = 0.42

# Cached template embeddings: {"greeting": np.array([[...], ...]), ...}
_template_embeddings: dict[str, np.ndarray] = {}
_initialized = False


def init_templates(embedder) -> None:
    """Compute & cache E5 embeddings buat SEMUA domain templates.
    Panggil SEKALI di startup — setelah E5 model di-load.
    """
    global _template_embeddings, _initialized

    if embedder is None:
        print("[DOMAIN] ⚠️ embedder None — skip init")
        return

    _template_embeddings = {}

    for domain, templates in DOMAIN_TEMPLATES.items():
        if not templates:
            continue
        # E5 passage prefix untuk template (bukan query prefix)
        passage_texts = [f"passage: {t}" for t in templates]
        try:
            _template_embeddings[domain] = embedder.encode(
                passage_texts, show_progress_bar=False
            )
            print(f"[DOMAIN] Template '{domain}': {len(templates)} patterns → {len(_template_embeddings[domain])} vecs")
        except Exception as e:
            print(f"[DOMAIN] ⚠️ Gagal encode template '{domain}': {e}")

    _initialized = bool(_template_embeddings)
    print(f"[DOMAIN] Domain filter ready — {len(_template_embeddings)} domains, threshold={DOMAIN_THRESHOLD}")


def classify(query_embedding: np.ndarray) -> tuple[str, float]:
    """Klasifikasi intent user dari E5 query embedding.

    Args:
        query_embedding: E5 embedding vector (768d) — SUDAH diprefix "query:"

    Returns:
        (domain, confidence):
            "greeting" | "capability" | "faq" | "out_of_context"
    """
    if not _initialized or not _template_embeddings:
        return "faq", 0.5

    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)

    best_domain = "out_of_context"
    best_score = 0.0

    for domain, emb_list in _template_embeddings.items():
        scores = cosine_similarity(query_embedding, emb_list).flatten()
        if len(scores) == 0:
            continue
        max_score = float(scores.max())

        if max_score > best_score:
            best_score = max_score
            best_domain = domain

    if best_score < DOMAIN_THRESHOLD:
        return "out_of_context", best_score

    return best_domain, best_score
