"""
database.py — Daily chat limit tracking di query_log.db
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / "query_log.db"

def _cn():
    return sqlite3.connect(str(DB))

def init_db():
    """Init table buat daily limit tracking"""
    with _cn() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS daily_limits (
                chat_id TEXT NOT NULL,
                tanggal TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, tanggal)
            )
        """)
        db.commit()
    print(f"[DB] Daily limit tracker ready")

def get_daily_count(chat_id: str, tanggal: str) -> int:
    try:
        row = _cn().execute(
            "SELECT count FROM daily_limits WHERE chat_id=? AND tanggal=?",
            (chat_id, tanggal)).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0

def increment_daily_count(chat_id: str, tanggal: str):
    try:
        with _cn() as db:
            db.execute(
                "INSERT INTO daily_limits(chat_id,tanggal,count) VALUES(?,?,1) "
                "ON CONFLICT(chat_id,tanggal) DO UPDATE SET count=count+1",
                (chat_id, tanggal))
            db.commit()
    except Exception:
        pass
