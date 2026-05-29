"""
FastText-based domain classifier — Nara Layer 2 filter
Membedakan: greeting, capability, out_of_context.
Hanya dipanggil KALAU FAQ sim (E5) < threshold.

Layer 2: FastText (4MB, <0.5ms) — lightweight intent classifier
Training otomatis di startup dari file fasttext_train.txt (~2 detik)
"""

import os
import numpy as np

_FT_DIR = os.path.dirname(os.path.abspath(__file__))
_FT_TRAIN_PATH = os.path.join(_FT_DIR, "fasttext_train.txt")

_model = None
_ready = False


def init_classifier() -> None:
    """Train FastText model dari training data — panggil SEKALI di startup.
    Training cuma ~2 detik, model ~4MB di RAM."""
    global _model, _ready

    if not os.path.exists(_FT_TRAIN_PATH):
        print(f"[FASTTEXT] ⚠️ Training data not found at {_FT_TRAIN_PATH}")
        return

    try:
        import fasttext
        print(f"[FASTTEXT] Training classifier from {_FT_TRAIN_PATH}...")
        _model = fasttext.train_supervised(
            input=_FT_TRAIN_PATH,
            dim=100, epoch=25, lr=0.5,
            wordNgrams=2, minCount=1,
            bucket=10000,
            loss='softmax'
        )
        _ready = True
        # Save compressed model as fallback
        ftz_path = os.path.join(_FT_DIR, "domain_filter.ftz")
        _model.save_model(ftz_path)
        ftz_size = os.path.getsize(ftz_path) >> 10
        print(f"[FASTTEXT] Domain classifier ready — {ftz_size}KB model saved")
    except Exception as e:
        print(f"[FASTTEXT] ⚠️ Gagal train model: {e}")
        _ready = False


def classify(text: str, threshold: float = 0.60) -> tuple[str, float]:
    """Predict intent pake FastText.

    Args:
        text: raw user query
        threshold: minimum confidence (default 0.60)

    Returns:
        (domain, confidence):
            "greeting" | "capability" | "out_of_context"
    """
    if not _ready or _model is None:
        return "out_of_context", 0.0

    try:
        labels, scores = _model.predict(text.strip().lower())
        domain = labels[0].replace("__label__", "")
        confidence = float(scores[0])

        if confidence < threshold:
            return "out_of_context", confidence

        return domain, confidence

    except Exception as e:
        print(f"[FASTTEXT] Error: {e}")
        return "out_of_context", 0.0
