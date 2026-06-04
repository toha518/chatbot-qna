"""
dashboard.py — NARA Dashboard Server
Serves dashboard UI + REST API membaca dari query_log.db
Jalankan paralel dengan server.py: python dashboard.py
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import asyncio
import subprocess
import sys
import os
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

DB = Path(__file__).parent / "query_log.db"
TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"
FAVICON = Path(__file__).parent / "templates" / "favicon.svg"
VERSION_FILE = Path(__file__).parent / "VERSION"

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
    cur = db.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    db.close()
    return [dict(zip(cols, r)) for r in rows]


@app.get("/api/version")
def get_version():
    """Return NARA version from git tag (auto). Fallback: VERSION file."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=2,
            cwd=str(Path(__file__).parent)
        )
        if result.returncode == 0 and result.stdout.strip():
            ver = result.stdout.strip()
        else:
            raise Exception("git describe failed")
    except Exception:
        # Fallback: baca VERSION file (kalo clone via ZIP, gak ada .git)
        if VERSION_FILE.exists():
            ver = VERSION_FILE.read_text(encoding="utf-8").strip()
        else:
            ver = "dev"
    return {"version": ver}


@app.get("/", response_class=HTMLResponse)
def index():
    if not TEMPLATE.exists():
        return HTMLResponse("<h2>Dashboard template not found. Run from project root.</h2>", status_code=500)
    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))


@app.get("/favicon.svg")
async def favicon():
    if FAVICON.exists():
        return FileResponse(str(FAVICON), media_type="image/svg+xml")
    return HTMLResponse("", status_code=404)


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
    by_feedback = {r["feedback_status"]: r["cnt"] for r in _rows(f"SELECT feedback_status, COUNT(*) as cnt FROM logs WHERE {clause} AND feedback_status != '' GROUP BY feedback_status ORDER BY cnt DESC")}
    return {**row, "by_gate": by_gate, "by_clf": by_clf, "by_feedback": by_feedback}


@app.get("/api/logs")
def api_logs(days: int = 7, limit: int = 100, offset: int = 0,
             search: str = "", gate: str = "", clf: str = "", source: str = "", dijawab: str = "", feedback: str = ""):
    if not _table_exists():
        return {"logs": [], "total": 0}
    clause = _period_clause(days)
    params = []

    if search:
        clause += " AND (pertanyaan LIKE ? OR chat_id LIKE ? OR jawaban LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    if gate:
        clause += " AND gate = ?"
        params.append(gate)
    if clf:
        clause += " AND clf_domain = ?"
        params.append(clf)
    if source:
        clause += " AND source = ?"
        params.append(source)
    if dijawab == "1":
        clause += " AND dijawab = 1"
    elif dijawab == "0":
        clause += " AND dijawab = 0"
    if feedback:
        clause += " AND feedback_status = ?"
        params.append(feedback)

    try:
        logs = _rows(f"""
            SELECT * FROM logs WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?
        """, params + [limit, offset])
    except Exception as e:
        import traceback
        print(f"[LOGS-ERROR] Query failed: {e}")
        traceback.print_exc()
        return {"logs": [], "total": 0, "error": str(e)}
    # Sanitize values — convert None & strings to proper types
    NUMERIC_COLS = {"rrf_score", "clf_confidence", "llm_time_ms", "e5_top", "bm25_raw", "bm25_gate", "jawaban_length"}
    INT_COLS = {"dijawab", "multi_part", "session_baru"}
    for l in logs:
        for k in list(l.keys()):
            v = l[k]
            if v is None:
                l[k] = 0 if k in NUMERIC_COLS | INT_COLS else ""
            elif k in NUMERIC_COLS and isinstance(v, str):
                try:
                    l[k] = float(v)
                except ValueError:
                    l[k] = 0
            elif k in INT_COLS and not isinstance(v, int):
                try:
                    l[k] = int(v)
                except (ValueError, TypeError):
                    l[k] = 0
    try:
        total = _rows(f"SELECT COALESCE(COUNT(*), 0) as cnt FROM logs WHERE {clause}", params)[0]["cnt"]
    except Exception as e:
        import traceback
        print(f"[LOGS-ERROR] {e}")
        traceback.print_exc()
        return {"logs": logs, "total": 0, "error": str(e), "sql": f"SELECT COUNT(*) FROM logs WHERE {clause}"}
    return {"logs": logs, "total": total}


