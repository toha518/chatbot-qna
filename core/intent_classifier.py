"""
Text classifier — Nara Layer 1 filter
Membedakan: greeting, capability, positive_feedback, negative_feedback, forward.

Dual mode:
  - Primary: SGDClassifier + TF-IDF (<10KB model, <1ms inferensi)
  - Fallback: keyword heuristic — auto aktif kalo scikit-learn gagal import
"""

import os
import re
import pickle

_FT_DIR = os.path.dirname(os.path.abspath(__file__))
_FT_TRAIN_PATH = os.path.join(_FT_DIR, "classifier_train.txt")
_FT_MODEL_PATH = os.path.join(_FT_DIR, "domain_filter.ftz")

_model = None
_vectorizer = None
_ready = False
_using_fallback = False

# ═══════════════════════════════════════════════════════════════
# FALLBACK — keyword matching (safety net kalo sklearn gak ada)
# ═══════════════════════════════════════════════════════════════

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

_GREETING_PATTERNS = [
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "good morning", "good afternoon", "good evening",
    "apa kabar",
    "assalamualaikum", "assalamu'alaikum",
]

_GREETING_TOKENS = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "permisi", "tes", "test", "coba",
    "min", "mas", "eh", "hii", "hei", "p",
]

_GREETING_PREFIX = [
    "halo", "hai", "hy", "hey", "hi", "helo", "hallo", "hello",
    "pagi", "siang", "sore", "malam",
    "assalamu",
]

_GREETING_TOKEN_RE = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in _GREETING_TOKENS) + r')\b',
    re.IGNORECASE
)

_LABELS = [
    "positive_feedback",
    "negative_feedback",
    "capability",
    "greeting",
    "forward",
]


def _keyword_classify(text: str) -> tuple[str, float]:
    """Fallback classifier pake keyword matching."""
    t = text.strip().lower()

    for kw in _POSITIVE_FEEDBACK_KEYWORDS:
        if kw in t:
            return "positive_feedback", 0.95
    for kw in _NEGATIVE_FEEDBACK_KEYWORDS:
        if kw in t:
            return "negative_feedback", 0.95
    for kw in _CAPABILITY_KEYWORDS:
        if kw in t:
            return "capability", 0.95

    words = t.split()
    for w in words:
        for prefix in _GREETING_PREFIX:
            if w.startswith(prefix):
                return "greeting", 0.90
    for phrase in _GREETING_PATTERNS:
        if phrase in t:
            return "greeting", 0.90
    if _GREETING_TOKEN_RE.search(t):
        return "greeting", 0.85

    return "forward", 0.0


# ═══════════════════════════════════════════════════════════════
# PRIMARY — scikit-learn SGDClassifier + TF-IDF
# ═══════════════════════════════════════════════════════════════

def _load_training_data(path: str) -> tuple[list[str], list[str]]:
    """Parse classifier_train.txt → (texts, labels)"""
    texts, labels = [], []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Format: __label__<class> <text>
            parts = line.split(' ', 1)
            if len(parts) < 2:
                continue
            label = parts[0].replace('__label__', '')
            text = parts[1]
            texts.append(text)
            labels.append(label)
    return texts, labels


def init_classifier() -> None:
    """Load atau train classifier.
    PRIMARY: SGDClassifier + TF-IDF (pure Python, zero C++ compiler)
    FALLBACK: keyword heuristic
    """
    global _model, _vectorizer, _ready, _using_fallback

    # Step 1: Coba load model yang udah ada
    if os.path.exists(_FT_MODEL_PATH):
        try:
            with open(_FT_MODEL_PATH, 'rb') as f:
                data = pickle.load(f)
            _vectorizer = data['vectorizer']
            _model = data['model']
            # Test predict
            _model.predict(_vectorizer.transform(["test"]))
            _ready = True
            ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
            print(f"[CLF] ✅ Loaded from {os.path.basename(_FT_MODEL_PATH)} ({ftz_size}KB)")
            return
        except Exception as e:
            print(f"[CLF] ⚠️ Gagal load model: {str(e)[:60]}...")

    # Step 2: Train dari scratch
    if not os.path.exists(_FT_TRAIN_PATH):
        print("[CLF] ⚠️ Training data tidak ditemukan — keyword fallback")
        _using_fallback = True
        _ready = True
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import SGDClassifier

        texts, labels = _load_training_data(_FT_TRAIN_PATH)
        unique_labels = len(set(labels))
        print(f"[CLF] Training from {os.path.basename(_FT_TRAIN_PATH)} "
              f"({len(texts)} samples, {unique_labels} classes)...")

        # Char n-gram + word n-gram — mirip FastText subword
        _vectorizer = TfidfVectorizer(
            analyzer='char_wb', ngram_range=(2, 4),
            max_features=5000, lowercase=True
        )
        X = _vectorizer.fit_transform(texts)

        _model = SGDClassifier(
            loss='log_loss', penalty='l2', alpha=1e-4,
            max_iter=500, tol=1e-4, random_state=42
        )
        _model.fit(X, labels)

        # Accuracy check
        acc = _model.score(X, labels)
        print(f"[CLF] Training accuracy: {acc*100:.1f}%")

        # Save
        with open(_FT_MODEL_PATH, 'wb') as f:
            pickle.dump({'vectorizer': _vectorizer, 'model': _model}, f)
        ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
        print(f"[CLF] Ready — {ftz_size}KB model saved")
        _ready = True

    except ImportError:
        print("[CLF] ⚠️ scikit-learn tidak terinstall — keyword fallback")
        _using_fallback = True
        _ready = True
    except Exception as e:
        print(f"[CLF] ⚠️ Training gagal: {str(e)[:60]} — keyword fallback")
        _using_fallback = True
        _ready = True


def classify(text: str, threshold: float = 0.40) -> tuple[str, float]:
    """Predict intent — SGDClassifier / keyword fallback.

    Returns:
        (domain, confidence):
            "greeting" | "capability" | "positive_feedback" |
            "negative_feedback" | "forward"
    """
    if not _ready:
        return "forward", 0.0

    if _using_fallback:
        domain, confidence = _keyword_classify(text)
        if confidence < threshold:
            return "forward", confidence
        return domain, confidence

    # Scikit-learn mode
    try:
        X = _vectorizer.transform([text.strip().lower()])
        probs = _model.predict_proba(X)[0]
        best_idx = probs.argmax()
        confidence = float(probs[best_idx])
        domain = _model.classes_[best_idx]

        if confidence < threshold:
            return "forward", confidence
        return domain, confidence

    except Exception as e:
        print(f"[CLF] Predict error: {str(e)[:60]} — fallback keyword")
        return _keyword_classify(text)
