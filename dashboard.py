"""
dashboard.py — NARA Dashboard Server
Serves dashboard UI + REST API membaca dari query_log.db
Jalankan paralel dengan server.py: python dashboard.py
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

DB = Path(__file__).parent / "query_log.db"
TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"

app = FastAPI(title="NARA Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WIB = timezone(timedelta(hours=7))


def _cn():
    return sqlite3.connect(str(DB))


def _period_clause(days: int) -> str:
    if days >= 9999:
        return "1=1"
    cutoff = datetime.now(WIB).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    return f"waktu >= '{cutoff.strftime('%Y-%m-%d')}'"


def _table_exists() -> bool:
    try:
        _cn().execute("SELECT 1 FROM logs LIMIT 1")
        return True
    except Exception:
        return False


def _rows(sql: str, params=()):
    db = _cn()
    rows = db.execute(sql, params).fetchall()
    cols = [d[0] for d in db.description]
    db.close()
    return [dict(zip(cols, r)) for r in rows]


@app.get("/", response_class=HTMLResponse)
def index():
    if not TEMPLATE.exists():
        return HTMLResponse("<h2>Dashboard template not found. Run from project root.</h2>", status_code=500)
    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))


# ── API ──

@app.get("/api/stats")
def api_stats(days: int = 7):
    if not _table_exists():
        return {"total_logs": 0, "unique_users": 0, "avg_rrf": 0, "answered": 0,
                "by_gate": {}, "by_clf": {}}
    clause = _period_clause(days)
    sql = f"""
        SELECT
            COALESCE(COUNT(*), 0) as total,
            COALESCE(COUNT(DISTINCT chat_id), 0) as unique_users,
            COALESCE(AVG(rrf_score), 0.0) as avg_rrf,
            COALESCE(SUM(CASE WHEN dijawab THEN 1 ELSE 0 END), 0) as answered
        FROM logs WHERE {clause}
    """
    row = _rows(sql)[0]
    by_gate = {r["gate"]: r["cnt"] for r in _rows(f"SELECT gate, COUNT(*) as cnt FROM logs WHERE {clause} GROUP BY gate ORDER BY cnt DESC")}
    by_clf = {r["clf_domain"]: r["cnt"] for r in _rows(f"SELECT clf_domain, COUNT(*) as cnt FROM logs WHERE {clause} AND clf_domain != '' GROUP BY clf_domain ORDER BY cnt DESC")}
    return {**row, "by_gate": by_gate, "by_clf": by_clf}


@app.get("/api/logs")
def api_logs(days: int = 7, limit: int = 100, offset: int = 0):
    if not _table_exists():
        return {"logs": [], "total": 0}
    clause = _period_clause(days)
    logs = _rows(f"""
        SELECT id, waktu, chat_id, pertanyaan, clf_domain, clf_confidence,
               rrf_score, gate, gate_detail, dijawab, llm_model, llm_time_ms
        FROM logs WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    # Sanitize None values
    for l in logs:
        for k in l:
            if l[k] is None:
                l[k] = 0 if k in ("rrf_score", "clf_confidence", "llm_time_ms") else ""
    total = _rows(f"SELECT COALESCE(COUNT(*), 0) as cnt FROM logs WHERE {clause}")[0]["cnt"]
    return {"logs": logs, "total": total}


@app.get("/api/logs-tail")
def api_logs_tail(days: int = 7, after: int = 0, limit: int = 50):
    if not _table_exists():
        return {"logs": []}
    clause = _period_clause(days)
    logs = _rows(f"""
        SELECT id, waktu, chat_id, pertanyaan, clf_domain, gate
        FROM logs WHERE {clause} AND id > ? ORDER BY id ASC LIMIT ?
    """, (after, limit))
    return {"logs": logs}


@app.get("/api/analytics")
def api_analytics(days: int = 7):
    if not _table_exists():
        return {"trend": [], "hourly": [], "llm_usage": {}}
    clause = _period_clause(days)

    trend = _rows(f"""
        SELECT SUBSTR(waktu,1,13) as h,
               COALESCE(AVG(rrf_score), 0.0) as v
        FROM logs WHERE {clause} AND rrf_score > 0
        GROUP BY h ORDER BY h
    """)
    trend = [{"h": r["h"][-2:]+":00", "v": round(r["v"], 4)} for r in trend]

    hourly = _rows(f"""
        SELECT SUBSTR(waktu,12,2) as h, COUNT(*) as v
        FROM logs WHERE {clause} GROUP BY h ORDER BY h
    """)
    hourly = [{"h": r["h"]+":00", "v": r["v"]} for r in hourly]

    llm_usage = {r["llm_model"] or "unknown": r["cnt"] for r in _rows(f"SELECT COALESCE(llm_model,'unknown') as llm_model, COUNT(*) as cnt FROM logs WHERE {clause} AND llm_model != '' GROUP BY llm_model")}

    return {"trend": trend, "hourly": hourly, "llm_usage": llm_usage}


@app.get("/api/top-faq")
def api_top_faq(days: int = 7, limit: int = 20):
    if not _table_exists():
        return {"faqs": []}
    clause = _period_clause(days)
    faqs = _rows(f"""
        SELECT faq, COUNT(*) as hits,
               COALESCE(AVG(rrf_score), 0.0) as avg_rrf,
               MAX(waktu) as last
        FROM (
            SELECT json_each.value as faq, rrf_score, waktu
            FROM logs, json_each(logs.top5_faq)
            WHERE {clause} AND top5_faq != '[]' AND top5_faq != ''
        )
        GROUP BY faq ORDER BY hits DESC LIMIT ?
    """, (limit,))
    for r in faqs:
        r["avg_rrf"] = round(r["avg_rrf"], 4) if r["avg_rrf"] else 0
    return {"faqs": faqs}


if __name__ == "__main__":
    print("[DASHBOARD] NARA Dashboard")
    print("[DASHBOARD] http://localhost:8001")
    print(f"[DASHBOARD] Database: {DB} {'✅' if DB.exists() else '(belum ada — akan dibuat otomatis)'}")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