@app.get("/api/logs-dt")
def api_logs_datatable(days: int = 7, draw: int = 1, start: int = 0, length: int = 50,
                       search: str = "", gate: str = "", clf: str = "", source: str = "", dijawab: str = "", feedback: str = ""):
    """Server-side DataTables endpoint. Returns {draw, recordsTotal, recordsFiltered, data}."""
    if not _table_exists():
        return {"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": []}

    where = _period_clause(days)
    params = []

    if search:
        where += " AND (pertanyaan LIKE ? OR chat_id LIKE ? OR jawaban LIKE ? OR clf_domain LIKE ? OR gate LIKE ? OR source LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s])
    if gate:
        where += " AND gate = ?"
        params.append(gate)
    if clf:
        where += " AND clf_domain = ?"
        params.append(clf)
    if source:
        where += " AND source = ?"
        params.append(source)
    if dijawab == "1":
        where += " AND dijawab = 1"
    elif dijawab == "0":
        where += " AND dijawab = 0"
    if feedback:
        where += " AND feedback_status = ?"
        params.append(feedback)

    # Records total & filtered
    total_all = _rows("SELECT COALESCE(COUNT(*),0) as cnt FROM logs", [])[0]["cnt"]
    total_filtered = _rows(f"SELECT COALESCE(COUNT(*),0) as cnt FROM logs WHERE {where}", params)[0]["cnt"]

    # Data
    rows = _rows(f"SELECT * FROM logs WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", params + [length, start])

    # Sanitize
    NUMERIC_COLS = {"rrf_score", "clf_confidence", "llm_time_ms", "e5_top", "bm25_raw", "bm25_gate", "jawaban_length"}
    INT_COLS = {"dijawab", "multi_part", "session_baru"}
    for row in rows:
        for k in list(row.keys()):
            v = row[k]
            if v is None:
                row[k] = 0 if k in NUMERIC_COLS | INT_COLS else ""
            elif k in NUMERIC_COLS and isinstance(v, str):
                try:
                    row[k] = float(v)
                except ValueError:
                    row[k] = 0
            elif k in INT_COLS and not isinstance(v, int):
                try:
                    row[k] = int(v)
                except (ValueError, TypeError):
                    row[k] = 0

    return {"draw": draw, "recordsTotal": total_all, "recordsFiltered": total_filtered, "data": rows}


