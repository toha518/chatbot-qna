"""
E5-based domain/intent classifier — Nara
Membedakan: greeting, capability, faq, out_of_context, unknown.
Menggunakan E5 embedding + cosine similarity ke template queries.
Gak perlu model tambahan — reuse E5 yang udah ada di pipeline.

Two-layer defense:
  Layer 1: E5 cosine similarity → 5 domains (termasuk "unknown")
  Layer 2: Keyword heuristic → tangkap pattern yang jelas di luar konteks BPS
"""

import re
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
        "perkenalkan", "kenalan", "kenalin",
        "siapa kamu", "kamu siapa", "nama kamu", "nama kamu siapa",
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
    "unknown": [
        # Tokoh & pemerintahan
        "siapa presiden Indonesia", "siapa nama presiden",
        "nama presiden Indonesia", "siapa presiden siapa",
        "siapa nama gubernur", "presiden Indonesia",
        "siapa presiden pertama", "siapa presiden sekarang",
        "siapa pahlawan nasional", "siapa nama menteri",
        "siapa nama bupati", "siapa nama walikota",
        "siapa penemu", "siapa nama orang",
        # Geografi & negara
        "dimana ibu kota Indonesia", "ibu kota Indonesia",
        "kapan indonesia merdeka", "berapa provinsi",
        "luas indonesia", "dimana indonesia",
        # Sains, resep, umum
        "resep nasi goreng", "cara masak nasi", "cara membuat kue",
        "berapa 1 ditambah 1", "matematika", "fisika", "kimia",
        "rumus fisika", "sejarah indonesia",
        # Hiburan
        "lagu populer", "film terbaru", "sepak bola",
        "siapa bilang", "saya mau makan",
        # Informasi pribadi
        "siapa nama lengkap", "siapa nama suami",
        "siapa nama istri", "siapa nama pacar",
        # Cuaca & umum
        "cuaca hari ini", "ramalan cuaca",
        "cara jadi kaya", "bisnis online",
        # General knowledge di luar BPS
        "siapa presiden amerika", "presiden rusia",
        "dimana rumah sakit", "dokter terdekat",
    ],
}

# Threshold cosine similarity — di bawah ini = out_of_context
DOMAIN_THRESHOLD = 0.42

# Layer 2: Keyword heuristic — pattern yang jelas bukan domain BPS
# Dipake sebagai post-filter kalo E5 masih ragu
_OUT_OF_SCOPE_PATTERNS = [
    # Tokoh & jabatan publik (gak relevan BPS)
    r'\bpresiden\b', r'\bgubernur\b', r'\bmenteri\b',
    r'\bbupati\b', r'\bwalikota\b', r'\bpahlawan\b',
    # Geografi di luar BPS
    r'\bibukota\b', r'\bibu kota\b', r'\bnegara\b.*\bindonesia\b',
    r'\bprovinsi\b.*\bindonesia\b',
    # Resep & kuliner
    r'\bresep\b', r'\bmasak\b', r'\bgoreng\b',
    r'\bkue\b', r'\bmakanan\b',
    # Sains murni
    r'\bmatematika\b', r'\bfisika\b', r'\bkimia\b',
    r'\bsejarah\b', r'\brumus\b',
    # Hiburan & lifestyle
    r'\bsepak bola\b', r'\bolahraga\b', r'\blagu\b',
    r'\bfilm\b', r'\bcuaca\b', r'\bzodiak\b',
    r'\bramalan\b',
    # Nama negara selain Indonesia (biasanya bukan BPS)
    r'\bamerika\b', r'\brusia\b', r'\bchina\b', r'\bjepang\b',
    r'\bmalaysia\b', r'\bsingapura\b', r'\beropa\b',
]

# Compile patterns
_OUT_OF_SCOPE_RE = re.compile(
    '|'.join(_OUT_OF_SCOPE_PATTERNS),
    re.IGNORECASE
)

# Domain yang "lemah" — kena heuristic override kalau match keyword
_WEAK_DOMAINS = {"greeting", "capability"}

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
            print(f"[DOMAIN] Template '{domain}': {len(templates)} patterns → {_template_embeddings[domain].shape}")
        except Exception as e:
            print(f"[DOMAIN] ⚠️ Gagal encode template '{domain}': {e}")

    _initialized = bool(_template_embeddings)
    print(f"[DOMAIN] Domain filter ready — {len(_template_embeddings)} domains, threshold={DOMAIN_THRESHOLD}")


def _heuristic_check(query: str) -> bool:
    """Layer 2: cek apakah query mengandung keyword di luar konteks BPS.
    Return True kalo terindikasi out-of-scope."""
    return bool(_OUT_OF_SCOPE_RE.search(query))


def classify(query_embedding: np.ndarray, query_text: str = "") -> tuple[str, float]:
    """Klasifikasi intent user dari E5 query embedding + heuristic fallback.

    Args:
        query_embedding: E5 embedding vector (768d) — SUDAH diprefix "query:"
        query_text: teks asli query (buat Layer 2 heuristic)

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

    # ── Layer 1: E5 cosine similarity ke semua domain ──
    for domain, emb_list in _template_embeddings.items():
        scores = cosine_similarity(query_embedding, emb_list).flatten()
        if len(scores) == 0:
            continue
        max_score = float(scores.max())

        if max_score > best_score:
            best_score = max_score
            best_domain = domain

    # ── Layer 2: Heuristic override ──
    # Kalau E5 classify ke greeting/capability (domain lemah)
    # Tapi query mengandung keyword luar BPS → override
    if best_domain in _WEAK_DOMAINS and query_text:
        if _heuristic_check(query_text):
            print(f"[DOMAIN] Heuristic override: '{query_text[:50]}' → out_of_context (was {best_domain})")
            best_domain = "out_of_context"
            best_score = 0.0

    # ── Kalau best domain adalah "unknown" → out_of_context ──
    if best_domain == "unknown":
        print(f"[DOMAIN] E5 match ke 'unknown' domain → out_of_context (conf={best_score:.3f})")
        best_domain = "out_of_context"
        best_score = 0.0

    # ── Threshold ──
    if best_score < DOMAIN_THRESHOLD:
        return "out_of_context", best_score

    return best_domain, best_score
