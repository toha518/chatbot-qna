"""
query_logger.py — Logging evaluasi query Nara
Mencatat tiap pertanyaan user + BM25 score + status + jawaban
Format: JSONL (JSON Lines) — 1 baris per query
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "query_log.jsonl"
_MAX_LINES = 50000  # rotasi otomatis kalo udah 50ribu baris


def _wib_now() -> str:
    return datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")


def log_query(
    pertanyaan: str,
    chat_id: str,
    bm25_score: float,
    bm25_status: str,       # "ACCEPT" | "REJECT"
    top_score: float = 0.0,
    top_faq: str = "",
    dijawab: bool = False,
    jawaban: str = "",
    multi_part: bool = False,
    greeting: bool = False,
    error: str = "",
):
    """Catat satu query ke file JSONL"""

    entry = {
        "waktu": _wib_now(),
        "chat_id": str(chat_id)[:16],
        "pertanyaan": pertanyaan[:200],
        "bm25_score": round(bm25_score, 2),
        "bm25_status": bm25_status,
        "top_score": round(top_score, 3),
        "top_faq": top_faq[:100],
        "dijawab": dijawab,
        "multi_part": multi_part,
        "greeting": greeting,
        "error": error[:100],
    }

    # Ambil 100 karakter pertama jawaban
    if jawaban:
        entry["jawaban_preview"] = jawaban[:100]

    try:
        # Cek rotasi
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 500 * 1024:  # 500KB
            _rotate()

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LOG] Gagal nulis log: {e}")


def _rotate():
    """Rotasi file log kalo kegedean — rename + buat baru"""
    if LOG_FILE.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = LOG_FILE.with_name(f"query_log_{ts}.jsonl")
        try:
            LOG_FILE.rename(backup)
            print(f"[LOG] Rotasi: {LOG_FILE.name} → {backup.name}")
        except Exception:
            pass


def get_stats() -> dict:
    """Baca file log dan kasi ringkasan statistik"""
    if not LOG_FILE.exists():
        return {"total": 0, "accepted": 0, "rejected": 0, "greetings": 0}

    total = 0
    accepted = 0
    rejected = 0
    greetings = 0
    errors = 0

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    total += 1
                    if entry.get("greeting"):
                        greetings += 1
                    elif entry.get("bm25_status") == "ACCEPT":
                        accepted += 1
                    else:
                        rejected += 1
                    if entry.get("error"):
                        errors += 1
                except json.JSONDecodeError:
                    continue
    except Exception:
        return {"total": total, "accepted": accepted, "rejected": rejected}

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "greetings": greetings,
        "errors": errors,
        "file": str(LOG_FILE),
        "size_kb": round(LOG_FILE.stat().st_size / 1024, 1) if LOG_FILE.exists() else 0,
    }