@app.get("/api/logs-export")
def api_logs_export(days: int = 7, format: str = "csv",
                    search: str = "", gate: str = "", clf: str = "", source: str = "", dijawab: str = "", feedback: str = ""):
    """Export filtered logs as CSV/Excel/PDF. Returns all matching rows (no pagination)."""
    if not _table_exists():
        return HTMLResponse("No data", status_code=404)

    where = _period_clause(days)
    params = []

    if search:
        where += " AND (pertanyaan LIKE ? OR chat_id LIKE ? OR jawaban LIKE ? OR clf_domain LIKE ? OR gate LIKE ? OR source LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s])
    if gate:
        where += " AND gate = ?"
        params.append(gate)
    if clf:
        where += " AND clf_domain = ?"
        params.append(clf)
    if source:
        where += " AND source = ?"
        params.append(source)
    if dijawab == "1":
        where += " AND dijawab = 1"
    elif dijawab == "0":
        where += " AND dijawab = 0"
    if feedback:
        where += " AND feedback_status = ?"
        params.append(feedback)

    rows = _rows(f"SELECT * FROM logs WHERE {where} ORDER BY id DESC LIMIT 10000", params)

    if not rows:
        return HTMLResponse("<h3>No data to export</h3>")

    cols = list(rows[0].keys())

    # ── CSV ──
    if format == "csv":
        import csv, io
        buf = io.StringIO()
        buf.write('\ufeff')
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
        writer.writerow(cols)
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c, "")
                if v is None: v = ""
                elif isinstance(v, str): v = v.replace('\r\n',' ').replace('\n',' ').replace('\r',' ')
                vals.append(v)
            writer.writerow(vals)
        content = buf.getvalue(); buf.close()
        ts = datetime.now(WIB).strftime('%Y%m%d_%H%M')
        resp = Response(content, media_type="text/csv; charset=utf-8-sig")
        resp.headers["Content-Disposition"] = f"attachment; filename=nara_logs_{ts}.csv"
        return resp

    # ── HTML (print view for PDF) ──
    if format == "html":
        h = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>NARA Query Log</title>']
        h += ['<style>body{font:12px/1.4 system-ui,sans-serif;margin:20px}h2{font-size:16px;margin-bottom:12px;color:#0070d1}']
        h += ['table{border-collapse:collapse;width:100%;font-size:10px}th,td{border:1px solid #ccc;padding:5px 7px;text-align:left}']
        h += ['th{background:#f0f4f8;font-weight:600}tr:nth-child(even){background:#f8fafc}']
        h += ['@media print{@page{size:landscape;margin:10mm}body{margin:0}}</style></head><body>']
        h += [f'<h2>📝 NARA Query Log — {len(rows)} baris</h2><table><thead><tr>']
        h += [f'<th>{c}</th>' for c in cols]
        h += ['</tr></thead><tbody>']
        for r in rows:
            h.append('<tr>')
            for c in cols:
                v = r.get(c,""); v = str(v) if v is not None else ""
                if len(v) > 300: v = v[:300] + '...'
                v = v.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                h.append(f'<td>{v}</td>')
            h.append('</tr>')
        h += ['</tbody></table>']
        h += ['<script>window.addEventListener("DOMContentLoaded",()=>{setTimeout(window.print,500)})</script>']
        h += ['</body></html>']
        return HTMLResponse(''.join(h))

    # ── HTML-table (for Excel) ──
    if format == "html-table":
        h = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>NARA Logs</title></head><body>']
        h += ['<table><thead><tr>']
        h += [f'<th>{c}</th>' for c in cols]
        h += ['</tr></thead><tbody>']
        for r in rows:
            h.append('<tr>')
            for c in cols:
                v = r.get(c,""); v = str(v) if v is not None else ""
                v = v.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                h.append(f'<td>{v}</td>')
            h.append('</tr>')
        h += ['</tbody></table></body></html>']
        return HTMLResponse(''.join(h))

    return HTMLResponse(f"Unknown format: {format}", status_code=400)

    return HTMLResponse(f"Unknown format: {format}", status_code=400)


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


# ── System Health ──

SERVICES = {
    "server": {"name": "Server API", "url": "http://localhost:8000/health", "port": 8000},
    "wa_handler": {"name": "WA Handler", "url": "http://localhost:3001/health", "port": 3001},
    "bridge": {"name": "WA Bridge", "url": "http://localhost:3000/status", "port": 3000},
    "telegram": {"name": "Telegram Bot", "url": "http://localhost:3002/", "port": 3002},
}


@app.get("/api/system")
async def api_system():
    results = {}
    all_ok = True
    for key, svc in SERVICES.items():
        if not svc["url"]:
            # Telegram bot — gak punya HTTP endpoint, cek proses via port aja
            results[key] = {"name": svc["name"], "status": "unknown", "detail": "No HTTP endpoint — running as process"}
            continue
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(svc["url"])
            if resp.status_code == 200:
                results[key] = {"name": svc["name"], "status": "ok", "detail": f":{svc['port']} ✅"}
            else:
                results[key] = {"name": svc["name"], "status": "error", "detail": f"HTTP {resp.status_code}"}
                all_ok = False
        except httpx.RequestError as e:
            results[key] = {"name": svc["name"], "status": "down", "detail": str(e)}
            all_ok = False
    return {"services": results, "overall": "ok" if all_ok else "degraded"}


