# NARA (NextGen AI Response Agent)

Asisten permasalahan IT dari **BPS Provinsi Kepulauan Bangka Belitung**.

> **N**extGen — Teknologi modern dan inovatif
> **A**I — Kecerdasan buatan sebagai mesin utama
> **R**esponse — Fokus menjawab dan merespons kebutuhan pengguna
> **A**gent — Asisten digital yang bertindak atas nama layanan

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)](https://core.telegram.org/bots)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Bridge-25D366?logo=whatsapp)](https://whatsapp.com)
[![Hybrid](https://img.shields.io/badge/Retrieval-Hybrid%20(E5%2BBM25)-purple)](https://huggingface.co/intfloat/multilingual-e5-base)
[![Dashboard](https://img.shields.io/badge/Dashboard-Web%20UI-%230070d1)](http://localhost:8001)
[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen)]()

Asisten permasalahan IT dari **BPS Provinsi Kepulauan Bangka Belitung**. Melayani pertanyaan seputar **SOBAT, GC PBI, GC PLN, FASIH,** dan **Pengolahan SE2026** via Telegram & WhatsApp.

> **Stack:** FastAPI + Hybrid E5+BM25 (RRF fusion) + Multi-LLM failover + SQLite + EasyOCR
> **Model:** Cloud (OpenAI-compatible) → Ollama lokal — auto failover

---

## 📋 Daftar Isi

- [📸 Tangkapan Layar](#tangkapan-layar)
- [🛠️ Tech Stack](#tech-stack)
- [✨ Fitur](#fitur)
- [🔒 Security & Proteksi](#security-proteksi)
- [🧠 Arsitektur Modular](#arsitektur-modular)
- [🧠 Detail Hybrid Search (E5 + BM25 via RRF)](#detail-hybrid-search-e5-bm25-via-rrf)
- [🆚 Perbandingan & Arsitektur Pipeline](#🆚-perbandingan-arsitektur-pipeline)
- [🔄 Replikasi / Custom Bot](#replikasi-custom-bot)
- [💻 Panduan Instalasi — Windows](#panduan-instalasi-windows)
- [🐧 Panduan Instalasi — Linux](#panduan-instalasi-linux)
- [✅ Verifikasi](#verifikasi)
- [🔗 API Endpoints](#api-endpoints)
- [📊 Logging & Evaluasi](#logging-evaluasi)
- [🖥️ Dashboard](#dashboard)
- [❓ FAQ](#faq)
- [📜 Riwayat Versi](#riwayat-versi)
- [📞 Kontak & Dukungan](#kontak-dukungan)
- [📄 Lisensi](#lisensi)


---

## 📸 Tangkapan Layar

<table>
  <tr>
    <td><img src="screenshots/wa-chat.jpg" alt="WhatsApp — Nara menjawab pertanyaan" width="300"></td>
    <td><img src="screenshots/tg-chat.jpg" alt="Telegram — Nara menjawab pertanyaan" width="300"></td>
  </tr>
  <tr>
    <td align="center"><sub>WhatsApp</sub></td>
    <td align="center"><sub>Telegram</sub></td>
  </tr>
</table>

---

## 🛠️ Tech Stack

| Layer | Teknologi |
|-------|-----------|
| **API Server** | FastAPI (Python) |
| **Domain Gate** | BM25 3-tier — <3 tolak, 3-4.9 QNA link, ≥5 hybrid search. Cascade BM25 depth 3 untuk follow-up pendek |
| **Hybrid Retrieval** | E5+BM25 via RRF fusion (K=60) — E5 semantic + BM25 keyword, top-5 FAQ |
| **Intent Classifier** | scikit-learn SGDClassifier + TF-IDF (pure Python, 185KB, 97.4% accuracy) — 5 kelas: greeting, capability, positive_feedback, negative_feedback, forward. Fallback keyword regex |
| **LLM Gateway** | Multi-provider: OpenCode → DeepSeek → Ollama lokal — auto failover chain |
| **Multi-Part Split** | E5 Semantic Boundary — heuristic split (konjungsi + delimiter) + E5 cosim merge (threshold 0.78) |
| **Database** | Google Sheets (FAQ live sync) + SQLite (chat history + daily limit) |
| **Telegram** | python-telegram-bot (Polling) |
| **WhatsApp** | whatsapp-web.js (Node.js bridge via Flask) |
| **OCR** | EasyOCR (Indonesia + Inggris, lazy load ~500MB) |
| **Dashboard** | FastAPI + vanilla HTML/CSS/JS (port 8001) — Live Terminal, RRF chart, Query Monitor |
| **Bahasa** | Python 3.11+ / Node.js v20 LTS

---

## ✨ Fitur

| Fitur | Detail |
|-------|--------|
| 🤖 **AI Answering** | Multi-LLM dengan failover chain. Coba provider 1 → error? auto lanjut provider 2 → dst. Cloud API (OpenAI-compatible) & Ollama lokal |
| 🧠 **Domain Gate (BM25 3-Tier)** | **3 tier**: BM25 < 3.0 → OOC (tolak), 3.0-4.9 → BM25_BORDERLINE (QNA link), ≥ 5.0 → lanjut hybrid search. Cascade BM25 depth 3 untuk follow-up pendek (best practice: NVIDIA 3-5 turns, Chatnexus sliding window 3). **Zero LLM cost untuk out-of-context & borderline.** |
| 🧠 **Hybrid Search (E5+BM25 via RRF)** | E5 semantic + BM25 keyword fusion via Reciprocal Rank Fusion (K=60). RRF **hanya untuk ranking** (bukan gate). Kategori sebagai metadata terpisah (gak ikut embedding). top_k=5. Centroid di-log untuk analytics. |
| 🧩 **Multi-Part Split (E5 Semantic Boundary)** | 2-layer: heuristic split (konjungsi + delimiter) → E5 cosim merge (threshold 0.78). Bagian di luar BPS di-skip. |
| 🏷️ **scikit-learn Intent Classifier** | SGDClassifier + TF-IDF — pure Python, zero C++ compiler. 5 kelas: greeting, capability, positive_feedback, negative_feedback, forward. 4 kelas respon langsung (template statis), skip retrieval & LLM. Keyword fallback safety net. |
| 📱 **WhatsApp Integration** | Bridge via `whatsapp-web.js`. QR scan, typing indicator, support gambar + OCR |
| ✈️ **Telegram Bot** | Reply keyboard, typing indicator, "⏳ Memproses gambar..." (auto-hapus setelah jawaban) |
| 🗣️ **OCR Gambar** | Screenshot error dibaca otomatis via EasyOCR. Support Indo + Inggris. **Bebas limit 500 karakter** (khusus OCR). |
| 🔄 **Auto-Reload FAQ** | Download ulang dari Google Sheets tiap 10 menit. Bisa reload manual via `/reload` |
| 📜 **Chat History** | Semua percakapan tersimpan di SQLite — kolom chat_id, pertanyaan, jawaban, source (API/WA/Telegram), BM25, RRF, gate status |
| 📊 **Dashboard** | Monitoring real-time: Live Terminal, RRF chart, Queries/Hour, Top FAQ, LLM response time, Daily users. Sidebar collapsible (desktop + mobile). |
| 🔄 **Cascade Fallback (E5 similarity)** | Jika BM25 < 5 + ada history, concat prev query depth 1-3 lalu hitung BM25 ulang. Jika cascade BM25 ≥ 5, cek **E5 similarity** antara query asli vs query sebelumnya (cosine sim ≥ 0.70). Jika similarity rendah → topic drift → cascade skip, jatuh ke 3-tier gate normal. Cegah query non-BPS yang numpang keyword dari history tembus cascade. |
| 🧹 **Input Sanitasi** | Karakter kontrol dibuang, emoji dibatasi maks 5, teks biasa maks 500 karakter (kecuali OCR). |
| 📝 **Markdown di Telegram** | Kirim **bold** dan *italic* via `ParseMode.MARKDOWN`. WhatsApp otomatis strip formatting. |
| 📊 **Query Logging** | Dual-log (JSONL + SQLite) — 25 kolom: pertanyaan asli user, CLF, RRF, E5 Top, BM25 Gate, BM25 Raw, gate status, LLM response, source tracking. `top5_faq` diberi label ranking (#1-#5) |

---

## 🔒 Security & Proteksi

Bot ini punya **6 lapis proteksi**:

| # | Lapisan | File | Cara Kerja |
|---|---------|------|------------|
| 1 | 🚫 **Anti-Spam** | `security/rate_limiter.py` | **5 request per menit** per user. Lewat? Block **5 menit**. Silent block setelah peringatan pertama |
| 2 | 📅 **Daily Chat Limit** | `server.py` | **25 chat per hari** per user. Reset otomatis tiap ganti hari (WIB) |
| 3 | 💬 **Session Timeout** | `security/session.py` | Session expired setelah **30 menit idle**. Watchdog tiap 15 detik, notif otomatis |
| 4 | 🎯 **scikit-learn Intent Classifier** | `core/intent_classifier.py` | scikit-learn SGDClassifier + TF-IDF. Pure Python — zero C++ compiler. 5 kelas: greeting, capability, positive_feedback, negative_feedback, forward. Training dari `classifier_train.txt` (845 sampel), akurasi 98.1%. Keyword fallback sbg safety net |
| 5 | 🔍 **Domain Gate (BM25 3-Tier)** | `core/bm25.py` → `server.py` | **BM25 3-tier threshold.** `BM25 < 3.0` → OOC (tolak). `3.0-4.9` → BM25_BORDERLINE (QNA link). `≥ 5.0` → lanjut hybrid search. Cascade BM25 depth 3 untuk follow-up. Centroid E5 di-log untuk analytics. **Zero LLM cost untuk out-of-context.** |
| 6 | 👑 **Trusted User** | `security/rate_limiter.py` | User di `TRUSTED_CHAT_IDS` **skip anti-spam & daily limit** |

### Detail Pipeline Domain Filter (BM25 Threshold)

```
Input → scikit-learn → greeting / capability → respon langsung (skip LLM)
                 → lainnya → BM25 keyword check
                              ├─ BM25 < 3.0 → ❌ OOC_BM25 (tolak, tanpa retrieval)
                              ├─ 3.0 ≤ BM25 < 5.0 → ❌ BM25_BORDERLINE (QNA link)
                              ├─ BM25 < 5 + ada history → cascade concat prev query depth 1-2
                              │   └─ BM25 cascade ≥ 5.0? → hybrid → LLM
                              └─ BM25 ≥ 5.0 → hybrid_search (E5+BM25 RRF) → LLM
```

**Kenapa BM25?** Keyword overlap langsung mengukur "ada gak sih istilah BPS di pertanyaan ini?". Query tanpa satupun istilah FAQ (nasi goreng, presiden AS) langsung ketahuan dari BM25 rendah.

**Threshold BM25 (dari analisis 100+ query production):**
| BM25 Range | Arti | Contoh Query |
|:---------:|------|--------------|
| BM25 Range | Arti | Gate | Contoh Query |
|:---------:|------|:----:|--------------|
| **< 3.0** | Gak ada keyword BPS signifikan | ❌ OOC_BM25 (tolak) | "cara membuat nasi goreng" (0.0), "resep nasi goreng" (0.0) |
| **3.0 - 4.9** | Keyword generic — samar | ❌ BM25_BORDERLINE (QNA link) | "di dtsen juga" (2.49), "maaf pak mau tanya" (3.2), "nasi goreng ala bps" (4.8) |
| **5.0 - 10.0** | Sinyal BPS jelas | ✅ Lanjut hybrid | "NIK sesuai KTP" (5.07), "FASIH gagal login" (6.79) |
| **10.0+** | FAQ match kuat | ✅ Lanjut hybrid | "verifikasi NIK gagal" (10.66), OCR screenshot (34-42) |

**Tambahan:** Centroid E5 dihitung (rata-rata vektor FAQ) dan di-log ke `query_log.db` untuk analytics dashboard, tapi **tidak digunakan sebagai gate**.

### 📩 QNA Form Link

Ketika hybrid search mendeteksi pertanyaan **domain BPS tapi belum ada di FAQ**, NARA memberikan link:

**http://s.bps.go.id/nara-qna**

Link keluar di 2 situasi:
1. **BM25 < 3.0** — OOC_BM25 (gak ada keyword BPS, tolak total)
2. **BM25 3.0-4.9** — BM25_BORDERLINE (ada sinyal BPS, tapi gak cukup kuat untuk FAQ match)

Response templates di `prompts/responses.json`:
- `rejection_out_of_context` — "Maaf, saya tidak bisa menjawab..." (BM25 < 3.0 — out of domain)
- `rejection_no_answer` — "Silakan ajukan lewat form..." (BM25 3.0-4.9 — borderline, gak match FAQ)

**Kenapa BM25 bisa jadi domain filter?**
BM25 = keyword overlap antara query user dan seluruh FAQ. Query di luar domain → gak ada satupun istilah BPS → BM25 < 3.0 → **tolak tanpa retrieval maupun LLM**. Query BPS → BM25 ≥ 3.0 → lanjut hybrid search + LLM. **Zero LLM cost untuk out-of-context.**

### Trusted User

User di `TRUSTED_CHAT_IDS` (dari `.env`) **tidak kena** anti-spam & daily limit. Tapi tetap kena session timeout.

### Input Sanitasi (Layer Awal)

- Control characters (`\x00-\x1f`) — dibuang
- Emoji > 5 — kelebihan dihapus
- Karakter > 500 — ditolak (kecuali dari OCR gambar)
- Input dari OCR (screenshot error, foto dokumentasi) **dibebaskan dari limit 500 karakter** via flag `is_ocr: True` di request. Server bedain berdasarkan field `is_ocr` di ChatRequest — kalo True, skip character limit

---

## 🧠 Arsitektur Modular

```
chatbot-qna/
│
├── server.py                 ← FastAPI router — inti logika chatbot
├── telegram_bot.py           ← Layer Telegram (OCR, sanitasi, kirim API)
├── wa_handler.py             ← Layer WhatsApp (Flask, terima dari bridge)
├── dashboard.py              ← Dashboard monitoring (port 8001)
├── start-all.bat             ← 1 klik buka 5 terminal + dashboard
│
├── core/                     ← 🔧 Mesin utama
│   ├── database.py           ←   SQLite: session chat history, daily limit
│   ├── embedder.py           ←   E5-base: load, encode, hybrid search (E5+BM25 RRF)
│   ├── bm25.py               ←   BM25: per-doc scoring untuk hybrid retrieval + domain gate
│   ├── intent_classifier.py  ←   scikit-learn SGDClassifier + TF-IDF intent classifier
│   ├── classifier_train.txt  ←   Training data (478 sampel, 5 kelas)
│   ├── intent_model.pkl      ←   Trained model (auto-generated, ~185KB)
│   ├── llm.py                ←   Multi-provider LLM, failover chain, build prompt
│   └── query_logger.py       ←   Query evaluation logging (JSONL + SQLite)
│
├── security/                 ← 🔒 Lapisan pengaman
│   ├── rate_limiter.py       ←   Anti-spam (5/menit), trusted user, daily limit
│   └── session.py            ←   Session: timeout 30 menit, watchdog
│
├── prompts/                  ← 🎯 IDENTITAS & ATURAN (ganti untuk replikasi)
│   ├── identity.json         ←   Nama, role, topik (ubah ini saja untuk bot berbeda)
│   ├── system.md             ←   System prompt — aturan main LLM
│   ├── greeting.md           ←   Template sapaan pertama
│   └── responses.json        ←   Semua user-facing text (tolak, error, dll)
│
├── templates/                ← 🎨 HTML Template
│   └── dashboard.html        ←   Dashboard UI (1447 baris vanilla HTML/CSS/JS)
│
├── whatsapp-bridge/          ← 📱 Bridge WhatsApp
│   ├── bridge.js             ←   whatsapp-web.js client (QR scan, typing, image)
│   └── package.json          ←   Node.js dependencies
│
├── faq_categories.json       ← 📊 Auto-generated kategori FAQ (dipake dashboard)
└── query_log.jsonl           ← 📊 Log evaluasi query (auto-generated)
```

### Alur Proses Chat (End-to-End)

```
USER CHAT
  │
  ▼
┌─ 1. INPUT SANITASI ──────────────────────────────┐
│  • Hapus karakter kontrol                         │
│  • Batasi emoji (maks 5)                          │
│  • Tolak >500 karakter (kecuali OCR gambar)       │
│  • OCR gambar via EasyOCR (lazy load ~500MB)      │
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 2. ANTI-SPAM & DAILY LIMIT ──────────────────────┐
│  • Rate limit: 5 req/menit, block 5 menit         │
│  • Daily limit: 25 chat/hari per user             │
│  • Trusted IDs (dari .env) skip semua             │
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 3. INTENT CLASSIFIER (scikit-learn, 97.4%) ─────┐
│  greeting        → LLM sapaan (tanpa retrieval)   │
│  capability      → Template daftar topik          │
│  positive_fb     → "Sama-sama 😊"                 │
│  negative_fb     → "Maaf ya 🙏"                    │
│  forward         → lanjut ke domain gate ↓        │
└───────────────────────────────────────────────────┘
  │ (kalau forward)
  ▼
┌─ 4. DOMAIN GATE: BM25 3-TIER ────────────────────┐
│  BM25 = keyword overlap query vs semua FAQ        │
│  • BM25 < 3.0    → ❌ OOC_BM25 (tolak, NO cascade) │
│  • BM25 3.0-4.9  → ❌ BM25_BORDERLINE (QNA link)   │
│  • BM25 3-4.9 + history → CASCADE depth 1-3       │
│  • BM25 ≥ 5.0    → ✅ lanjut hybrid ↓              │
│  Cascade: concat prev query, hitung BM25 ulang     │
└───────────────────────────────────────────────────┘
  │ (BM25 ≥ 3.0)
  ▼
┌─ 5. MULTI-PART SPLIT? ───────────────────────────┐
│  Ada konjungsi ("dan", "serta", "juga")?          │
│  YA → Split → tiap part hybrid search sendiri     │
│        Merge kalo E5 similarity ≥ 0.78            │
│  TIDAK → Single question ↓                        │
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 6. HYBRID SEARCH (E5 + BM25 via RRF) ──────────┐
│  E5 semantic similarity  +  BM25 keyword scoring  │
│  RRF: 1/(rank_E5+K) + 1/(rank_BM25+K), K=60      │
│  Top-5 FAQ terpilih (RRF ranking, BUKAN gate)     │
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 7. RRF GATE (3 cabang) ────────────────────────┐
│  (RRF digunakan untuk ranking, bukan gate)       │
└───────────────────────────────────────────────────┘
  │ (ANSWER)
  ▼
┌─ 8. LLM GENERATE ───────────────────────────────┐
│  System prompt + 5 FAQ context + chat history     │
│  Multi-provider failover (cloud → Ollama lokal)   │
│  Timeout 30 detik per provider                    │
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 9. RESPONSE + LOGGING ─────────────────────────┐
│  Kirim jawaban ke user (Telegram / WA / API)      │
│  DUAL-LOGGED: JSONL + SQLite (non-blocking thread)│
│  Kolom: BM25 Gate, BM25 Raw, RRF, E5, centroid_sim, gate │
└───────────────────────────────────────────────────┘
```

> **Ringkasan:** User chat → sanitasi → anti-spam → intent classifier → **BM25 3-tier gate (OOC/BORDERLINE/ANSWER)** → cascade depth 2 → hybrid search (E5+BM25 RRF) → LLM → jawab + log

---

## 🧠 Detail Hybrid Search (E5 + BM25 via RRF)

Hybrid search menggabungkan **2 pendekatan berbeda** — keyword exact match (BM25) dan semantic similarity (E5) — lalu menyatukan peringkatnya pakai **Reciprocal Rank Fusion (RRF)**.

---

### 🔤 BM25 — Keyword Exact Match

**BM25 (Best Matching 25)** adalah algoritma ranking berbasis _term frequency_ — turunan modern dari TF-IDF.

**Cara kerja:**
1. Query user di-tokenisasi & di-*stopword* (kata umum seperti "siapa", "bagaimana", "bapak", "ibu" dihapus)
2. Tiap FAQ juga di-tokenisasi saat index di-build
3. BM25 menghitung skor tiap dokumen berdasarkan:
   - **Seberapa sering** kata kunci query muncul di dokumen (TF — Term Frequency)
   - **Seberapa langka** kata itu di seluruh corpus (IDF — Inverse Document Frequency)
   - **Panjang dokumen** — dokumen panjang di-penalti biar gak curang

**Rumus (intuisi):**
```
BM25(doc, query) = sum over query terms [ IDF(term) × TF(term, doc) / (TF(term, doc) + k₁ × (1 − b + b × docLen/avgDocLen)) ]
```

**Di NARA, BM25 punya 1 peran:**

| Peran | Ada di | Threshold | Fungsi |
|-------|--------|-----------|--------|
| 🔗 **Hybrid Leg** | `core/embedder.py` | Per-doc, di-RRF | `get_bm25_scores_all()` return skor BM25 untuk semua FAQ, digabung dengan ranking E5 via RRF |

> **Catatan:** BM25 punya dua peran: (1) **Gate 3-tier** — `get_bm25_score()` ambil max dari semua FAQ, putuskan OOC/BM25_BORDERLINE/lanjut. Juga sebagai **cascade trigger** — concat prev query depth 1-3 kalo BM25 < 5. Cascade lolos ke **hybrid search** (E5+BM25 RRF), bukan cuma BM25.. (2) **Hybrid leg** — `get_bm25_scores_all()` return per-doc untuk RRF fusion. Kedua nilai di-log terpisah: `bm25_gate` (gate) dan `bm25_raw` (BM25 FAQ pemenang RRF). Centroid E5 di-log untuk analytics (bukan gate).

**✅ Kelebihan:**
- ⚡ **Cepat & ringan** — tanpa GPU, CPU doang udah cukup. Index built dalam < 1 detik untuk 127 FAQ
- 🔍 **Transparan** — skor bisa di-debug
- 🎯 **Peka istilah teknis** — kode kayak "GC PBI", "FASIH", "SE2026 prelist" langsung kena skor tinggi karena exact match
- 🧹 **Zero dependency** — implementasi custom Python
- 📉 **Memory footprint** — ~10 KB doang (cuma frequency table)

**❌ Kekurangan:**
- 🧠 **Buta sinonim** — "lupa password" dan "lupa kata sandi" dianggap berbeda total karena surface form beda
- 📖 **Buta konteks kalimat** — urutan kata gak ngaruh. "Aktivasi FASIH error" sama dengan "error aktivasi FASIH"
- 📏 **Bergantung kualitas FAQ** — kalo FAQ singkat/sedikit kata, skor BM25-nya rendah
- 📐 **Skor beda-beda tiap query** — skor BM25 antar query gak bisa dibandingin langsung

---

### 🧬 E5-base — Semantic Similarity

**E5 (EmbEddings from bidirEctional Encoder rEpresentations)** adalah model embedding dari Microsoft — versi khusus `intfloat/multilingual-e5-base` yang support **multilingual** (termasuk Indonesia). Output: vektor 768 dimensi.

**Cara kerja:**
1. FAQ di-encode **sekali saat startup** dengan prefix `"passage: "` → jadi 768D vector tiap FAQ
2. Query user di-encode **real-time** dengan prefix `"query: "` → 768D vector
3. Cosine similarity antara query vector dan tiap FAQ vector:
   ```
   cosine_sim(q, d) = dot(q, d) / (||q|| × ||d||)
   ```
   Range: -1 sampai 1 (makin mendekati 1 = makin mirip secara semantik)

**Kenapa pake prefix `"passage:"` / `"query:"`?**
E5 adalah model **asymmetric** — dia dilatih khusus untuk matching query → passage. Prefix yang beda bikin representasi lebih akurat daripada encode polos.

**✅ Kelebihan:**
- 🧠 **Paham sinonim** — "lupa password" ⇄ "lupa kata sandi" tetap nyambung karena representasi vektornya mirip
- 📖 **Peka konteks kalimat** — urutan kata ngaruh. "Cara reset password" beda embedding dengan "password reset cara"
- 🌐 **Multilingual** — E5-base dilatih untuk banyak bahasa, termasuk Indonesia. Gak perlu model Inggris doang
- 🔄 **Robust ke variasi bahasa** — "gimana cara daftar SOBAT?", "cara pendaftaran SOBAT", "SOBAT registration" semua punya vektor yang berdekatan
- 🧩 **Generalize ke FAQ baru** — selama FAQ masih dalam domain yang sama, similarity tetap akurat meskipun kata-katanya gak persis sama

**❌ Kekurangan:**
- 💾 **Butuh memori besar** — model E5-base ~278MB di RAM. Untuk server dengan RAM terbatas, ini berat
- 🐢 **Lambat di CPU** — encode query butuh ~200-500ms di CPU. Kalo rame, bisa jadi bottleneck
- 🎯 **Kurang peka keyword spesifik** — kode teknis kayak "GC PBI" atau "FASIH" yang jarang muncul di training data bisa kena noise. "GC PLN error" bisa mirip vektornya dengan "GC PBI error" karena pola kalimatnya sama — padahal topiknya beda
- 📉 **Semantic drift** — query pendek kayak "linknya udah dicoba" punya vektor yang tersebar (gak jelas arahnya), similarity jadi rendah ke FAQ manapun
- 🔄 **Harus rebuild encoding** — setiap FAQ berubah (reload), semua 127 vektor harus di-encode ulang (~10-20 detik di CPU)
- 🧪 **Blackbox** — susah di-debug kenapa similarity 0.65 dan bukan 0.85. Gak ada keyword yang bisa diinspeksi seperti BM25

---

### 🔗 RRF Fusion — Menyatukan BM25 + E5

**RRF (Reciprocal Rank Fusion)** adalah metode tanpa training untuk menggabungkan ranking dari dua atau lebih sistem retrieval.

**Cara kerja:**
1. BM25 meng*ranking* semua FAQ → tiap FAQ dapat rank_BM25 (1 = paling cocok keyword)
2. E5 meng*ranking* semua FAQ → tiap FAQ dapat rank_E5 (1 = paling cocok semantik)
3. RRF menghitung **skor gabungan** per FAQ:
   ```
   ```
   Kalo BM25_max > 0:
     RRF_score(d) = 1/(K+rank_E5(d)) + 1/(K+rank_BM25(d))
   Kalo BM25_max == 0 (out of context):
     RRF_score(d) = 1/(K+rank_E5(d))  ← skip BM25, hindari ranking noise
   ```
   **K = 60** — konstanta smoothing industry standard.
4. Ambil **top-5** FAQ berdasarkan RRF_score tertinggi

**Visual sederhana (2 FAQ):**
| FAQ | rank_E5 | rank_BM25 | RRF dengan K=60 |
|-----|:-------:|:---------:|:----------------:|
| "Cara aktivasi FASIH" | 1 | 2 | 1/(60+1) + 1/(60+2) = 0.0325 |
| "FASIH error terus" | 3 | 1 | 1/(60+3) + 1/(60+1) = 0.0323 |

→ FAQ pertama menang tipis. Tapi kalo BM25 gak cocok sama sekali (rank rendah), E5 masih bisa angkat FAQ yang relevan secara semantik.

**Kenapa RRF? Kenapa gak average atau weighted sum?**
- **Average score** gak fair karena BM25 score range beda dengan cosine similarity
- **Weighted sum** butuh tuning bobot manual
- **RRF** cuma butuh ranking (bukan skor mentah), jadi scale-invariant, zero-config, dan terbukti robust di berbagai dataset

---

### 🏷️ scikit-learn — Intent Classifier (CLF)

Sebelum hybrid search dijalankan, **CLF (Classifier)** menyaring 5 jenis intent user yang **gak perlu retrieval** — langsung respon dengan template / LLM greeting:

**Arsitektur:**
```
Input user → CLF (SGDClassifier + TF-IDF, 185KB, 97.4% accuracy)
              ├─ greeting            → LLM menjawab dengan sapaan ramah
              ├─ capability          → Template statis: "Saya bisa membantu: ..."
              ├─ positive_feedback   → Template: "Senang bisa membantu, terima kasih telah menggunakan layanan Nara 😊"
              │                        (hanya direspon jika session punya riwayat forward;
              │                         tanpa konteks → treat sebagai greeting)
              ├─ negative_feedback   → Template + link QNA: "Maaf ya... silakan ajukan lewat form"
              │                        (hanya direspon jika session punya riwayat forward;
              │                         tanpa konteks → treat sebagai forward)
              └─ forward             → Lanjut ke hybrid search + domain filter (RRF gate)
```

**Context-aware feedback (v2.5.1+):**
- Feedback responses (`positive_feedback` / `negative_feedback`) **hanya muncul** jika session telah memiliki riwayat CLF `forward` (user pernah bertanya sebelumnya).
- `positive_feedback` tanpa konteks → diarahkan ke **greeting** (user mungkin cuma ramah).
- `negative_feedback` tanpa konteks → diarahkan ke **forward pipeline** (user mungkin typo atau iseng; fallback ke BM25 gate normal).

| Domain | Deskripsi | Contoh Input | Respon | Handler |
|--------|-----------|-------------|--------|---------|
| **greeting** | User menyapa | "halo", "pagi nara", "assalamualaikum", "met malem", "hi bang" | LLM — sapaan ramah + tawarkan bantuan | `prompts/greeting.md` |
| **capability** | User tanya kemampuan bot | "kamu bisa apa?", "nara bisa ngapain?", "fitur apa aja?", "siapa kamu?" | Template statis — daftar topik dari identity.json | `responses.json → capability` |
| **positive_feedback** | User berterima kasih / acknowledge | "makasih", "terima kasih banyak", "ok", "sip", "mantap", "noted" | "Senang bisa membantu, terima kasih telah menggunakan layanan Nara 😊" | `responses.json → positive_feedback` (hanya jika ada riwayat forward; tanpa konteks → greeting) |
| **negative_feedback** | User komplain / kecewa | "kamu tidak membantu", "ga guna", "jawabanmu salah", "jelek", "payah" | "Maaf ya..." + link QNA `s.bps.go.id/nara-qna` | `responses.json → negative_feedback` |
| **forward** | Bukan 4 intent di atas | "siapa presiden", "kenapa mitra ga bisa verifikasi NIK" | Lanjut ke BM25 gate (≥3.0) → hybrid search → RRF gate | BM25 + RRF 2-layer |

**Kenapa perlu 5 kelas?**
- Tanpa `positive_feedback`: "makasih" masuk forward → hybrid search → RRF rendah → ditolak dengan *"Maaf, saya tidak bisa menjawab..."* — awkward.
- Tanpa `negative_feedback`: "kamu ga membantu" masuk forward → hybrid search → LLM dengan system prompt ketat → malah kasih link QNA dengan nada formal — padahal harusnya empati dulu.
- Tanpa `capability` terpisah: LLM suka ngarang definisi palsu ("GC PBI = Ground Check Penggunaan Bahan Bakar Industri"). Template statis mencegah hal ini.

**Model:**
- **SGDClassifier + TF-IDF (185KB)** — pure Python, semua OS. Training dari `classifier_train.txt` (845 sampel), akurasi 98.1%, inferensi < 1ms
- **Keyword fallback** — auto aktif kalo scikit-learn gak terinstall. Akurasi: ~95%

**Training data:** `core/classifier_train.txt` — 478 baris, format:
```
__label__greeting halo
__label__greeting pagi nara
__label__capability kamu bisa apa
__label__positive_feedback makasih
__label__negative_feedback kamu tidak membantu
__label__forward siapa presiden
```

### 🧩 Multi-Part Split (E5 Semantic Boundary)

User sering nanya multiple hal dalam 1 chat — "cara daftar SOBAT dan aktivasi FASIH" atau "lupa password? cara reset?". Dulu cuma split pake regex konjungsi (`dan`, `serta`, `lalu`), tapi ada false positive:

| Query | Regex Split (dulu) | Seharusnya |
|-------|:------------------:|:----------:|
| "cara daftar SOBAT dan aktivasi FASIH" | ✅ Split (beda program) | ✅ Split |
| "cara daftar SOBAT dan ketentuannya" | ❌ Split padahal 1 konteks | ❌ Jangan split |
| "aktivasi FASIH bagaimana? kalau error?" | ❌ Gak split | ✅ Split |

**Solusi — 2 Layer Split:**

**Layer 1: Heuristic Split**
Split berdasarkan delimiter alami:
```
• Konjungsi: dan, serta, sedangkan, lalu, terus, trus,
  sementara itu, adapun, namun, tetapi, selanjutnya,
  pertama, kedua, ketiga
• Delimiter: ? diikuti kata, . sentence boundary, koma, titik koma
```

**Layer 2: E5 Semantic Merge**
Setelah heuristic split, tiap pasangan part dicek cosine similarity:
```python
vec_a = E5_encode(part_a)
vec_b = E5_encode(part_b)
sim = cosine_similarity(vec_a, vec_b)

if sim >= 0.78:
    MERGE → masih 1 konteks ("daftar SOBAT" + "ketentuannya" → 0.85)
else:
    SPLIT → beda intent ("verifikasi NIK" + "siapa presiden" → 0.77)
```

**E5 encode tiap part** — ini **reuse** dari pipeline yang udah jalan, jadi zero additional model cost.

**Contoh hasil final:**

| Query | Heuristic Split | Setelah E5 Merge | Hybrid Result |
|-------|:---------------:|:----------------:|:-------------:|
| "cara daftar SOBAT dan aktivasi FASIH" | [daftar SOBAT, aktivasi FASIH] | **split** (cosim 0.35) | ✅ 2 FAQ dicari |
| "cara daftar SOBAT dan ketentuannya" | [daftar SOBAT, ketentuannya] | **merge** (cosim 0.72) | ✅ 1 query utuh |
| "aktivasi FASIH? kalau error?" | [aktivasi FASIH, kalau error] | **split** (cosim 0.30) | ✅ 2 FAQ dicari |

---

### 🔄 Cascade Fallback

Hybrid search RRF udah lumayan, tapi ada kasus follow-up pendek yang jeblok:
```
User: "aktivasi FASIH gimana caranya?"  → skor hybrid 0.88 ✅
User: "linknya udah dicoba"             → skor hybrid 0.65 ❌ (terlalu pendek, gak nyambung ke FAQ)
```

**Solusi — Cascade Fallback:**

| Depth | Aksi | Threshold |
|:-----:|------|:---------:|
| 0 | Search dengan query original | RRF < 0.025 → depth 1 |
| 1 | **Concat** 1 query user sebelumnya + query saat ini → search ulang | RRF < 0.025 → depth 2 |
| 2 | **Concat** 2 query user sebelumnya + query saat ini → search ulang | RRF < 0.025 → **TOLAK** → 📩 QNA link |

> 🔑 **Poin penting:** Cascade reject berarti **LLM tidak pernah dipanggil**. Biaya token = 0. Yang terbuang cuma komputasi E5 encode + BM25 scoring — itu pun < 100ms di CPU.

**Contoh cascade:**
```
Query: "linknya udah dicoba"  → hybrid score 0.65 ❌
  ↓ depth 1 (concat 1 prev)
  "aktivasi FASIH gimana caranya? linknya udah dicoba"  → hybrid score 0.85 ✅
```

Cascade depth max 2 — cukup untuk handle follow-up natural tanpa bikin prompt terlalu panjang.

---

## 🆚 Perbandingan & Arsitektur Pipeline

### Saling Melengkapi: BM25 vs E5 vs Hybrid

BM25 dan E5 punya **kelemahan yang saling melengkapi**. Pake salah satu aja berarti mewarisi semua blindspot-nya.

| Skenario | BM25 sendiri | E5 sendiri | Hybrid RRF |
|----------|:------------:|:----------:|:----------:|
| User nanya "aktivasi FASIH" | ✅ Skor tinggi (exact match "FASIH") | ✅ Skor tinggi (paham konteks aktivasi) | ✅ Keduanya setuju → aman |
| User nanya "aktivasi FASIH" besoknya nanya "linknya udah dicoba" | ❌ Skor 0 (gak ada keyword overlap sama FAQ) | ❌ Skor rendah (query pendek, semantic drift) | ✅ Cascade fallback concat prev query → dapat konteks |
| User nanya "reset password FASIH" vs "lupa kata sandi FASIH" | ❌ Skor beda (password ≠ kata sandi) | ✅ Skor mirip (sinonim dipahami) | ✅ E5 angkat, BM25 bantu konfirmasi keyword "FASIH" |
| User nanya "error GC PBI" — padahal maksudnya GC PLN | ⚠️ Skor tinggi ke GC PBI (keyword match) | ⚠️ Skor mirip (pola kalimat sama, embedding berdekatan) | ✅ RRF average out — BM25 ke GC PBI, E5 ke GC PLN → top-5 masih include yang bener |
| User nanya "resep nasi goreng" | ✅ Skor 0 → reject bersih (BM25 < 3.0, tolak sebelum retrieval) | — (tidak sampai E5) | ✅ BM25 gate sudah nangkap |
| User nanya "siapa presiden indonesia" | ✅ Skor 0 → reject bersih (BM25 < 3.0) | — (tidak sampai E5) | ✅ BM25 gate sudah nangkap |

### 📊 Tabel Perbandingan

| Aspek | BM25 | E5-base | Hybrid (RRF) |
|-------|:----:|:-------:|:------------:|
| **Pendekatan** | Keyword overlap | Semantic vector | Ranking fusion |
| **Paham sinonim?** | ❌ | ✅ | ✅ |
| **Peka istilah teknis?** | ✅ (GC PBI, FASIH) | ⚠️ (kadang bias) | ✅ (ter cover BM25) |
| **GPU dibutuhkan?** | ❌ (CPU doang) | ⚠️ (CPU bisa, lambat) | — |
| **Kecepatan** | ⚡ sangat cepat | 🐢 lebih lambat | 🐢 mengikuti E5 |
| **Ukuran memori** | ~10 KB | ~278 MB | — |
| **Ketangguhan follow-up** | ❌ (kata kunci aja) | ⚠️ (lumayan) | ✅ + cascade |

### 🎯 Analogi Lengkap

```
scikit-learn CLF = resepsionis → sapa tamu, arahin ke bagian terkait
BM25     = petugas arsip → jago nyari dokumen pake kata kunci
E5       = kolega senior → hafal isi dokumen, nyari berdasarkan kesamaan topik
RRF      = manager → gabungin rekomendasi arsip + kolega buat ranking final
Cascade  = follow-up pintu belakang → "eh ini rombongan yang tadi udah masuk kan?"
```

### 💡 Kenapa gak pake model embedding / tool lain?

| Model / Tool | Alasan gak dipakai |
|-------|-------------------|
| **OpenAI text-embedding-3-small** | API key tambahan, biaya per query, latency jaringan |
| **BAAI/bge-base-en-v1.5** | Inggris doang, gak optimal untuk Indonesia |
| **Qwen2.5-embedding** | Baru, belum mature, komunitas kecil |
| **ChromaDB / LangChain** | Overkill untuk skala saat ini (113 FAQ) — setup overhead gak sebanding |
| **FastText (classifier)** | Butuh C++ compiler di Windows, numpy 2.x incompatible — diganti scikit-learn |

E5-base dipilih karena: **gratis, lokal, multilingual (Indonesia), 768D cukup untuk 113 FAQ, dan terbukti di berbagai benchmark retrieval.** Scikit-learn dipilih sebagai classifier karena: **pure Python, zero dependency, 97.4% accuracy, 185KB model.**

---

## 🔄 Replikasi / Custom Bot

| File | Wajib? | Keterangan |
|------|:------:|------------|
| `.env` | ✅ **Wajib** | Sesuaikan token, API key, model |
| `prompts/identity.json` | ✅ **Wajib** | Nama & role bot baru |
| `prompts/system.md` | ⬜ Opsional | Aturan main LLM |
| `prompts/greeting.md` | ⬜ Opsional | Template sambutan |
| `core/embedder.py` | ⬜ Opsional | Bisa ganti model hybrid search |
| `core/bm25.py` | ⬜ Opsional | Stopwords disesuaikan domain |
| `security/*.py` | ❌ **Jangan** | Proteksi built-in |

---

## 💻 Panduan Instalasi — Windows

<details>
<summary><b>Klik untuk lihat panduan Windows</b></summary>

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **Node.js** | v20 LTS (v24 mungkin bermasalah dengan puppeteer) |
| **RAM** | **Minimal 8GB** (disarankan 16GB kalau mau + Ollama lokal) |

### 1. Install Python

1. Buka [python.org/downloads](https://www.python.org/downloads/release/python-3119/)
2. Download **Windows installer (64-bit)**
3. ✅ Centang **Add Python to PATH** → Install Now
4. Verifikasi: `python --version`

### 2. Install Node.js

Download dari [nodejs.org](https://nodejs.org/) — pilih **v20 LTS**.

Verifikasi: `node --version` (harus v20.x.x)

### 3. Install Git & Clone

```cmd
winget install git.git
cd C:\Proyek
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 4. Buat file `.env`

```env
TELEGRAM_BOT_TOKEN=isi_token_telegram
CHATBOT_URL=http://localhost:8000/chat
GSHEET_CSV_URL=https://docs.google.com/spreadsheets/d/.../pub?...&output=csv

# LLM 1 — Utama
LLM_API_1=https://opencode.ai/zen/go/v1/chat/completions
LLM_API_KEY_1=sk-...
LLM_MODEL_1=deepseek-v4-flash

# LLM 2 — Cadangan
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-...
LLM_MODEL_2=deepseek-chat

# LLM 3 — Cadangan akhir (Ollama lokal)
LLM_API_3=http://localhost:11434/v1/chat/completions
LLM_API_KEY_3=***
LLM_MODEL_3=qwen2.5:1.5b

# Admin — skip anti-spam & daily limit
TRUSTED_CHAT_IDS=1267972859
```

### 5. Install Python Dependencies

```cmd
pip install -r requirements.txt
```

> **Catatan:** `sentence-transformers` akan download E5-base (~278MB) di first run.
> **scikit-learn classifier:** pure Python — gak perlu C++ compiler. Training auto dari `classifier_train.txt`.
> Semua dependency sudah diatur di `requirements.txt` — tinggal `pip install -r` aja.

### 6. Install Node.js Dependencies (WhatsApp Bridge)

```cmd
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
cd ..
```

### 7. Jalankan (5 Terminal)

**Skema arsitektur:**
```
Telegram ──> telegram_bot.py ──┐
                              ├──> server.py:8000 (E5 + BM25 + LLM)
WhatsApp ──> wa_handler.py:3001 ─┘                │
                ^                                 ├──> dashboard.py:8001 (Monitoring UI)
                │                                 │
         bridge.js:3000 (Chrome/WA Web)           │
```

**Terminal 1 — Server API (port 8000):**
```cmd
cd C:\Proyek\chatbot-qna
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Dashboard (port 8001):**
```cmd
cd C:\Proyek\chatbot-qna
python dashboard.py
```

**Terminal 3 — WhatsApp Handler (port 3001):**
```cmd
cd C:\Proyek\chatbot-qna
python wa_handler.py
```

**Terminal 4 — WhatsApp Bridge (port 3000):**
```cmd
cd C:\Proyek\chatbot-qna\whatsapp-bridge
node bridge.js
```
QR code muncul → scan pake WhatsApp > Linked Devices.

**Terminal 5 — Telegram Bot:**
```cmd
cd C:\Proyek\chatbot-qna
python telegram_bot.py
```

### 8. Start All (1 Klik)

Double-click `start-all.bat` — langsung buka 5 terminal + buka dashboard otomatis di browser.

### 9. Pindah ke PC Baru (1 Langkah + .env)

```cmd
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
pip install -r requirements.txt
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
```

Buat file `.env` (isi token), terus double-click `start-all.bat`. Selesai.

</details>

---

## 🐧 Panduan Instalasi — Linux

<details>
<summary><b>Klik untuk lihat panduan Linux</b></summary>

### 📋 Kebutuhan Sistem

| Komponen | Spesifikasi |
|----------|-------------|
| **OS** | Ubuntu 22.04+ / Debian 12+ (64-bit) |
| **Python** | 3.11 atau 3.12 |
| **Node.js** | v20 LTS |
| **RAM** | **Minimal 8GB** (disarankan 16GB kalau mau + Ollama lokal) |

> **Catatan WhatsApp Bridge:** `whatsapp-web.js` butuh Chrome/Chromium. Di Linux server tanpa GUI, jalanin `npx puppeteer browsers install chrome` setelah npm install.
> Untuk production, disarankan **Telegram Bot saja** tanpa WA bridge di Linux.

### 1. Install Python 3.11

```bash
# Ubuntu 22.04+
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-pip
```

Verifikasi:
```bash
python3.11 --version   # harus Python 3.11.x
```

### 2. Install Node.js v20

```bash
# Pake NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verifikasi:
```bash
node --version   # harus v20.x.x
npm --version
```

### 3. Install Git & Clone

```bash
sudo apt install -y git
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
```

### 4. Buat file `.env`

```env
TELEGRAM_BOT_TOKEN=isi_token_telegram
CHATBOT_URL=http://localhost:8000/chat
GSHEET_CSV_URL=https://docs.google.com/spreadsheets/d/.../pub?...&output=csv

# LLM 1 — Utama
LLM_API_1=https://opencode.ai/zen/go/v1/chat/completions
LLM_API_KEY_1=sk-...
LLM_MODEL_1=deepseek-v4-flash

# LLM 2 — Cadangan
LLM_API_2=https://api.deepseek.com/chat/completions
LLM_API_KEY_2=sk-...
LLM_MODEL_2=deepseek-chat

# LLM 3 — Cadangan akhir (Ollama lokal)
LLM_API_3=http://localhost:11434/v1/chat/completions
LLM_API_KEY_3=***
LLM_MODEL_3=qwen2.5:1.5b

# Admin — skip anti-spam & daily limit
TRUSTED_CHAT_IDS=1267972859
```

### 5. Install Python Dependencies

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-telegram-bot httpx sentence-transformers scikit-learn numpy python-dotenv easyocr requests flask rank-bm25
```

> **Catatan:** `sentence-transformers` akan download E5-base (~278MB) di first run.
> scikit-learn included by default — no extra setup needed

### 6. Install Node.js Dependencies (WhatsApp Bridge)

```bash
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
cd ..
```

### 7. Jalankan (5 Terminal)

**Skema arsitektur:**
```
Telegram ──> telegram_bot.py ──┐
                              ├──> server.py:8000 (E5 + BM25 + LLM)
WhatsApp ──> wa_handler.py:3001 ─┘                │
                ^                                 ├──> dashboard.py:8001 (Monitoring UI)
                │                                 │
         bridge.js:3000 (Chrome/WA Web)           │
```

**Terminal 1 — Server API (port 8000):**
```bash
cd chatbot-qna
source venv/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Dashboard (port 8001):**
```bash
cd chatbot-qna
source venv/bin/activate
python dashboard.py
```

**Terminal 3 — WhatsApp Handler (port 3001):**
```bash
cd chatbot-qna
source venv/bin/activate
python wa_handler.py
```

**Terminal 4 — WhatsApp Bridge (port 3000):**
```bash
cd chatbot-qna/whatsapp-bridge
node bridge.js
```
QR code muncul → scan pake WhatsApp > Perangkat Tertaut.

**Terminal 5 — Telegram Bot:**
```bash
cd chatbot-qna
source venv/bin/activate
python telegram_bot.py
```

### 8. Start All (1 Script)

Buat file `start.sh`:
```bash
#!/bin/bash
echo "=== Starting NARA Services ==="
cd "$(dirname "$0")"
source venv/bin/activate

gnome-terminal -- bash -c "python -m uvicorn server:app --host 0.0.0.0 --port 8000; exec bash"
gnome-terminal -- bash -c "source venv/bin/activate && python dashboard.py; exec bash"
gnome-terminal -- bash -c "source venv/bin/activate && python wa_handler.py; exec bash"
gnome-terminal -- bash -c "cd whatsapp-bridge && node bridge.js; exec bash"
gnome-terminal -- bash -c "source venv/bin/activate && python telegram_bot.py; exec bash"
```

Kasih izin:
```bash
chmod +x start.sh
```

### 9. Pindah ke Server Baru

```bash
git clone https://github.com/toha518/chatbot-qna.git
cd chatbot-qna
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd whatsapp-bridge
npm install
npx puppeteer browsers install chrome
```

Buat `.env`, terus `./start.sh`. Selesai.

</details>

---

## ✅ Verifikasi

### Cek server:
```bash
curl http://localhost:8000/health
```

Output:
```json
{
  "status": "ok",
  "total_qna": 100+,
  "engine": "hybrid (E5+BM25)",
  "source": "Google Sheets",
  "active_sessions": 0,
  "query_stats": {
    "total": 85,
    "accepted": 62,
    "rejected": 20,
    "greetings": 3,
    "errors": 0
  }
}
```

### Cek bot Telegram:
Buka Telegram, cari bot Anda, kirim pesan.

### Cek WhatsApp:
Chat nomor yang discan — bot harus merespon dengan typing indicator.

---

## 🔗 API Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/health` | GET | Status server, total Q&A, active sessions, query stats |
| `/log-stats` | GET | Statistik query log (total, accepted, rejected, errors) |
| `/chat` | POST | Kirim pertanyaan → dapat jawaban dari AI |
| `/start` | POST | Inisialisasi sesi baru untuk user |
| `/stop` | POST | Akhiri sesi chat (dapat durasi) |
| `/reload` | POST | Reload FAQ dari Google Sheets manual |
| `/history` | GET | Daftar semua sesi chat |
| `/history/{chat_id}` | GET | Detail chat per user |

### Contoh `/chat`

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pertanyaan": "Cara daftar SOBAT", "chat_id": "12345"}'
```

Response:
```json
{
  "jawaban": "Untuk mendaftar SOBAT...",
  "skor": 0.89
}
```

### Contoh `/log-stats`

```bash
curl http://localhost:8000/log-stats
```

Response:
```json
{
  "total": 120,
  "accepted": 95,
  "rejected": 22,
  "greetings": 3,
  "errors": 0,
  "file": "C:\\Proyek\\chatbot-qna\\query_log.jsonl",
  "size_kb": 4.2
}
```

---

## 📊 Logging & Evaluasi

Setiap request user dicatat otomatis ke **dual storage**:

| Storage | File | Fungsi |
|---------|------|--------|
| **JSONL** | `query_log.jsonl` | Debug real-time — `tail -f` langsung keliatan |
| **SQLite** | `query_log.db` | Analytics jangka panjang — SQL query instant |

### Format Log (21 field per entry)

```json
{
  "waktu": "2026-06-01 00:15:30",
  "chat_id": "1267972859",
  "pertanyaan": "Kenapa mitra ga bisa verifikasi NIK",
  "clf_domain": "forward",
  "clf_confidence": 0.876,
  "clf_mode": "scikit-learn",
  "rrf_score": 0.0331,
  "e5_top": 0.86,
  "bm25_raw": 10.7,
  "top5_faq": ["Verifikasi NIK Gagal", "Email aktivasi"],
  "gate": "ANSWER",
  "gate_detail": "",
  "dijawab": true,
  "jawaban": "Coba cek dulu...",
  "jawaban_length": 342,
  "llm_model": "llama-3.3-70b-versatile",
  "llm_provider": "provider 1",
  "llm_time_ms": 850,
  "multi_part": false,
  "session_baru": false,
  "error": ""
}
```

### Gate Labels

| Gate | Arti |
|------|------|
| `CLF_GREETING` / `CLF_CAPABILITY` | CLF deteksi → respon langsung |
| `CLF_POSITIVE_FEEDBACK` | "makasih" → "Sama-sama! 😊" |
| `CLF_NEGATIVE_FEEDBACK` | "ga membantu" → link QNA |
| `OUT_OF_CONTEXT` | RRF < 0.018 → tolak |
| `CASCADE_QNA` / `MULTI_PART_QNA` | RRF 0.018-0.025 → link QNA |
| `ANSWER` | RRF ≥ 0.025 → LLM jawab |

### Built-in Analytics (`GET /log-stats`)

```json
{
  "period": "7 hari",
  "total_logs": 342,
  "unique_users": 12,
  "avg_rrf_score": 0.0241,
  "by_gate": {"ANSWER": 200, "CLF_GREETING": 80, ...},
  "by_clf": {"forward": 250, "greeting": 82, ...}
}
```

### Rotasi
- **JSONL**: dirotate saat ~500KB → file lama ditimestamp
- **SQLite**: gaperlu rotasi — query data historis langsung

### Chat History (Per-User)

Tersimpan di SQLite (`chatbot.db`) — akses via:
- `GET /history` — list semua sesi
- `GET /history/{chat_id}` — detail per user

---

## ❓ FAQ

<details>
<summary><b>Klik untuk lihat FAQ</b></summary>

**Q:** Kok jawabannya gak nyambung?

**A:** Bisa jadi FAQ database belum mencakup topik tersebut. Update Google Sheets lalu POST ke `/reload`.

---

**Q:** Error "Address already in use"?

**A:** Port 8000 masih dipakai. Cek:
```cmd
netstat -ano | findstr :8000    # Windows
sudo lsof -i :8000              # Linux
```

---

**Q:** Bikin bot dengan identitas beda?

**A:** Ganti `prompts/identity.json` + `.env` — gak perlu edit Python.

---

**Q:** Chat history ilang?

**A:** History di `chatbot.db`. Di-ignore git, aman.

---

**Q:** Bisa pake LLM model lain?

**A:** Bisa. Atur `LLM_API_1`, `LLM_API_KEY_1`, `LLM_MODEL_1` di `.env`.

---

**Q:** WhatsApp bridge-nya gak muncul QR?

**A:** Pastikan `node bridge.js` jalan dari folder `whatsapp-bridge/`. Cek log — harus ada `[BM25]` waktu ada chat. Kalo score selalu 999 → restart server.

---

**Q:** BM25 score kok 999?

**A:** BM25 gagal di-build. Restart server (`python -m uvicorn server:app ...`). Cek log startup — harus ada `[RELOAD] N Q&A loaded` + BM25 index kebangun otomatis.

---

**Q:** Error "Browser was not found at the configured executablePath"?

**A:** Chrome 146 belum terdownload. Jalanin: `npx puppeteer browsers install chrome` di folder `whatsapp-bridge/`.

---

**Q:** Mau offline pake CPU doang?

**A:** Install Ollama, pull `gemma3n:e4b`, ubah `.env` ke `http://localhost:11434/v1/chat/completions`.

---

**Q:** Cara reset daily limit?

**A:** Otomatis reset tiap ganti hari (WIB). Restart server juga reset.

---

**Q:** Siapa trusted user?

**A:** User di `TRUSTED_CHAT_IDS` di `.env` — skip anti-spam & daily limit.

---

**Q:** Bot WA error "tidak ada jawaban"?

**A:** Cek terminal wa_handler. Biasanya karena `requests` belum diinstall (`pip install requests`) atau URL double path (`/chat/chat`). Pull terbaru + restart.

---

**Q:** Pertanyaan di luar BPS masih tembus?

**A:** Cek terminal server — apakah ada log `[BM25]`? Kalo tidak ada → BM25 gagal build (restart). Kalo score 999 → sama. Kalo score 0 tapi masih tembus → laporkan.

</details>

---

## 🖥️ Dashboard

Dashboard web untuk monitoring, debugging, dan manajemen Nara. Buka di browser: [http://localhost:8001](http://localhost:8001)

> **Jalankan:** `python dashboard.py` (paralel dengan `server.py`)

| Tab | Fungsi |
|-----|--------|
| 📊 **Overview** | Statistik query, distribusi Gate & CLF, answered rate |
| 📝 **Query Log** | 22 kolom dari `query_log.db`, search + filter (gate, CLF, source, status), column visibility toggles, pagination 50/page |
| 💻 **Live Terminal** | Streaming query real-time (`tail -f`), polling 3 detik |
| 📈 **Analytics** | RRF trend per jam, Queries per Hour, LLM Model Usage (charts) |
| 🖥️ **System Health** | Status 4 service (Server API, WA Handler, Bridge, Telegram Bot) + tombol Start All / Stop All |
| 🏆 **Top FAQ** | FAQ paling sering muncul + kategori dari spreadsheet (SOBAT, GC PBI, dll) |

### Fitur Tambahan
- 🔗 **Quick links** sidebar: Database FAQ, Nara QnA, Data QnA
- 🌙 **Dark/Light mode** — toggle di top bar, auto-detect OS preference
- 📱 **Responsive** — sidebar overlay di mobile, tabel scrollable
- 🏷️ **Source tracking** — setiap query di-tag `wa` / `telegram` / `api`
- 📂 **Column toggles** — pilih kolom mana yang ditampilkan, state disimpan di localStorage

### Tech Stack Dashboard
- **Backend:** FastAPI + SQLite (`query_log.db`) + httpx (health check)
- **Frontend:** Vanilla HTML/CSS/JS + Chart.js 4.4 + Inter font (Google Fonts)
- **Design system:** PlayStation-inspired — flat no-shadow, `#0070d1` primary, 8px cards, `9999px` pill buttons

---

## 📜 Riwayat Versi

<details>
<summary><b>Klik untuk lihat riwayat lengkap</b></summary>


---

---

#### v2.5.1 — 2026-06-03

**Context-Aware Feedback + Positive Response Update**

**Changed**
- **Positive feedback response** diperbarui: "Senang bisa membantu, terima kasih telah menggunakan layanan Nara 😊"
- **Context-aware feedback:** `positive_feedback` / `negative_feedback` hanya direspon jika session punya riwayat CLF `forward` (user pernah bertanya).
  - `positive_feedback` tanpa konteks → treat sebagai greeting.
  - `negative_feedback` tanpa konteks → treat sebagai forward (domain check normal).
  - Tracking via `session_has_forward` dict di `security/session.py`.
- File diubah: `prompts/responses.json`, `server.py`, `security/session.py`

---

#### v2.5.0 — 2026-06-02

**BREAKING: Domain Gate RRF Dihapus**
- **RRF tidak lagi sebagai gate** — RRF hanya untuk ranking fusion E5+BM25. Skor RRF berkutat di rentang sempit (0.018-0.033) karena K=60, membuatnya tidak efektif sebagai domain filter
- Gate label `OUT_OF_CONTEXT`, `CASCADE_QNA`, `CASCADE_FAILED` dihapus
- **BM25 3-tier gate** menggantikan pipeline sebelumnya:
  - `< 3.0` → `OOC_BM25` (tolak total)
  - `3.0-4.9` → `BM25_BORDERLINE` (QNA link — ada sinyal BPS samar)
  - `≥ 5.0` → lanjut hybrid search + LLM
- **Cascade BM25 depth 3** — concat 1-3 prev query depth, hitung ulang BM25. Cascade lolos ke **hybrid search** (E5+BM25 RRF), bukan cuma BM25. Depth 3 berdasarkan NVIDIA (3-5 turns), Chatnexus (sliding window 3), MTRAG paper (3-5 turns).
- **E5 similarity guard** — setelah cascade BM25 ≥ 5, cek E5 cosine similarity antara query asli vs prev query. Jika < 0.70 → topic drift → cascade skip, jatuh ke 3-tier gate. Mencegah false positive cascade. Biaya: ~0ms (query_vec sudah ada, prev query di LRU cache).

**Fixed**
- **Cascade compounding bug** — `req.pertanyaan` sebelumnya dimodifikasi oleh cascade, menyebabkan concat berantai di follow-up berikutnya. Sekarang `_cascade_query` terpisah.

**Added**
- **`bm25_gate` field** di query log + dashboard — nilai max BM25 dari semua FAQ yang dipakai gate. Dua kolom terpisah: `bm25_gate` (gate) + `bm25_raw` (BM25 FAQ top-RRF)
- **Dashboard version auto-detect** — baca dari `git describe --tags`, fallback file `VERSION`. Update otomatis setelah `git pull` + restart
- **Personality Nara** — "pendengar yang baik dan perhatian"
- **Ranked context format** — FAQ diberi label `⭐️ PERINGKAT 1 (JAWABAN UTAMA)` s.d. `PERINGKAT 5`. Berbasis riset Galileo AI RAG prompting + Thread of Thought (ThoT) + Chain-of-Note (CoN)
- **Multi-part LLM routing** — tiap part di multi-part query sekarang di-routing melalui LLM penuh, bukan copy-paste FAQ
- **`_display_query` logging** — log mencatat teks asli dari user (termasuk koma, spasi, dll), bukan teks yang sudah dinormalisasi

**Changed**
- **CLF training data rebuild** — 478 → **845 samples** (+193 greeting, +94 capability), **zero cross-domain overlap**. Sumber: production logs + IndoNLU + Kaggle + UNSRI Chatbot dataset. Training accuracy 98.1%, 5-fold CV 87.9%. Fix 10 item overlap dihapus dari `forward`
- **Greeting prompt simplified** — `greeting.md` 13→6 baris
- **System prompt refined** — aturan ranking eksplisit: pilih FAQ yang PALING COCOK, jangan jawab generik jika ada solusi spesifik
- **Personality & identity updates** — `identity.json`, `system.md`, `greeting.md` semua disederhanakan
- **`responses.json`** — `context_header` dipindah ke `server.py` sebagai f-string (bukan user-facing template)

**Fixed**
- **`hybrid_search()` unpack error** — multi-part split cuma unpack 3 values, fungsi return 4 → 500 Internal Server Error
- **Comma normalization** — koma dihapus di input sanitasi (`,` → spasi) untuk konsistensi E5 embedding. `_raw_query` disimpan terpisah untuk multi-part comma detection
- **Multi-part regex** — `[,;]\s*` + konjungsi lemah dihapus. Hanya split di konjungsi kuat + koma + titik + tanda tanya
- **Dashboard column toggles** — fix duplikasi `data-col` index, realign 25 kolom 1:1 ke DT_HEADERS
- **top5_faq** — sekarang menampilkan ranking label: `#1`, `#2`, ...

**Docs**
- README instalasi Windows — update ke 5 terminal (include dashboard), pakai `pip install -r requirements.txt`
- BM25 section — jelasin dual role + 3-tier gate + cascade BM25
- Pipeline flowchart — update ke BM25 3-tier + cascade + hapus RRF gate
- SETUP-WINDOWS.md — rewrite lengkap, tambah dashboard + pindah PC baru

**Housekeeping**
- `requirements.txt` — hapus `fasttext`, `google-generativeai`, `ollama` (tidak dipakai)
- `.gitignore` — tambah `faq_categories.json`
- `core/intent_classifier.py` — rename `FT_` → `CLF_` vars, model path `domain_filter.ftz` → `intent_model.pkl`
- `VERSION` file — single source of truth untuk versi

#### v2.4.2 — 2026-06-02

**Added**
- **`bm25_gate` field** di query log + dashboard — nilai max BM25 dari semua FAQ yang dipakai gate. Dua kolom terpisah: `bm25_gate` (gate) + `bm25_raw` (top-RRF)
- **Dashboard version auto-detect** — baca dari `git describe --tags`, fallback ke file `VERSION`. Update otomatis setelah `git pull` + restart
- **Personality Nara** — "pendengar yang baik dan perhatian" di `identity.json`
- **Ranked context format** — FAQ diberi label `⭐️ PERINGKAT 1 (JAWABAN UTAMA)` s.d. `PERINGKAT 5`. `context_header` di `responses.json` diperkuat: LLM diinstruksikan memilih peringkat yang PALING COCOK, dilarang jawab generik jika ada solusi spesifik. Berbasis riset Galileo AI RAG prompting + Thread of Thought (ThoT) + Chain-of-Note (CoN)
- **Multi-part LLM routing** — tiap part di multi-part query sekarang di-routing melalui LLM (system prompt + ranked context + call_llm), bukan copy-paste mentah dari FAQ. Respons konsisten antara single-query dan multi-part

**Changed**
- **CLF training data rebuild** — 478 → **845 samples** (+193 greeting, +94 capability), **zero cross-domain overlap**. Sumber: NARA production logs + IndoNLU + Kaggle + UNSRI University Chatbot dataset. Akurasi training 98.1%, 5-fold CV 87.9%. Fix 10 item overlap dihapus dari `forward`
- **Greeting prompt simplified** — `greeting.md` 13→6 baris (capability ditangani template statis CLF)
- **System prompt refined** — lebih tegas di QNA link rule

**Fixed**
- **`hybrid_search()` unpack error** — multi-part split cuma unpack 3 values, padahal fungsi return 4. Bikin 500 Internal Server Error saat multi-part query
- **Comma normalization** — koma dihapus di input sanitasi (`,` → spasi) sebelum E5 encoding, biar vektor embedding konsisten. `_raw_query` disimpan terpisah untuk multi-part comma detection
- **Multi-part regex** — `[,;]\s*` + konjungsi lemah dihapus. Hanya split di `dan`, `serta`, `sedangkan`, `namun`, `tetapi`, `tapi`, `,`, `.`, `?`. E5 tetap yang menentukan merge/split final
- **Dashboard column toggles** — fix duplikasi `data-col` index + realign 25 kolom ke DT_HEADERS 1:1

**Docs**
- **README instalasi Windows** — update ke 5 terminal (include dashboard), pakai `pip install -r requirements.txt`
- **BM25 section** — jelasin dual role: `bm25_gate` (max semua FAQ) vs `bm25_raw` (top-RRF), keduanya di-log terpisah
- **SETUP-WINDOWS.md** — rewrite lengkap, tambah step dashboard + petunjuk pindah PC baru

**Housekeeping**
- `requirements.txt` — hapus `fasttext`, `google-generativeai`, `ollama` (gak dipake)
- `.gitignore` — tambah `faq_categories.json` (auto-generated)
- `core/intent_classifier.py` — rename `FT_` → `CLF_` vars, model path `domain_filter.ftz` → `intent_model.pkl`

---

#### v2.4.1 — 2026-06-01

**Performance (7 optimasi)**
- **E5 embedding cache** (`core/embedder.py`) — LRU 128 query, cache hit = 0ms (vs 50-100ms encode)
- **BM25 → `rank_bm25` library** (`core/bm25.py`) — C-optimized scoring, 35 baris kode lebih ringkas
- **Google Sheets non-blocking** (`server.py`) — `asyncio.to_thread()` biar gak freeze server saat reload 10-menit
- **Logging non-blocking** (`core/query_logger.py`) — JSONL + SQLite write via daemon thread (hemat ~10-25ms/request)
- **Lazy SQLite init** (`core/query_logger.py`) — `_ensure_sqlite()` gak bikin side-effect pas module import
- **Regex compile → module level** (`server.py`) — `EMOJI_RE` compiled sekali, bukan per request

**Domain Filter Overhaul**
- **BM25 threshold ≥ 3.0** — jadi domain gate sebelum hybrid search (dari analisis 100+ query production)
- **Centroid E5** — dihitung & di-log ke `query_log.db` untuk analytics (bukan gate)
- **2-layer gate**: BM25 threshold → hybrid search RRF → ANSWER/OOC/CASCADE
- **Kolom `centroid_sim`** di `query_log.db` + dashboard Query Log
- **Kolom `source`** — tracking `wa` / `telegram` / `api` untuk setiap query

**Dependencies**
- `rank-bm25>=0.2.2` — baru, ganti implementasi BM25 manual

---

#### v2.4.0 — 2026-06-01

**Added**
- **🖥️ Dashboard Web UI** — monitoring, debugging, dan manajemen Nara via browser
  - 📊 Overview: statistik query, distribusi Gate & CLF, answered rate
  - 📝 Query Log: 22 kolom dari `query_log.db`, search + filter (gate, CLF, source, status, search teks), column visibility toggles, pagination 50/page
  - 💻 Live Terminal: streaming real-time query, polling 3 detik
  - 📈 Analytics: RRF score trend per jam, Queries per Hour, LLM Model Usage (Chart.js)
  - 🖥️ System Health: monitoring 4 service runtime + tombol Start All / Stop All
  - 🏆 Top FAQ: FAQ terpopuler + kategori dari spreadsheet
  - 🔗 Quick links: Database FAQ, Nara QnA, Data QnA (shortlink BPS)
- **🏷️ Source tracking** — setiap query di-tag `wa` / `telegram` / `api`
  - Kolom `source` baru di `query_log.db` + JSONL
  - `wa_handler.py` & `telegram_bot.py` kirim source ke `server.py`
  - Dashboard: filter & badge by source
- **Telegram Bot health endpoint** — port 3002 (threaded HTTP server)
- **FAQ Categories** — `faq_categories.json` auto-save dari spreadsheet, dipake dashboard Top FAQ
- **Favicon** — chatbot AI bubble icon
- **🌙 Dark/Light mode** — toggle + auto-detect OS preference + localStorage
  - Full dual-mode via CSS `--ps-*` token override (`[data-theme="dark"]`)
- **📱 Full responsive** — sidebar overlay mobile (≤768px), tabel scrollable, compact layout (≤480px)
- **🏗️ Design system** — PlayStation-inspired (clean, flat, no-shadow, `#0070d1` primary, `8px` cards, `9999px` pill CTAs)

**Changed**
- `start-all.bat` — update port & label

**Files**
- `dashboard.py` — baru (FastAPI, port 8001)
- `templates/dashboard.html` — baru (1447 baris, vanilla HTML/CSS/JS)
- `templates/favicon.svg` — baru
- `core/query_logger.py` — `source` column + migrasi ALTER TABLE
- `server.py` — `ChatRequest.source` param + 8 `log_query()` calls
- `wa_handler.py` — `payload["source"] = "wa"`
- `telegram_bot.py` — health server thread (port 3002) + `source: "telegram"`
- `core/embedder.py` — save `faq_categories.json` on reload

---

#### v2.3.1 — 2026-05-31

**Added**
- **QNA Form Link** — `http://s.bps.go.id/nara-qna` untuk pertanyaan domain BPS tapi belum ada di FAQ
- **scikit-learn Intent Classifier** — ganti FastText → SGDClassifier + TF-IDF (pure Python, 185KB, 97.4% accuracy)
  - Training dari `classifier_train.txt` (478 baris, 5 kelas)
  - Zero C++ compiler dependency — auto-train di semua platform
- `responses.json`: 3 template baru — `rejection_out_of_context`, `rejection_no_answer`, `capability` (statis)
- **positive_feedback & negative_feedback detection** — 2 kelas baru classifier:
  - `positive_feedback`: "makasih", "ok", "sip", "mantap" → "Senang bisa membantu, terima kasih telah menggunakan layanan Nara 😊"
  - `negative_feedback`: "kamu tidak membantu", "jelek" → link QNA form
  - Keduanya respon template statis (skip LLM, 0ms, $0)
- System prompt diperkuat — checklist topik BPS + larangan ngarang definisi

**Changed**
- **Semua threshold pake RRF score** (bukan E5 atau BM25 doang)
- **BM25=0 di RRF fusion di-skip** — cegah ranking noise
- **Merge threshold multi-part**: `0.55 → 0.78` — cegah false merge
- **Capability → template statis** — gak panggil LLM (hemat token cost)
- **Personality pindah ke identity.json** — `{personality}` placeholder
- Emoji dibebaskan — hapus batasan di greeting.md & system.md
- **Hapus semua hardcode daftar topik** — semua dari `identity.json`
- **Scikit-learn ganti FastText** — pure Python, zero C++ compiler, akurasi 97.4%

**Fixed**
- LLM ngarang definisi "GC PBI = Penggunaan Bahan Bakar Industri" — capability template statis

**Docs**
- README: Domain Filter RRF-based + QNA Form Link + scikit-learn classifier

---

#### v2.3.0 — 2026-05-30

**Added**
- **FastText greeting & capability detector** — dual-mode classifier:
  - Primary: FastText model (4MB, <0.5ms inferensi) — jalan di Linux/VPS
  - Fallback: keyword regex (auto aktif di Windows, akurasi test 24/25=96%)
  - FastText dulu di pipeline, sebelum hybrid search. Greeting/capability langsung respon, skip retrieval & LLM
- `core/fasttext_filter.py` — FastText wrapper (load/train/classify) + keyword fallback
- `core/fasttext_train.txt` — 215 baris training data (50 greeting, 35 capability, 130+ forward)
- `core/domain_filter.ftz` — pre-trained FastText model (4MB, load instant)
- `requirements.txt` — file dependencies resmi
- **Multi-part split E5 Semantic Boundary** — 2 layer:
  - Layer 1: Heuristic split (konjungsi + delimiter `?` `.` `,` `;`)
  - Layer 2: E5 cosim antar part ≥ 0.55 → merge (1 konteks), < 0.55 → split (beda intent)
  - Fix false split "daftar SOBAT dan ketentuannya" (cosim 0.72 → merge)
- README: flow chart FastText step, tabel LLM dipanggil hanya saat top_score >= 0.82

**Changed**
- **BM25 domain filter dihapus** — hybrid search (E5+BM25 RRF) + cascade fallback sekarang jadi domain filter otomatis.
  Query di luar BPS -> E5 cosim rendah + BM25 0 -> top_score < 0.82 -> cascade reject. **LLM tidak dipanggil** (zero cost token)
- Pipeline: regex greeting + BM25 filter -> FastText classifier + hybrid cascade
- Flow chart: step 3 FastText greeting/capability -> step 5 hybrid search + domain filter
- Tech stack: BM25 filter -> FastText + Hybrid Cascade
- Security layer 4: BM25 -> FastText, layer 5: hybrid threshold -> hybrid + domain filter

**Removed**
- `core/domain_filter.py` (E5 template approach — rawan false positive "siapa presiden" -> capability)
- FAQ sim layer (redundan — hybrid score sudah mencakup E5 + BM25)
- BM25 sebagai domain filter (sekarang hanya sebagai hybrid leg)

**Fixed**
- Python 3.12 + numpy 2.x compatibility — auto fallback keyword di Windows
- Keyword false positive: "p" match "presiden", "min" match "admin", "mas" match "masalah"
  -> word boundary regex \b untuk single tokens
- Pipeline urutan: FastText duluan, FAQ sim setelah (biar "hi"/"haloo" gak kena cascade reject)
- `history` undefined: baris `init_session()` kehapus saat replace block
- **OCR 500 char limit** — OCR gambar gak kena potong 500 karakter. Telegram & WA kirim flag `is_ocr: True`, server skip character limit kalo request dari OCR

**Dependencies**
- Tambah `fasttext` (Linux) / `fasttext-wheel` (Windows)

---
#### v2.2.0 — 2026-05-29

**Added**
- **Hybrid retrieval** E5+BM25 via RRF fusion — BM25 keyword + E5 semantic digabung pake Reciprocal Rank Fusion
- `get_bm25_scores_all()` — BM25 return score per-doc buat hybrid
- `hybrid_search()` — fungsi baru di embedder, RRF dengan K=60
- Kategori sebagai **metadata terpisah** — gak ikut di-embedding, similarity murni konten
- `prompts/responses.json` — single source of truth untuk SEMUA user-facing text
- **Cascade Fallback** — hybrid score < 0.82? concat 1-2 query user sebelumnya, search ulang. depth max 2. Fix follow-up pendek kayak "di dtsen juga udah sesuai"

**Changed**
- top_k: 3 → 5 (distribusi hybrid lebih variatif)
- `/health` → engine: `hybrid (E5+BM25)`
- Greeting prompt: sekarang menyebutkan nama, role, dan topik yang dikuasai
- Multi-part split flowchart: BM25 + E5 → BM25 domain + hybrid search
- Tabel "Perbedaan Format Pesan Telegram vs WhatsApp" dihapus dari README
- Contoh `total_qna` di health response: 79 → 100+
- Flowchart step 7: cascade fallback detail (depth 1-2)
- Badge: `E5-base` → `Hybrid (E5+BM25)`

**Refactor**
- **Zero hardcode prompt** — semua teks statis di .py dipindah ke `prompts/responses.json`
  - server.py, telegram_bot.py, wa_handler.py, security/rate_limiter.py
  - Cukup edit `prompts/responses.json` untuk ubah semua pesan
- `load_responses()` di `core/llm.py` — helper buat load responses.json
- Greeting fallback di `server.py`: bacanya dari `prompts/identity.json` + `responses.json`

**Docs**
- Flowchart step 6 di-update: multi-part split → hybrid search
- Flowchart step 7 di-update: HYBRID RETRIEVAL + cascade fallback
- Tech Stack: Semantic Search → Hybrid Retrieval
- Lisensi: Apache 2.0 → Proyek internal BPS

---

#### v2.1.1 — 2026-05-26

**Fixed**
- Akronim dipisah jadi referensi, bukan bagian dari daftar topik utama
- Greeting detection pake prefix matching — `"haloo"`, `"pagii"`, `"helo"` tetap terdeteksi
- Korupsi server.py setelah edit beruntun

---

#### v2.1.0 — 2026-05-26

**Added**
- Intro detection: `"kamu bisa apa?"`, `"siapa kamu?"` langsung pake greeting prompt (skip E5/BM25)
- File referensi akronim terpisah `prompts/acronyms.md`

---

#### v2.0.0 — 2026-05-26

**Added**
- Rebrand total: **Cici Anova → NARA (NextGen AI Response Agent)**
- Personality system di `prompts/system.md` — Nara si IT Support sabar & step-by-step
- Command handler WhatsApp: `/start`, `/help`, `/topics`, `/stop`
- WA watchdog notifikasi session expired via bridge `/send`
- WA image processing indicator "⏳ Memproses gambar..."
- Foto + caption di Telegram diarahkan ke handler gambar (bukan handler teks)

**Changed**
- Identity, role, gender bot berubah total (nama, persona, domain framing)

**Fixed**
- WA bold: `**text**` → `*text*` (sekarang bold di WA)
- Semua sisa string "Cici Anova" di 10 file dihapus total
- Emoji rule relax — bebas emoji
- Pesan "Memproses gambar..." di WA dibiarkan (gak dihapus, hindari "Pesan telah dihapus")

**Docs**
- Backronym NARA, FAQ rapi, RAM 8GB, Linux guide selengkap Windows

---

#### v1.0.0 — 2026-05-25/26

**Added**
- BM25 hybrid domain filter — keyword overlap, zero-dependency
- E5-base semantic search (hybrid RRF dengan BM25)
- Evaluasi logging (`query_log.jsonl`) — BM25 score, status, jawaban tiap query
- Multi-part query split — pertanyaan dengan "dan", "serta" dipisah otomatis
- WA typing indicator (`sendStateTyping`)
- WA image support — detect + OCR via EasyOCR
- Telegram image processing "⏳ Memproses gambar..." + auto-hapus
- WA watchdog notif session expired via bridge
- Daily limit 50→25 (perintah Owner)
- Resureksi repo: WA bridge + start-all 4 terminal

**Fixed**
- Python import trap — `build_bm25()` pake list kosong
- WA handler double path bug (`/chat/chat`)
- WA bridge kirim pesan biasa, bukan reply
- top_k tuning: 3→5→3 setelah embedding kategori
- BM25 stopwords — filter angka-only
- E5 score threshold 0.82 sebelum LLM
- Prompt strict — HANYA data referensi, temperature=0.1
- Encoding UTF-8 fix untuk Windows (cp1252)
- `scores.argmax()` wrong index fix
- Puppeteer `--single-process` (LifecycleWatcher crash)

---

#### v0.4.0 — 2026-05-21

**Added**
- Gemini 2.5 Flash sebagai opsi free LLM
- Daily chat limit 100/user/hari, reset otomatis
- `TRUSTED_CHAT_IDS` dari `.env` — admin skip security
- LLM failover chain sampai 20 provider

**Fixed**
- Rate limiter duplikat di telegram_bot.py
- Session rest 6 jam (redundan)
- Error logging API response sebelum akses `choices`

---

#### v0.3.0 — 2026-05-20

**Added**
- 6-layer security: sanitasi input, anti-spam, daily limit, BM25 filter, E5 threshold, session watchdog
- Credit: dibuat dan dikelola oleh Syahrul Toha Saputra
- Failover chain: 3→10 provider
- Logging sukses/gagal tiap provider LLM

**Fixed**
- Deteksi otomatis Ollama lokal
- max_tokens: 500→2000 — jawaban gak kepotong
- Fallback plain text kalo markdown error di Telegram
- Rate limiter duplikat

---

#### v0.2.0 — 2026-05-19

**Added**
- Refactor modular: `core/`, `prompts/`, `security/`
- EasyOCR untuk screenshot/image
- LLM failover: 3 provider backup chain
- ParseMode.MARKDOWN di Telegram — bold/italic tampil

**Fixed**
- TOP_K: 5→3 — hemat token
- OCR: hapus `paragraph=True` — format output beda
- Import `ParseMode` ketinggalan
- Rename DB: `cici_anova.db` → `chatbot.db`
- Rename kolom: `pertanyaan→kendala`, `jawaban→solusi`

---

#### v0.1.0 — 2026-05-18 — Rilis Perdana

**Added**
- FastAPI server + Telegram bot
- OpenCode Go: deepseek-v4-flash (thinking off)
- LLM config dari `.env` (DEEPSEEK_* → LLM_*)
- Anti-spam rate limit: 5 chat/menit
- 500 karakter limit per chat
- Input sanitasi + media filter
- Chat history limit: 20→10
- `.gitignore` + CLEANED history (token aman)

</details>

---

## 📞 Kontak & Dukungan

Dibuat dan dikelola oleh **Syahrul Toha Saputra** — Pengembang & Arsitek Sistem.

Untuk update, fitur baru, atau laporan error, hubungi tim teknis BPS Provinsi Kepulauan Bangka Belitung.

---

## 📄 Lisensi

Proyek internal BPS Provinsi Kepulauan Bangka Belitung.

---

<p align="center">
  <sub>© 2026 — Badan Pusat Statistik Provinsi Kepulauan Bangka Belitung</sub>
</p>
