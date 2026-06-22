# KBLI Flow v2 — Multi-Query Expansion + Pooling

> Draft: 2026-06-23
> Status: 💬 Diskusi (belum implementasi)

## 🎯 Alur Lengkap

```
User: "kbli untuk [deskripsi usaha]"
         │
         ▼
┌── 1. DETEKSI ───────────────────────────────────┐
│  is_kbli_query() — regex \bkbli\b               │
│  Sama seperti sekarang, tidak ada perubahan      │
└──────────────────────────────────────────────────┘
         │
         ▼
┌── 2. CLEAN ──────────────────────────────────────┐
│  clean_kbli_query() — strip noise words          │
│  Sisa: "[deskripsi usaha]" bersih                │
└──────────────────────────────────────────────────┘
         │
         ▼
┌── 3. LLM EXPAND ────────────────────────────────┐
│  System prompt: prompts/kbli_expand.md           │
│  Input: deskripsi user yang sudah di-clean       │
│  Output: JSON array of 3 strings                 │
│                                                   │
│  Contoh:                                          │
│  Input:  "jualan bakso"                          │
│  Output: ["restoran bakso sapi siap saji",       │
│           "industri pembuatan bakso beku",       │
│           "pedagang kaki lima bakso"]            │
│                                                   │
│  ⚡ Single LLM call (ringan, model flash)         │
└──────────────────────────────────────────────────┘
         │
         ▼
┌── 4. API POOLING ───────────────────────────────┐
│  foreach query in 3 varian:                      │
│    hasil = search_kbli_api(query) → top 5        │
│    append ke pool                                 │
│                                                   │
│  Pool = 3 × 5 = ~15 hasil (bisa kurang kalo      │
│  ada kode yang sama dari beda query)             │
│                                                   │
│  ⚡ 3× async call → concurrent via httpx          │
└──────────────────────────────────────────────────┘
         │
         ▼
┌── 5. DEDUP ──────────────────────────────────────┐
│  dedup_kbli_results(pool):                        │
│    - Group by kode KBLI (5 digit)                 │
│    - Tiap grup: ambil entry dengan               │
│      _semanticSimilarity tertinggi               │
│    - Sort by similarity descending                │
│    - Ambil top 7 (untuk konteks LLM)             │
│                                                   │
│  ⚡ O(15) — sekejap                               │
└──────────────────────────────────────────────────┘
         │
         ▼
┌── 6. LLM RE-RANK + FORMAT ──────────────────────┐
│  System prompt: prompts/kbli.md (update)         │
│  Context: top 7 hasil dedup (kode, nama,         │
│           kategori, deskripsi)                   │
│  Tugas:                                           │
│    - Re-rank berdasarkan deskripsi USER ASLI     │
│    - Tampilkan format:                           │
│      1. **Kategori: X — Nama**                   │
│         **KBLI XXXXX — Nama**                    │
│         Deskripsi singkat                        │
│         → **Cocok untuk:** [penjelasan]          │
│  Output: 5 opsi terbaik + disclaimer              │
│                                                   │
│  ⚡ 1 LLM call (sama kayak sekarang)              │
└──────────────────────────────────────────────────┘
```

## 🔄 Ringkasan Perubahan

| Tahap | Sebelum | Sesudah |
|-------|---------|---------|
| **Expand** | ❌ Tidak ada — langsung API | ✅ LLM expand → 3 varian query |
| **API Call** | 1× ke kbli.co.id | 3× concurrent ke kbli.co.id |
| **Dedup** | ❌ Tidak perlu | ✅ Dedup 15→7 by kode |
| **LLM Re-rank** | 1 call (format lama) | 1 call (format baru + "Cocok untuk") |
| **Total LLM** | 1 call | **2 calls** (+1 ringan untuk expand) |
| **Total API** | 1 call | **3 calls** (concurrent) |

## 📦 File Baru

| File | Fungsi |
|------|--------|
| `prompts/kbli_expand.md` | ✅ Baru — system prompt untuk LLM expansion |
| `prompts/kbli.md` | ✅ Update — format kategori di atas + "Cocok untuk" |
| `core/kbli_handler.py` | 🔄 Nanti di-update — tambah expand + pool + dedup |

## 💡 Catatan

- **3× API call concurrent** — pake `asyncio.gather()` atau `httpx.AsyncClient` parallel, gak nambah latency signifikan (total tetap ~1-3 detik)
- **LLM expand** — model flash cukup (DeepSeek V4 Flash), prompt sederhana, output JSON
- **Dedup by kode** — hasil pooling yang punya kode KBLI sama, ambil yang skor semantic similarity tertinggi
- **"Cocok untuk"** — LLM jelasin alasan matching berdasarkan deskripsi user asli + data KBLI, bukan ngarang