@app.get("/api/system/check")
async def api_system_check():
    """Quick ping — just returns overall status, lightweight."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            tasks = [client.get(svc["url"]) for svc in SERVICES.values() if svc["url"]]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            ok = sum(1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200)
    except Exception:
        ok = 0
    return {"total": len([s for s in SERVICES.values() if s["url"]]), "healthy": ok}


# ── Service Control (Windows) ──

SERVICE_PROCESSES = {
    8000: "Server API (server.py)",
    3000: "WA Bridge (bridge.js)",
    3001: "WA Handler (wa_handler.py)",
    3002: "Telegram Bot (telegram_bot.py)",
}


def _is_windows():
    return sys.platform == "win32"


def _find_pids_by_port(port: int) -> list[int]:
    """Cari PID yang nge-listen di port tertentu (Windows)."""
    if not _is_windows():
        return []
    pids = []
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{port} "',
            shell=True, stderr=subprocess.DEVNULL, timeout=10
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                pid = parts[-1]
                if pid.isdigit():
                    pids.append(int(pid))
    except Exception:
        pass
    return list(set(pids))


def _find_pids_by_name(names: list[str]) -> list[int]:
    """Cari PID berdasarkan window title (Windows)."""
    if not _is_windows():
        return []
    pids = []
    for name in names:
        try:
            out = subprocess.check_output(
                f'tasklist /FI "WINDOWTITLE eq {name}*" /FO CSV /NH',
                shell=True, stderr=subprocess.DEVNULL, timeout=10
            ).decode("utf-8", errors="ignore")
            for line in out.splitlines():
                parts = [p.strip().strip('"') for p in line.split(",")]
                if len(parts) >= 2 and parts[1].isdigit():
                    pids.append(int(parts[1]))
        except Exception:
            pass
    return list(set(pids))


@app.post("/api/system/stop-all")
async def api_stop_all():
    """Stop semua service Nara."""
    if not _is_windows():
        return {"status": "error", "message": "Hanya bisa di Windows"}
    killed = []
    errors = []

    # Stop via port
    for port, label in SERVICE_PROCESSES.items():
        pids = _find_pids_by_port(port)
        for pid in pids:
            try:
                subprocess.run(f"taskkill /PID {pid} /F", shell=True,
                               capture_output=True, timeout=5)
                killed.append(f"{label} (PID {pid}, port {port})")
            except Exception as e:
                errors.append(f"{label} (PID {pid}): {e}")

    # Stop via window title
    window_pids = _find_pids_by_name(["SERVER", "WA_HANDLER", "BRIDGE", "TELEGRAM"])
    for pid in window_pids:
        if pid not in [int(p.split("PID ")[1].split(")")[0]) for p in killed if "PID" in p]:
            try:
                subprocess.run(f"taskkill /PID {pid} /F", shell=True,
                               capture_output=True, timeout=5)
                killed.append(f"Window process (PID {pid})")
            except Exception as e:
                errors.append(f"Window PID {pid}: {e}")

    return {
        "status": "ok",
        "killed": killed,
        "errors": errors,
        "message": f"{len(killed)} service(s) stopped{' with ' + str(len(errors)) + ' error(s)' if errors else ''}"
    }


@app.post("/api/system/start-all")
async def api_start_all():
    """Start semua service Nara via start-all.bat."""
    bat_path = Path(__file__).parent / "start-all.bat"
    if not bat_path.exists():
        return {"status": "error", "message": f"start-all.bat tidak ditemukan di {bat_path}"}
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", str(bat_path)],
            cwd=str(bat_path.parent),
            shell=True
        )
        return {"status": "ok", "message": "start-all.bat dijalankan — 4 terminal akan terbuka"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Load FAQ → category mapping dari faq_categories.json
_FAQ_CATEGORIES = {}
def _load_faq_categories():
    global _FAQ_CATEGORIES
    fp = Path(__file__).parent / "faq_categories.json"
    if fp.exists():
        try:
            import json
            _FAQ_CATEGORIES = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            _FAQ_CATEGORIES = {}
    else:
        _FAQ_CATEGORIES = {}

_load_faq_categories()


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
        # Cari kategori dari spreadsheet FAQ (SOBAT, dll)
        r["category"] = _FAQ_CATEGORIES.get(r["faq"], "-")
    return {"faqs": faqs}


if __name__ == "__main__":
    print("[DASHBOARD] NARA Dashboard")
    print("[DASHBOARD] http://localhost:8001")
    print(f"[DASHBOARD] Database: {DB} {'✅' if DB.exists() else '(belum ada — akan dibuat otomatis)'}")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
