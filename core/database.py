# core/database.py — SQLite: init, log history, query

import sqlite3
import os
import time
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cici_anova.db")


def init_db():
    """Bikin tabel kalau belum ada"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            waktu TIMESTAMP NOT NULL,
            kendala TEXT NOT NULL,
            solusi TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_id ON chat_logs(chat_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waktu ON chat_logs(waktu)")
    conn.commit()
    conn.close()
    print(f"[DB] SQLite ready: {DB_PATH}")


def log_chat(chat_id: str, pertanyaan: str, jawaban: str):
    """Simpan chat ke SQLite"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_logs (chat_id, waktu, kendala, solusi) VALUES (?, ?, ?, ?)",
            (chat_id, time.time(), pertanyaan, jawaban)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] Gagal log chat: {e}")


def get_chat_history(chat_id: str):
    """Ambil history chat per user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT waktu, kendala, solusi FROM chat_logs WHERE chat_id = ? ORDER BY waktu ASC",
            (chat_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB] Gagal ambil history: {e}")
        return []


def list_sessions():
    """Daftar semua chat_id yang punya history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chat_id, COUNT(*) as total, MIN(waktu) as pertama
            FROM chat_logs
            GROUP BY chat_id
            ORDER BY pertama DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB] Gagal list sessions: {e}")
        return []
