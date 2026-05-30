"""
FastText-based domain classifier — Nara Layer 2 filter
Membedakan: greeting, capability, out_of_context.
Hanya dipanggil KALAU FAQ sim (E5) < threshold.

Dual mode:
  - Primary: FastText (4MB, <0.5ms) — jalan di Linux / VPS
  - Fallback: keyword heuristic — auto aktif kalo FastText error (Windows numpy bug)
"""

import os
import re

_FT_DIR = os.path.dirname(os.path.abspath(__file__))
_FT_TRAIN_PATH = os.path.join(_FT_DIR, "fasttext_train.txt")
_FT_MODEL_PATH = os.path.join(_FT_DIR, "domain_filter.ftz")

_model = None
_ready = False
_using_fallback = False

# ── Fallback keyword patterns (extracted from fasttext_train.txt) ──
_GREETING_KEYWORDS = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "permisi", "assalamualaikum", "assalamu'alaikum",
    "good morning", "good afternoon", "good evening",
    "apa kabar",
    "tes", "test",
    "coba",
    "min", "mas",
    "eh", "hii", "hei",
    "p",
]

_CAPABILITY_KEYWORDS = [
    "kamu bisa apa", "bisa apa",
    "fitur apa", "fungsi kamu", "tugas kamu", "peran kamu",
    "keahlian kamu", "kegunaan kamu",
    "apa yang bisa", "ada yang bisa",
    "bantuan apa",
    "siapa kamu", "kamu siapa", "nama kamu",
    "kamu ini apa", "bot apa",
    "perkenalkan", "kenalan", "kenalin",
    "ceritakan tentang dirimu", "jelaskan tentang dirimu",
    "what can you do",
]

_GREETING_PREFIXES = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "assalamu",
]


def _keyword_classify(text: str) -> tuple[str, float]:
    """Fallback classifier pake keyword matching.
    Cek capability dulu (string spesifik), baru greeting (prefix & keyword).
    """
    t = text.strip().lower()

    # Capability — exact substring match (spesifik)
    for kw in _CAPABILITY_KEYWORDS:
        if kw in t:
            return "capability", 0.95

    # Greeting — prefix match (biar "haloo", "pagi min" kena)
    words = t.split()
    for w in words:
        for prefix in _GREETING_PREFIXES:
            if w.startswith(prefix):
                return "greeting", 0.90

    # Greeting — multi-word exact match
    for kw in _GREETING_KEYWORDS:
        if kw in t:
            return "greeting", 0.85

    return "out_of_context", 0.0


def init_classifier() -> None:
    """Load atau train FastText model.
    Panggil SEKALI di startup.
    
    FastText = primary, keyword = fallback kalo gagal.
    """
    global _model, _ready, _using_fallback

    try:
        import fasttext
    except ImportError:
        print("[FASTTEXT] ⚠️ Library not installed — using keyword fallback")
        _using_fallback = True
        _ready = True
        return

    # Coba load model
    if os.path.exists(_FT_MODEL_PATH):
        try:
            _model = fasttext.load_model(_FT_MODEL_PATH)
            # Test predict — kalo gagal (Windows numpy bug), fallback
            try:
                _model.predict("test")
            except Exception as e:
                print(f"[FASTTEXT] ⚠️ Predict error: {str(e)[:60]}... — using keyword fallback")
                _model = None
                _using_fallback = True
                _ready = True
                return

            _ready = True
            ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
            print(f"[FASTTEXT] Loaded from {os.path.basename(_FT_MODEL_PATH)} ({ftz_size}KB)")
            return
        except Exception as e:
            print(f"[FASTTEXT] ⚠️ Gagal load: {str(e)[:60]}... — using keyword fallback")

    # Train dari scratch
    if not os.path.exists(_FT_TRAIN_PATH):
        print("[FASTTEXT] ⚠️ Training data not found — using keyword fallback")
        _using_fallback = True
        _ready = True
        return

    try:
        print(f"[FASTTEXT] Training from {os.path.basename(_FT_TRAIN_PATH)}...")
        _model = fasttext.train_supervised(
            input=_FT_TRAIN_PATH, dim=100, epoch=25, lr=0.5,
            wordNgrams=2, minCount=1, bucket=10000, loss='softmax'
        )
        _model.save_model(_FT_MODEL_PATH)
        _ready = True
        ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
        print(f"[FASTTEXT] Ready — {ftz_size}KB model saved")
    except Exception as e:
        print(f"[FASTTEXT] ⚠️ Train gagal: {str(e)[:60]}... — fallback keyword")
        _using_fallback = True
        _ready = True


def classify(text: str, threshold: float = 0.60) -> tuple[str, float]:
    """Predict intent — FastText (primary) / keyword fallback.

    Args:
        text: raw user query
        threshold: minimum confidence (default 0.60)

    Returns:
        (domain, confidence):
            "greeting" | "capability" | "out_of_context"
    """
    if not _ready:
        return "out_of_context", 0.0

    if _using_fallback:
        domain, confidence = _keyword_classify(text)
        if confidence < threshold:
            return "out_of_context", confidence
        return domain, confidence

    # FastText mode
    try:
        labels, scores = _model.predict(text.strip().lower())
        domain = labels[0].replace("__label__", "")
        confidence = float(scores[0])

        if confidence < threshold:
            return "out_of_context", confidence
        return domain, confidence

    except Exception as e:
        print(f"[FASTTEXT] Error: {str(e)[:60]} — fallback keyword")
        return _keyword_classify(text)
