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

- [✨ Fitur](#-fitur)
- [📸 Tangkapan Layar](#tangkapan-layar)
- [🛠️ Tech Stack](#tech-stack)
- [🔒 Security & Proteksi](#-security--proteksi)
- [🧠 Arsitektur Modular](#-arsitektur-modular)
- [🔄 Replikasi / Custom Bot](#-replikasi--custom-bot)
- [💻 Panduan Instalasi — Windows](#-panduan-instalasi--windows)
- [🐧 Panduan Instalasi — Linux](#-panduan-instalasi--linux)
- [🔗 API Endpoints](#-api-endpoints)
- [📊 Logging & Evaluasi](#-logging--evaluasi)
- [🖥️ Dashboard](#-dashboard)
- [❓ FAQ](#-faq)
- [📜 Riwayat Versi](#riwayat-versi)
- [📞 Kontak & Dukungan](#kontak-dukungan)


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
| **Domain Gate** | BM25 3-tier — <3 tolak, 3-4.9 QNA link, ≥5 hybrid search. Cascade BM25 depth 3 + E5 similarity guard (cosim ≥0.70 cegah topic drift) |
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
| 🧠 **Domain Gate (BM25 3-Tier)** | **3 tier**: BM25 < 3.0 → OOC (tolak), 3.0-4.9 → BM25_BORDERLINE (QNA link), ≥ 5.0 → lanjut hybrid search. Cascade BM25 depth 3 + E5 similarity guard (cosim ≥0.70 cegah topic drift) (best practice: NVIDIA 3-5 turns, Chatnexus sliding window 3). **Zero LLM cost untuk out-of-context & borderline.** |
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
                              ├─ BM25 < 5 + history → cascade depth 1-3
                              │   └─ BM25 cascade ≥ 5 + E5 sim ≥0.70? → hybrid
                              │   └─ E5 sim <0.70? → topic drift → 3-tier gate
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
│  • BM25 < 3.0    → ❌ OOC_BM25 (tolak)             │
│  • BM25 3.0-4.9  → ❌ BM25_BORDERLINE (QNA link)   │
│  • BM25 < 5 + history → CASCADE depth 1-3          │
│  │  ├─ cascade BM25 ≥ 5 + E5 sim ≥ 0.70 → hybrid ↓│
│  │  └─ E5 sim < 0.70 → topic drift → 3-tier gate   │
│  • BM25 ≥ 5.0    → ✅ lanjut hybrid ↓              │
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
│  RRF ranking: 1/(rank_E5+K) + 1/(rank_BM25+K)    │
│  Top-5 FAQ terpilih (RRF untuk ranking, bukan gate)│
└───────────────────────────────────────────────────┘
  │
  ▼
┌─ 7. LLM GENERATE ───────────────────────────────┐
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

> **Ringkasan:** User chat → sanitasi → anti-spam → intent classifier → **BM25 3-tier gate** → cascade depth 3 + E5 similarity guard → hybrid search (E5+BM25 RRF) → LLM → jawab + log

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

> **Catatan:** BM25 punya dua peran: (1) **Gate 3-tier** — `get_bm25_score()` ambil max dari semua FAQ, putuskan OOC/BM25_BORDERLINE/lanjut. Juga sebagai **cascade trigger** — concat prev query depth 1-3 kalo BM25 < 5 + ada history. (2) **Hybrid leg** — `get_bm25_scores_all()` return per-doc untuk RRF fusion. Cascade yang lolos BM25 ≥ 5 dicek **E5 similarity** (cosim ≥ 0.70) untuk deteksi topic drift. Kedua nilai BM25 di-log terpisah: `bm25_gate` (gate) dan `bm25_raw` (BM25 FAQ pemenang RRF). Centroid E5 di-log untuk analytics (bukan gate).

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
              │                         tanpa konteks → treat sebagai forward — domain check normal)
              └─ forward             → Lanjut ke hybrid search + domain filter (RRF gate)
```

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

**Context-aware feedback (v2.5.1+):**
- Feedback responses (`positive_feedback` / `negative_feedback`) **hanya muncul** jika session telah memiliki riwayat CLF `forward` (user pernah bertanya sebelumnya).
- `positive_feedback` tanpa konteks → diarahkan ke **greeting** (user mungkin cuma ramah).
- `negative_feedback` tanpa konteks → diarahkan ke **forward pipeline** (user mungkin typo atau iseng; fallback ke BM25 gate normal).
- Tracking per-session via `session_has_forward` dict di `security/session.py`.

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

### 🔄 Cascade Fallback (BM25 + E5 Similarity)

Ketika user memberi **follow-up pendek** yang kurang keyword (misal "tetep gabisa" setelah "verifikasi NIK gimana"), BM25 original bisa turun drastis. Cascade menyelamatkan ini dengan concat prev query.

**Cara kerja:**
1. **BM25 original < 5** + ada history → concat prev query depth 1-3, hitung BM25 ulang
2. Jika **BM25 cascade ≥ 5** (dapat keyword dari prev query) → cek **E5 cosine similarity** antara query asli vs prev query
3. **E5 sim ≥ 0.70** → masih satu topik → ✅ lanjut hybrid search → LLM
4. **E5 sim < 0.70** → topic drift → ❌ cascade skip, jatuh ke 3-tier BM25 gate

| Skenario | BM25 original | BM25 cascade | E5 sim | Hasil |
|----------|:---:|:---:|:---:|:--:|
| Follow-up: "tetep gabisa" setelah "verifikasi NIK" | 0.0 | 9.2 | 0.89 ✅ | LLM jawab |
| Topic drift: "BPS bukan satu-satunya" setelah "verifikasi NIK" | 2.1 | 5.2 | 0.55 ❌ | Cascade skip → tier gate |
| Non-BPS: "siapa presiden" setelah "aktivasi FASIH" | 0.0 | 5.8 | 0.34 ❌ | Cascade skip → tier gate |

**Biaya:** E5 query_vec sudah di-compute untuk BM25 gate, prev query di LRU cache. Cek cosine similarity cuma ~0.001ms — praktis gratis.

---

## Riwayat Versi

### v2.5.1 — Context-Aware Feedback + Positive Response Update
- **Positive feedback response** diperbarui: "Senang bisa membantu, terima kasih telah menggunakan layanan Nara 😊"
- **Context-aware feedback:** `positive_feedback` / `negative_feedback` hanya direspon jika session punya riwayat CLF `forward` (user pernah bertanya).
  - `positive_feedback` tanpa konteks → treat sebagai greeting.
  - `negative_feedback` tanpa konteks → treat sebagai forward (domain check normal).
  - Tracking via `session_has_forward` dict di `security/session.py`.
- File diubah: `prompts/responses.json`, `server.py`, `security/session.py`

### v2.5.0 — scikit-learn Intent Classifier
- Intent classifier migrasi dari keyword regex ke **SGDClassifier + TF-IDF** (pure Python, 185KB, 98.1% accuracy).
- 5 kelas: `greeting`, `capability`, `positive_feedback`, `negative_feedback`, `forward`.
- Keyword fallback auto aktif jika scikit-learn tidak terinstall.
- Training data: `core/classifier_train.txt` (845 sampel).
- File baru: `core/intent_classifier.py`, `core/classifier_train.txt`

### v2.4.0 — Cascade BM25 + E5 Similarity Guard
- Cascade BM25 depth 3 untuk follow-up pendek (concat prev query).
- E5 cosine similarity guard (≥0.70) cegah topic drift.
- Multi-part split dengan E5 Semantic Boundary (threshold 0.78).
- Pipeline parsing pindah dari heuristic ke `_raw_query` (E5 split + merge).

### v2.3.0 — Hybrid E5+BM25 via RRF Fusion
- Hybrid search: E5 semantic + BM25 keyword fusion via Reciprocal Rank Fusion (K=60).
- RRF untuk ranking saja (bukan gate).
- BM25 3-tier threshold: <3 tolak, 3-4.9 QNA link, ≥5 hybrid.
- Centroid E5 di-log untuk analytics dashboard.

### v2.2.0 — Multi-LLM Failover Chain
- Multi-provider LLM: OpenCode → DeepSeek → Ollama lokal — auto failover.
- `call_llm` return (content, model, provider, elapsed_ms).

### v2.1.0 — BM25 Domain Gate
- Domain gate: BM25 3-tier threshold.
- Cascade BM25 depth 3 untuk follow-up.
- QNA form link untuk borderline queries.

### v2.0.0 — Arsitektur Modular
- Restrukturisasi lengkap: `core/`, `security/`, `prompts/`.
- Session management + watchdog.
- Anti-spam + daily limit.
- Dashboard monitoring (port 8001).

### v1.0.0 — MVP
- E5-base semantic search via numpy cosine similarity.
- Single-provider LLM (DeepSeek).
- Google Sheets FAQ + SQLite chat history.
- OCR via EasyOCR.

---


