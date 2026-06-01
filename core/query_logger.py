"""
query_logger.py — Dual-write logging Nara (JSONL + SQLite)
Format: JSONL (1 baris JSON) + SQLite untuk analytics jangka panjang.
Logging non-blocking: writes via background thread.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent
JSONL_FILE = LOG_DIR / "query_log.jsonl"
SQLITE_FILE = LOG_DIR / "query_log.db"
_MAX_JSONL_SIZE_KB = 500
_sqlite_lock = threading.Lock()
_sqlite_ready = False


def _wib_now() -> str:
    return datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")


def _ensure_sqlite():
    """Lazy init — cuma di-thread pertama yang butuh. Aman dari race condition kalo di-import barengan."""
    global _sqlite_ready
    if _sqlite_ready:
        return
    with _sqlite_lock:
        if _sqlite_ready:
            return
        db = sqlite3.connect(str(SQLITE_FILE))
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                pertanyaan TEXT,
                clf_domain TEXT,
                clf_confidence REAL,
                clf_mode TEXT,
                rrf_score REAL,
                e5_top REAL,
                bm25_raw REAL,
                top5_faq TEXT,
                source TEXT,
                gate TEXT,
                gate_detail TEXT,
                dijawab INTEGER,
                jawaban TEXT,
                jawaban_length INTEGER,
                llm_model TEXT,
                llm_provider TEXT,
                llm_time_ms INTEGER,
                multi_part INTEGER,
                session_baru INTEGER,
                error TEXT
            )
        """)
        # Migrasi: tambah kolom source kalo belum ada
        try:
            db.execute("ALTER TABLE logs ADD COLUMN source TEXT DEFAULT ''")
        except Exception:
            pass
        db.execute("CREATE INDEX IF NOT EXISTS idx_waktu ON logs(waktu)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_gate ON logs(gate)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_clf ON logs(clf_domain)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_chat ON logs(chat_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_source ON logs(source)")
        db.commit()
        db.close()
        _sqlite_ready = True


def log_query(
    pertanyaan: str,
    chat_id: str,
    *,
    source: str = "",
    clf_domain: str = "",
    clf_confidence: float = 0.0,
    clf_mode: str = "scikit-learn",
    rrf_score: float = 0.0,
    e5_top: float = 0.0,
    bm25_raw: float = 0.0,
    top5_faq: list = None,
    gate: str = "",
    gate_detail: str = "",
    dijawab: bool = False,
    jawaban: str = "",
    multi_part: bool = False,
    session_baru: bool = False,
    llm_model: str = "",
    llm_provider: str = "",
    llm_time_ms: int = 0,
    error: str = "",
):
    """Catat satu request lengkap — non-blocking (ditulis di background thread)."""
    _ensure_sqlite()

    entry = {
        "waktu": _wib_now(),
        "chat_id": str(chat_id),
        "pertanyaan": pertanyaan,
        "source": source,
        "clf_domain": clf_domain,
        "clf_confidence": round(clf_confidence, 4),
        "clf_mode": clf_mode,
        "rrf_score": round(rrf_score, 4),
        "e5_top": round(e5_top, 4),
        "bm25_raw": round(bm25_raw, 2),
        "top5_faq": top5_faq or [],
        "gate": gate,
        "gate_detail": gate_detail,
        "dijawab": dijawab,
        "jawaban": jawaban,
        "jawaban_length": len(jawaban),
        "llm_model": llm_model,
        "llm_provider": llm_provider,
        "llm_time_ms": llm_time_ms,
        "multi_part": multi_part,
        "session_baru": session_baru,
        "error": error[:200],
    }

    # ── Fire-and-forget: tulis JSONL + SQLite di background ──
    def _write():
        # JSONL
        try:
            if JSONL_FILE.exists() and JSONL_FILE.stat().st_size > _MAX_JSONL_SIZE_KB * 1024:
                _rotate_jsonl()
            with open(JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[LOG] JSONL error: {e}")

        # SQLite
        try:
            with _sqlite_lock:
                db = sqlite3.connect(str(SQLITE_FILE))
                db.execute("""
                    INSERT INTO logs (
                        waktu, chat_id, pertanyaan,
                        clf_domain, clf_confidence, clf_mode,
                        rrf_score, e5_top, bm25_raw, top5_faq,
                        source, gate, gate_detail, dijawab,
                        jawaban, jawaban_length,
                        llm_model, llm_provider, llm_time_ms,
                        multi_part, session_baru, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry["waktu"], entry["chat_id"], entry["pertanyaan"],
                    clf_domain, clf_confidence, clf_mode,
                    rrf_score, e5_top, bm25_raw, json.dumps(top5_faq or []),
                    source, gate, gate_detail, int(dijawab),
                    jawaban, len(jawaban),
                    llm_model, llm_provider, llm_time_ms,
                    int(multi_part), int(session_baru), error[:200],
                ))
                db.commit()
                db.close()
        except Exception as e:
            print(f"[LOG] SQLite error: {e}")

    threading.Thread(target=_write, daemon=True).start()


def _rotate_jsonl():
    """Rotasi JSONL — rename + buat baru"""
    if JSONL_FILE.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = JSONL_FILE.with_name(f"query_log_{ts}.jsonl")
        try:
            JSONL_FILE.rename(backup)
            print(f"[LOG] Rotasi: {JSONL_FILE.name} → {backup.name}")
        except Exception:
            pass


def get_stats(days: int = 7) -> dict:
    """Statistik dari SQLite (7 hari terakhir default)"""
    try:
        db = sqlite3.connect(str(SQLITE_FILE))
        cutoff = (datetime.now(timezone(timedelta(hours=7)))
                  .replace(hour=0, minute=0, second=0, microsecond=0))
        from datetime import timedelta as td
        cutoff = (cutoff - td(days=days - 1)).strftime("%Y-%m-%d")

        total = db.execute("SELECT COUNT(*) FROM logs WHERE waktu >= ?", (cutoff,)).fetchone()[0]
        by_gate = {}
        for row in db.execute("SELECT gate, COUNT(*) FROM logs WHERE waktu >= ? GROUP BY gate", (cutoff,)):
            by_gate[row[0]] = row[1]
        by_clf = {}
        for row in db.execute("SELECT clf_domain, COUNT(*) FROM logs WHERE waktu >= ? GROUP BY clf_domain", (cutoff,)):
            by_clf[row[0]] = row[1]
        avg_rrf = db.execute("SELECT AVG(rrf_score) FROM logs WHERE waktu >= ?", (cutoff,)).fetchone()[0]
        unique_users = db.execute("SELECT COUNT(DISTINCT chat_id) FROM logs WHERE waktu >= ?", (cutoff,)).fetchone()[0]
        db.close()

        return {
            "period": f"{days} hari",
            "total_logs": total,
            "unique_users": unique_users,
            "avg_rrf_score": round(avg_rrf, 4) if avg_rrf else 0,
            "by_gate": by_gate,
            "by_clf": by_clf,
            "jsonl_size_kb": round(JSONL_FILE.stat().st_size / 1024, 1) if JSONL_FILE.exists() else 0,
            "sqlite_size_kb": round(SQLITE_FILE.stat().st_size / 1024, 1) if SQLITE_FILE.exists() else 0,
        }
    except Exception as e:
        return {"error": str(e)}
