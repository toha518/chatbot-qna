# KBLI Lookup — Implementation Guide

> **Nara Chatbot** — Fitur pencarian KBLI (Klasifikasi Baku Lapangan Usaha Indonesia)
> Versi: v2.16.0 | Diperkenalkan: v2.15.0 | API: kbli.co.id

---

## Daftar Isi

1. [Overview](#overview)
2. [Algoritma — Cara Kerja KBLI](#algoritma--cara-kerja-kbli)
3. [Chat Flow — Diagram Alur](#chat-flow--diagram-alur)
4. [Trigger & Deteksi](#trigger--deteksi)
5. [API Integration](#api-integration)
6. [Prompt System](#prompt-system)
7. [Konfigurasi](#konfigurasi)
8. [File Structure](#file-structure)
9. [Common Mistakes & Known Issues](#common-mistakes--known-issues)
10. [Changelog](#changelog)

---

## Overview

Fitur KBLI Lookup memungkinkan Nara mencari dan merekomendasikan kode KBLI yang sesuai dengan deskripsi usaha user. Menggunakan pendekatan **multi-query expansion + concurrent API + LLM re-ranking** untuk menghasilkan hasil yang akurat dan kontekstual.

**Sumber data:** [kbli.co.id](https://kbli.co.id) — direktori KBLI Indonesia 2020 & 2025.

**Trigger:** Cukup sebut kata "kbli" di pertanyaan user (case insensitive).

---

## Algoritma — Cara Kerja KBLI

### Tahap 1: Deteksi & Pembersihan (Detection & Cleaning)

```
Input: "kbli jualan baju online di shopee"
       ↓
is_kbli_query() → regex \bkbli\b → true
       ↓
clean_kbli_query() → strip noise words:
  • Stopwords: kbli, kbl, kode, usaha, bisnis, lapangan, klasifikasi
  • Filler: masuk, cari, apa, untuk, yang, saya, punya, buka
  • Panggilan: kak, bang, mas, nara, kak nara
  • Partikel: sih, ya, yah, dong, deh, nih, tuh
  • KBLI codes 5-digit (kalo ada)
       ↓
Output bersih: "jual baju online shopee"
```

### Tahap 2: Query Expansion (LLM)

LLM (**DeepSeek V4 Flash**) generate **3 varian query** dari deskripsi bersih untuk mencakup spektrum interpretasi yang berbeda.

**Prompt:** `prompts/kbli_expand.md`

| Parameter | Deskripsi |
|-----------|-----------|
| Produk/Jasa | Apa yang dihasilkan? |
| Skala | Kecil/menengah/besar |
| Cara jual | Toko fisik/online/grosir/eceran/jasa |
| Metode produksi | Manual/pabrik/home industry |
| Bahan baku | Apa yang diproses? |

**Contoh:**

```
Input:  "jual baju online shopee"
Output: [
  "perdagangan eceran pakaian online",
  "industri konveksi pakaian jadi",
  "perdagangan besar tekstil pakaian"
]
```

Tiap varian query **genuinely berbeda sudut pandang** — bukan cuma sinonim dari kata yang sama.

### Tahap 3: Concurrent API Calls

3 varian query dikirim **bersamaan** ke kbli.co.id API via `asyncio.gather()`:

```
API: GET https://kbli.co.id/api/search?q={query}
     ↓
Response: JSON { results: [{ code, nameId, description, level, _semanticSimilarity }] }
     ↓
Filter: hanya level=5 (class-level, 5-digit KBLI)
Ambil: top 5 per query
     ↓
Total raw: 3 × 5 = 15 hasil
```

**Karakteristik API:**
- **Public** — no auth key required
- **Semantic search built-in** — ada field `_semanticSimilarity` (0.0–1.0)
- **Timeout:** 8 detik per request
- **Concurrent:** total latency ≈ 1 call terlama (bukan 3×)

### Tahap 4: Pooling & Deduplikasi

```
Pool: 15 hasil dari 3 query
       ↓
pool_and_dedup():
  • Top 2 per query (hasil dengan skor tertinggi untuk tiap varian)
  • Dedup by kode KBLI (5-digit) — kode yang sama cuma sekali
  • Urutan dipertahankan per interpretasi
       ↓
Output: max 6 KBLI unik (3 interpretasi × 2 hasil)
```

### Tahap 5: LLM Re-rank & Format

LLM (**DeepSeek V4 Flash**) menerima context dari hasil pooling, lalu:
1. **Grouping** — hasil dikelompokkan per interpretasi (3 grup)
2. **Re-ranking** — urutan dalam tiap grup berdasarkan relevansi ke deskripsi user asli
3. **Format output** — struktur rapi dengan kategori, kode, deskripsi, dan penjelasan

**Prompt:** `prompts/kbli.md` (v2 — updated)

**Format output:**

```
Berikut beberapa opsi KBLI yang sesuai dengan usaha "jual baju online di shopee":

🔹 Sebagai perdagangan eceran pakaian (sesuai deskripsi)
**Kategori: G — Perdagangan Besar dan Eceran**
**KBLI 47711 — Perdagangan Eceran Pakaian**
Mencakup usaha eceran khusus pakaian dari tekstil, kulit, atau kulit sintetis.
→ **Cocok untuk:** Usaha jual baju online yang membeli dari supplier dan menjual kembali ke konsumen akhir.

🔹 Sebagai perdagangan eceran melalui media daring
**Kategori: G — Perdagangan Besar dan Eceran**
**KBLI 47912 — Perdagangan Eceran Melalui Media Daring (Online)**
Mencakup perdagangan eceran melalui internet (e-commerce).
→ **Cocok untuk:** Usaha jual baju melalui platform online seperti Shopee.

⚠️ Sumber data: kbli.co.id — Harap dipastikan kembali kebenarannya, ya!
```

### Ringkasan Resource

| Tahap | Resource | Waktu |
|-------|----------|-------|
| Deteksi & Clean | Regex (CPU) | ~1ms |
| Query Expansion | 1× LLM call (flash) | ~1-3 detik |
| API Calls | 3× concurrent HTTPX | ~1-3 detik |
| Pooling & Dedup | Python dict (CPU) | ~1ms |
| Re-rank & Format | 1× LLM call (flash) | ~3-5 detik |
| **Total** | **2 LLM + 3 API** | **~5-10 detik** |

---

## Chat Flow — Diagram Alur

```
📩 User chat masuk
  │
  ├─ Source: Telegram / WhatsApp / API
  │
  ├─ [PRE-PROCESS]
  │   ├─ OCR gambar? → EasyOCR → append teks
  │   ├─ Anti-spam check
  │   └─ Daily limit check (50/user/hari)
  │
  ├─ [ROUTING — Priority Order]
  │   │
  │   ├─ KBLI query? (regex \bkbli\b)
  │   │   │
  │   │   └─ ⭐ KBLI PIPELINE ⭐
  │   │       ├─ 1. Clean query → strip noise words
  │   │       ├─ 2. LLM Expand → 3 varian query
  │   │       ├─ 3. 3× Concurrent API kbli.co.id
  │   │       ├─ 4. Pool + Dedup by kode (top 2/query)
  │   │       ├─ 5. LLM Re-rank + Group by interpretasi
  │   │       └─ 6. Format output + disclaimer
  │   │
  │   ├─ Salam/greeting? → LLM langsung
  │   │
  │   ├─ Pertanyaan FAQ?
  │   │   │
  │   │   └─ RETRIEVAL PIPELINE
  │   │       ├─ E5-base encode → 768d vector
  │   │       ├─ Cosine similarity → top-30
  │   │       ├─ BM25 hybrid + RRF
  │   │       ├─ Domain gate check
  │   │       ├─ Multi-part split (kalo perlu)
  │   │       └─ LLM prompt → jawab dari konteks
  │   │
  │   └─ General chat / lainnya? → LLM langsung
  │
  ├─ [POST-PROCESS]
  │   ├─ Log query → SQLite
  │   └─ Update dashboard
  │
  └─ 📩 Kirim jawaban ke user
```

### KBLI Pipeline — Detail

```
  ┌─────────────────────────────────────────────────────────┐
  │  KBLI PIPELINE                                          │
  │                                                         │
  │  Input: "kbli jual baju online"                         │
  │       ↓                                                 │
  │  ┌── 1. CLEAN ──────────────────────────────────────┐   │
  │  │  "jual baju online" ← hapus noise & kata "kbli"  │   │
  │  └──────────────────────────────────────────────────┘   │
  │       ↓                                                 │
  │  ┌── 2. LLM EXPAND ─────────────────────────────────┐   │
  │  │  3 varian:                                       │   │
  │  │  • "perdagangan eceran pakaian"                  │   │
  │  │  • "industri konveksi pakaian"                   │   │
  │  │  • "perdagangan besar tekstil"                   │   │
  │  └──────────────────────────────────────────────────┘   │
  │       ↓                                                 │
  │  ┌── 3. API CALLS ─────────────────────────────────┐   │
  │  │  3× → kbli.co.id/api/search (asyncio.gather)    │   │
  │  │  Masing-masing → top 5 hasil (level=5)          │   │
  │  │  Total raw: ~15 hasil                           │   │
  │  └──────────────────────────────────────────────────┘   │
  │       ↓                                                 │
  │  ┌── 4. POOL + DEDUP ──────────────────────────────┐   │
  │  │  • Top 2 per query                               │   │
  │  │  • Dedup by 5-digit code                         │   │
  │  │  • Max 6 hasil unik                             │   │
  │  └──────────────────────────────────────────────────┘   │
  │       ↓                                                 │
  │  ┌── 5. LLM RE-RANK ───────────────────────────────┐   │
  │  │  • Group by interpretasi (3 grup)                │   │
  │  │  • Re-rank per grup berdasarkan user asli        │   │
  │  │  • Format: Kategori → KBLI → Deskripsi → Cocok  │   │
  │  └──────────────────────────────────────────────────┘   │
  │       ↓                                                 │
  │  Output: Jawaban + "⚠️ Sumber: kbli.co.id"              │
  └─────────────────────────────────────────────────────────┘
```

---

## Trigger & Deteksi

### Regex
```python
KBLI_PATTERNS = [
    r'\bkbli\b',  # hanya trigger kata "kbli" aja (case insensitive)
]
```

### Kata yang Di-strip dari Query (`CLEAN_WORDS`)

| Kategori | Contoh |
|----------|--------|
| Kata KBLI | kbli, kbl, kode, usaha, bisnis, lapangan, klasifikasi |
| Kata Tanya | apa, bagaimana, gimana, caranya, cara |
| Panggilan | kak, bang, mas, nara, kak nara, bang nara, mas nara |
| Partikel | sih, ya, yah, dong, deh, nih, tuh |
| Kata Kerja | mau, buka, punya, cari, tolong, tolong cari, minta |
| Preposisi | di, ke, dari, dengan, dan, atau |

### Contoh Deteksi

| Input | Detected | Clean Query |
|-------|----------|-------------|
| "kbli jualan bakso" | ✅ | "jualan bakso" |
| "KBLI untuk restoran" | ✅ | "restoran" |
| "kode KBLI usaha konveksi" | ✅ | "usaha konveksi" → "konveksi" |
| "apa itu KBLI 56101" | ✅ | "apa" → "" (kosong → fallback kode 56101) |
| "cara daftar NIB" | ❌ | — |

---

## API Integration

### Endpoint
```
https://kbli.co.id/api/search?q={query}
```

### Response Format
```json
{
  "results": [
    {
      "code": "47711",
      "nameEn": "Retail Trade of Clothing",
      "nameId": "Perdagangan Eceran Pakaian",
      "description": "This group includes retail businesses specializing in clothing...",
      "level": 5,
      "table": "classes",
      "_semanticSimilarity": 0.425164
    }
  ]
}
```

### Kode (`core/kbli_handler.py`)

```python
KBLI_API_URL = "https://kbli.co.id/api/search?q={query}"

async def search_kbli_api(query: str) -> list[dict]:
    """Cari KBLI via kbli.co.id API — return raw top 5 results"""
    if not query or len(query.strip()) < 2:
        return []
    try:
        url = KBLI_API_URL.format(query=query)
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
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
```

### Kategori Sektor

KBLI 2025 punya 22 kategori (A–V). Fungsi `get_sector_label()` di `core/kbli_sectors.py` mapping kode 5-digit ke sektor:

| Range Kode | Kategori | Nama |
|------------|----------|------|
| 01111–03202 | A | Pertanian, Kehutanan, dan Perikanan |
| 05100–09900 | B | Pertambangan dan Penggalian |
| 10110–33200 | C | Industri Pengolahan |
| 35101–35302 | D | Pengadaan Listrik, Gas, Uap/Air Panas |
| 36001–39000 | E | Pengadaan Air; Pengelolaan Sampah |
| 41011–43909 | F | Konstruksi |
| 45101–47999 | G | Perdagangan Besar dan Eceran |
| 49111–53201 | H | Pengangkutan dan Pergudangan |
| 55110–56309 | I | Penyediaan Akomodasi dan Makan Minum |
| 58110–63999 | J | Informasi dan Komunikasi |
| 64110–66309 | K | Aktivitas Keuangan dan Asuransi |
| 68110–68329 | L | Real Estat |
| 69101–75009 | M | Aktivitas Profesional, Ilmiah, dan Teknis |
| 77110–80109 | N | Aktivitas Sewa Menyewa dan Penunjang Usaha |
| 84110–84309 | O | Administrasi Pemerintahan |
| 85110–88999 | P | Pendidikan |
| 86101–88999 | Q | Kesehatan dan Aktivitas Sosial |
| 90011–93299 | R | Kesenian, Hiburan, dan Rekreasi |
| 94110–94209 | S | Aktivitas Jasa Lainnya |
| 97000–98200 | T | Jasa Perorangan |
| 99000–99000 | U | Aktivitas Badan Internasional |
| — | V | (Khusus KBLI 2025 — kategori baru) |

---

## Prompt System

### 1. `prompts/kbli_expand.md` — Query Expansion

System prompt untuk generate 3 varian query. Menggunakan parameter:
- Produk/Jasa
- Skala  
- Cara jual
- Metode produksi
- Bahan baku

Output: JSON array of 3 strings.

### 2. `prompts/kbli.md` — Re-rank & Format (v2)

System prompt untuk re-rank hasil + format output grouping per interpretasi.

Aturan:
- Wajib group by interpretasi (3 grup)
- Tiap KBLI: Kategori **bold** → Kode+Nama **bold** → Deskripsi → Cocok untuk
- 100% bahasa Indonesia (terjemahkan deskripsi Inggris)
- **Bold** markdown, bukan HTML
- Akhiri dengan disclaimer: ⚠️ Sumber data: kbli.co.id

### Prompt Files Location
```
chatbot-qna/prompts/
├── kbli.md              # Re-rank & format (v2 — grouping + Cocok untuk)
├── kbli_expand.md       # Query expansion (baru di v2.16.0)
└── KBLI-FLOW-v2.md      # Dokumentasi alur v2 (draft)
```

---

## Konfigurasi

| Parameter | Nilai | File | Keterangan |
|-----------|-------|------|------------|
| `KBLI_API_URL` | `https://kbli.co.id/api/search?q={query}` | `core/kbli_handler.py` | Base URL API |
| API Timeout | 8 detik | `core/kbli_handler.py` | Per request |
| Top-K per API | 5 | `core/kbli_handler.py` | Jumlah hasil tiap query |
| Top per Query (pool) | 2 | `pool_and_dedup()` | Ambil 2 terbaik per varian |
| Max Final Items | 6 | implicit | 3 interpretasi × 2 hasil |
| LLM for Expand | DeepSeek V4 Flash | `core/llm.py` | Model ringan |
| LLM for Re-rank | DeepSeek V4 Flash | `core/llm.py` | Model ringan |
| Expand Timeout | 15 detik | `server.py` | Timeout LLM expand |
| Re-rank Timeout | 30 detik | `server.py` | Timeout LLM re-rank |
| Min Query Length | 2 karakter | `search_kbli_api()` | Minimal query bersih |

---

## File Structure

```
chatbot-qna/
├── server.py                    # Routing → KBLI pipeline (lines ~353-427)
├── core/
│   ├── __init__.py
│   ├── kbli_handler.py          # Semua logika KBLI
│   │   ├── is_kbli_query()      # Deteksi trigger
│   │   ├── extract_kbli_code()  # Ekstrak 5-digit code
│   │   ├── clean_kbli_query()   # Hapus noise words
│   │   ├── search_kbli_api()    # API call ke kbli.co.id
│   │   ├── parse_expand_response()  # Parse JSON dari LLM expand
│   │   ├── format_kbli_context()    # Format hasil API (v1)
│   │   ├── format_kbli_context_v2() # Format hasil API (v2 — grouped)
│   │   ├── pool_and_dedup()     # Gabung + dedup hasil multi-API
│   │   ├── get_sector_label()   # Cari kategori sektor
│   │   └── format_sectors()     # Daftar sektor
│   ├── kbli_sectors.py          # Mapping kode → sektor (A–V)
│   └── llm.py                   # Load prompt template untuk KBLI
├── prompts/
│   ├── kbli.md                  # System prompt re-rank (v2)
│   ├── kbli_expand.md           # System prompt query expansion
│   └── KBLI-FLOW-v2.md          # Dokumentasi alur v2
└── README.md                    # Dokumentasi global
```

---

## Common Mistakes & Known Issues

### ❌ User sering salah bedain kategori
**Masalah:** User sering bingung antara produksi (industri) vs jualan (perdagangan) vs jasa.
**Solusi:** LLM expansion generate 3 varian yang beda sudut pandang secara otomatis.

### ❌ Eceran vs Grosir ketuker
**Masalah:** API kadang return hasil yang mirip untuk eceran (47711) dan grosir (464xx).
**Solusi:** LLM re-rank bedain dari deskripsi user asli.

### ❌ Multi-kegiatan usaha
**Masalah:** User punya >1 jenis kegiatan (jualan + produksi sendiri).
**Solusi:** Grouping per interpretasi menampilkan beberapa opsi sekaligus.

### ❌ API kadang ngaco
**Masalah:** API kbli.co.id kadang return hasil yang kurang relevan untuk query tertentu.
**Solusi:** Multi-query expansion + 3 concurrent call coverage, LLM re-rank fix.

### ❌ LLM hallucination
**Masalah:** LLM kadang menambahkan kode KBLI dari pengetahuannya sendiri.
**Solusi:** Prompt explicitly melarang — "Jangan tambahkan data KBLI dari pengetahuan sendiri."

### ⚠️ Rate Limit API
Belum diketahui batas rate limit kbli.co.id. 3 concurrent call per request user dengan rata-rata ~5-10 detik antar request seharusnya aman.

---

## Changelog

### v2.16.0 (2026-06-23)
- **feat:** KBLI v2 — multi-query expansion (3 varian) + concurrent API
- **feat:** Pooling + dedup by kode KBLI (top 2 per query)
- **feat:** LLM re-rank with grouping per interpretasi + "Cocok untuk"
- **new:** `prompts/kbli_expand.md` — prompt untuk query expansion
- **update:** `prompts/kbli.md` — format baru grouping + kategori + cocok untuk
- **update:** `core/kbli_handler.py` — expand response parser, pool & dedup, format v2
- **update:** `core/llm.py` — load kbli expand template

### v2.15.0 (2026-06-22)
- **feat:** KBLI lookup pertama — single API call + LLM format
- **fix:** Trigger hanya kata "kbli" (case insensitive)
- **fix:** Wajib 100% bahasa Indonesia (terjemah deskripsi Inggris)
- **fix:** Bold markdown, bukan HTML

---

## Testing

### Manual Test Cases

| Input | Expected |
|-------|----------|
| "kbli jualan bakso" | ✅ 3 interpretasi (restoran, industri, kaki lima) |
| "KBLI untuk usaha konveksi baju" | ✅ Industri pengolahan (C) |
| "kbli restoran" | ✅ Kategori I |
| "kbli 56101" | ✅ Spesifik kode, fallback ke deskripsi |
| "apa KBLI untuk jual pulsa" | ✅ Kategori J (Informasi & Komunikasi) |
| "kbli " (empty) | ✅ Fallback ke manual link |
| Non-KBLI biasa | ❌ Tidak trigger |

### Monitoring
- **Log:** Prefix `[KBLI]` di server log — pantau jumlah request, error API
- **Dashboard:** Ada field `gate` di log_query — filter `"KBLI"`
