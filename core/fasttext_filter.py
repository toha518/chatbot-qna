"""
FastText-based domain classifier — Nara Layer 2 filter
Membedakan: greeting, capability, out_of_context.
Hanya dipanggil KALAU FAQ sim (E5) < threshold.

Layer 2: FastText (4MB, <0.5ms) — lightweight intent classifier
- Startup pertama: train dari fasttext_train.txt, simpan .ftz (2 detik)
- Startup berikut: load .ftz langsung (instant)
"""

import os
import numpy as np

_FT_DIR = os.path.dirname(os.path.abspath(__file__))
_FT_TRAIN_PATH = os.path.join(_FT_DIR, "fasttext_train.txt")
_FT_MODEL_PATH = os.path.join(_FT_DIR, "domain_filter.ftz")

_model = None
_ready = False


def init_classifier() -> None:
    """Load atau train FastText model.
    Panggil SEKALI di startup.
    
    Prioritas: load .ftz (instant) > train dari .txt (2 detik)
    """
    global _model, _ready

    try:
        import fasttext
    except ImportError:
        print("[FASTTEXT] ⚠️ fasttext library not installed")
        return

    # Coba load model yang udah ada
    if os.path.exists(_FT_MODEL_PATH):
        try:
            _model = fasttext.load_model(_FT_MODEL_PATH)
            _ready = True
            ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
            print(f"[FASTTEXT] Loaded from {os.path.basename(_FT_MODEL_PATH)} ({ftz_size}KB)")
            return
        except Exception as e:
            print(f"[FASTTEXT] ⚠️ Gagal load model: {e} — retrain")

    # Gak ada model — train dari scratch
    if not os.path.exists(_FT_TRAIN_PATH):
        print(f"[FASTTEXT] ⚠️ Training data not found at {_FT_TRAIN_PATH}")
        return

    try:
        print(f"[FASTTEXT] Training classifier from {os.path.basename(_FT_TRAIN_PATH)}...")
        _model = fasttext.train_supervised(
            input=_FT_TRAIN_PATH,
            dim=100, epoch=25, lr=0.5,
            wordNgrams=2, minCount=1,
            bucket=10000,
            loss='softmax'
        )
        _model.save_model(_FT_MODEL_PATH)
        _ready = True
        ftz_size = os.path.getsize(_FT_MODEL_PATH) >> 10
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
