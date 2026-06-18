"""
kbli_handler.py — KBLI lookup handler for Nara
Pipeline: keyword detect → clean query → kbli.co.id API → LLM context
"""

import json
import logging
import re
import httpx
from typing import Optional

KBLI_API_URL = "https://kbli.co.id/api/search?q={query}"

# Kata/frasa yang perlu di-strip dari query sebelum dikirim ke API
CLEAN_WORDS = [
    "kbli", "kbl", "kode", "usaha", "bisnis", "lapangan", "klasifikasi",
    "masuk", "cari", "apa", "untuk", "yang", "saya", "punya", "buka",
    "mau", "tanya", "mau tanya", "kalau", "kalo", "saya mau", "aku mau",
    "tolong", "kak", "bang", "mas", "kak nara", "bang nara", "mas nara",
    "nara", "nara tolong", "gimana", "bagaimana", "caranya", "cara",
    "buat", "sama", "sih", "ya", "yah", "dong", "deh", "nih", "tuh",
    "bisa", "mohon", "please", "dengan", "dan", "atau", "di", "ke",
    "dari", "seperti", "tolong cari", "tolong carikan",
]

# Regex patterns untuk deteksi query KBLI
KBLI_PATTERNS = [
    r'\bkbli\b',
    r'\b(kbli\s*)?\d{5}\b',  # 5-digit KBLI code with optional kbli prefix
]

# Sektor-level KBLI
logger = logging.getLogger(__name__)


def is_kbli_query(text: str) -> bool:
    """Deteksi apakah query berkaitan dengan KBLI (hanya keyword explicit)"""
    if not text:
        return False
    text_lower = text.lower().strip()
    for pat in KBLI_PATTERNS:
        if re.search(pat, text_lower):
            return True
    return False


def extract_kbli_code(text: str) -> Optional[str]:
    """Extract 5-digit KBLI code from text"""
    match = re.search(r'\b(\d{5})\b', text)
    return match.group(1) if match else None


def clean_kbli_query(text: str) -> str:
    """Strip kata/frasa noise dari query, sisakan deskripsi usaha bersih"""
    clean = text.lower().strip()
    # Sort longest first to match multi-word phrases
    sorted_words = sorted(CLEAN_WORDS, key=len, reverse=True)
    for word in sorted_words:
        # Replace whole word/phrase
        clean = re.sub(r'\b' + re.escape(word) + r'\b', ' ', clean)
    # Clean up: multiple spaces, leading/trailing whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Remove 5-digit KBLI codes (keep the rest)
    clean = re.sub(r'\b\d{5}\b', '', clean).strip()
    return clean


async def search_kbli_api(query: str) -> list[dict]:
    """Cari KBLI via kbli.co.id API — return raw top 5 results"""
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = KBLI_API_URL.format(query=query)
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"[KBLI API] HTTP {resp.status_code}")
                return []
            data = resp.json()
            results = data.get("results", [])
            
            # Filter: class-level (5 digit) + top 5
            formatted = []
            for r in results:
                if len(formatted) >= 5:
                    break
                if r.get("level") == 5:
                    formatted.append({
                        "kode": r.get("code", ""),
                        "judul": (r.get("nameId", "") or r.get("nameEn", "")).strip(),
                        "deskripsi_en": r.get("description", "").strip(),
                        "skor": r.get("_semanticSimilarity", 0),
                    })
            return formatted
    except Exception as e:
        logger.error(f"[KBLI API] Error: {e}")
        return []


def format_kbli_context(results: list[dict]) -> str:
    """Format hasil API jadi context string untuk LLM prompt — termasuk kategori sektor"""
    if not results:
        return "Tidak ada data KBLI yang cocok."
    
    from core.kbli_sectors import get_sector_label
    
    lines = []
    for i, r in enumerate(results, 1):
        sektor = get_sector_label(r['kode'])
        lines.append(f"[Opsi {i}]")
        lines.append(f"Kode: {r['kode']}")
        lines.append(f"Nama: {r['judul']}")
        if sektor:
            lines.append(f"Kategori: {sektor}")
        if r.get("deskripsi_en"):
            lines.append(f"Deskripsi: {r['deskripsi_en']}")
        lines.append("")
    
    return "\n".join(lines)


def format_sectors() -> str:
    """Return daftar sektor KBLI"""
    from core.kbli_sectors import SECTOR_RANGES
    lines = ["📂 **Kategori KBLI 2025 (A–V):**\n"]
    for start, end, kat, nama in SECTOR_RANGES:
        r = str(start) if start == end else f"{start}–{end}"
        lines.append(f"• **{kat}** ({r:>5s}) — {nama}")
    return "\n".join(lines)
