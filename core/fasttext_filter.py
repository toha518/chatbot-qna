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
import numpy as np

# ── PATCH: numpy 2.x + FastText C extension incompatibility ──
# FastText internals call np.array(buf, copy=False) — numpy 2.x on
# Windows can't do zero-copy on that buffer type → ValueError.
# Patch: intercept, retry with copy=True. Tetap aktif sepanjang
# runtime karena model.predict() dipanggil setiap chat.
# https://github.com/facebookresearch/fastText/issues/1067
_np_array_original = np.array
_np_patched = [False]
def _np_array_fasttext_compat(obj, *args, **kwargs):
    try:
        return _np_array_original(obj, *args, **kwargs)
    except ValueError:
        _np_patched[0] = True
        kwargs['copy'] = True
        return _np_array_original(obj, *args, **kwargs)

def _patch_numpy():
    np.array = _np_array_fasttext_compat

def _unpatch_numpy():
    np.array = _np_array_original

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

_POSITIVE_FEEDBACK_KEYWORDS = [
    "makasih", "terima kasih", "terimakasih", "thanks", "thank you",
    "makasih ya", "makasih banyak", "trims", "tengkyu",
    "makasih kak", "makasih min", "makasih bang", "makasih loh",
    "terima kasih banyak", "thank you so much",
    "ok", "oke", "sip", "siap", "oke sip", "ok deh", "okee",
    "baik", "baiklah", "noted",
    "oke kak", "oke min", "siap kak",
    "mantap", "thanks ya",
]

_NEGATIVE_FEEDBACK_KEYWORDS = [
    "tidak membantu", "ga membantu", "gak membantu", "tak membantu",
    "kamu tidak membantu", "kamu ga membantu", "kamu gak membantu",
    "ga membantu jawabanmu", "jawabanmu ga membantu",
    "gak guna", "ga guna", "tak guna",
    "kamu gak guna", "kamu ga guna",
    "jelek", "jelek banget", "kamu jelek", "bot jelek",
    "gak jelas", "ga jelas", "jawabanmu gak jelas",
    "payah", "kamu payah",
    "bot sampah",
    "percuma", "percuma nanya", "sia sia",
    "jawabanmu salah", "salah semua",
    "ngawur", "jawabanmu ngawur",
    "kamu bodoh", "gak paham", "ga paham",
]

# ── Compiled regex patterns ──
# Multi-word phrases bisa substring match (gak ada false positive)
# Single words pake word boundary \b biar "p" gak match "presiden"
_GREETING_PATTERNS = [
    # Multi-word (substring safe)
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "good morning", "good afternoon", "good evening",
    "apa kabar",
    "assalamualaikum", "assalamu'alaikum",
]

# Single-word + word boundary \b
_GREETING_TOKENS = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "permisi", "tes", "test", "coba",
    "min", "mas", "eh", "hii", "hei", "p",
]

# PREFIX = single word prefix (biar "haloo", "pagi2", "assalamu" kena)
_GREETING_PREFIX = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "assalamu",
]

# Compile once
_GREETING_TOKEN_RE = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in _GREETING_TOKENS) + r')\b',
    re.IGNORECASE
)


def _keyword_classify(text: str) -> tuple[str, float]:
    """Fallback classifier pake keyword matching.
    Cek capability dulu (frasa spesifik), baru greeting (prefix & token regex).
    """
    t = text.strip().lower()

    # ── Positive feedback — "makasih", "ok", "sip" ──
    for kw in _POSITIVE_FEEDBACK_KEYWORDS:
        if kw in t:
            return "positive_feedback", 0.95

    # ── Negative feedback — "ga membantu", "jelek" ──
    for kw in _NEGATIVE_FEEDBACK_KEYWORDS:
        if kw in t:
            return "negative_feedback", 0.95

    # ── Capability — exact phrase match (spesifik, aman dari false positive) ──
    for kw in _CAPABILITY_KEYWORDS:
        if kw in t:
            return "capability", 0.95

    # ── Greeting: prefix match (biar "haloo", "pagi min" kena) ──
    words = t.split()
    for w in words:
        for prefix in _GREETING_PREFIX:
            if w.startswith(prefix):
                return "greeting", 0.90

    # ── Greeting: multi-word substring ──
    for phrase in _GREETING_PATTERNS:
        if phrase in t:
            return "greeting", 0.90

    # ── Greeting: single token word boundary ──
    if _GREETING_TOKEN_RE.search(t):
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

    # ── Patch numpy untuk FastText (Windows numpy 2.x compatibility) ──
    # FastText C extension internals call np.array(buf, copy=False)
    # Patch ini tetap aktif sepanjang runtime — hanya ngaruh saat
    # np.array gagal zero-copy (kasus FastText aja, bukan numpy normal)
    _patch_numpy()

    # Coba load model
    if os.path.exists(_FT_MODEL_PATH):
        try:
            _model = fasttext.load_model(_FT_MODEL_PATH)
            # Test predict
            _model.predict("test")

            if _np_patched[0]:
                print(f"[FASTTEXT] ✅ Loaded with numpy compatibility patch")
            _ready = True
            ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
            print(f"[FASTTEXT] Loaded from {os.path.basename(_FT_MODEL_PATH)} ({ftz_size}KB)")
            return
        except Exception as e:
            _unpatch_numpy()
            print(f"[FASTTEXT] ⚠️ Predict error: {str(e)[:60]}... — using keyword fallback")
            _model = None
            _using_fallback = True
            _ready = True
            return

    _unpatch_numpy()

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
