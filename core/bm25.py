"""
BM25 domain checker — Nara
Membedakan pertanyaan BPS vs non-BPS pake keyword overlap.
"""

import math
import re as _re

from rank_bm25 import BM25Okapi

# ── STOPWORDS ──
_STOPWORDS = set('''
siapa apa dimana kapan mengapa bagaimana nama yang di ke dari
dan atau dengan untuk pada adalah ini itu saya kami kita anda
dia mereka telah sudah akan sedang tidak ada bisa dapat mohon
tolong apakah boleh halo hai permisi maaf terima kasih ya juga
saja lagi oleh sebagai secara setelah sebelum tentang dalam antara
seperti semua setiap sangat lebih kurang cukup agak paling baik
buruk baru lama besar kecil banyak sedikit selalu sering jarang
pernah belum bukan tapi namun meski walaupun karena sebab maka
lalu kemudian kalau jika bila meskipun serta sampai hingga sejak
mulai bapak ibu pak bu berapa benarkah mas lokasi hari tempat
waktu tanggal jam malam siang sore besok kemarin sekarang nanti
pernah menjadi merupakan sebuah terhadap tersebut sendiri yaitu
yakni dimana melalui tanpa maupun bahwa hingga mana pun atau
bisa bisakah dapat tolong dimohon
cara daftar medaftar mendaftar pendaftaran
terbaru versi update info informasi pengumuman
'''.strip().split())

# Regex angka doang (tahun, nomor) — minimal harus ada huruf
_ANGKA_ONLY = _re.compile(r'^[0-9]+$')

K1 = 1.2
B = 0.75
_THRESHOLD = 0.5


def _tokenize(text: str) -> list[str]:
    """Tokenize: lowercasing, remove non-alnum, stopwords, min 2 chars"""
    tokens = _re.sub(r'[^a-z0-9\s]', '', text.lower()).split()
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1 and not _ANGKA_ONLY.match(t)]


class BM25DomainChecker:
    """BM25 index dari FAQ + domain check — pakai rank_bm25"""

    def __init__(self):
        self.tokenized_docs: list[list[str]] = []
        self.bm25: BM25Okapi | None = None
        self.n_docs = 0
        self.ready = False

    def build(self, questions: list[str]):
        """Build index dari list pertanyaan FAQ"""
        self.tokenized_docs = [_tokenize(q) for q in questions if q]
        self.n_docs = len(self.tokenized_docs)
        if self.n_docs > 0:
            self.bm25 = BM25Okapi(self.tokenized_docs, k1=K1, b=B)
        self.ready = True

    def score(self, query: str) -> float:
        """BM25 max score query vs semua dokumen"""
        if not self.ready or self.n_docs == 0:
            return 999.0
        q_tokens = _tokenize(query)
        if not q_tokens:
            return 0.0
        scores = self.bm25.get_scores(q_tokens)
        return float(max(scores))

    def score_all(self, query: str) -> list[float]:
        """BM25 scores untuk SEMUA dokumen (buat hybrid)"""
        if not self.ready or self.n_docs == 0:
            return [0.0]
        q_tokens = _tokenize(query)
        if not q_tokens:
            return [0.0] * self.n_docs
        return [float(s) for s in self.bm25.get_scores(q_tokens)]

    def check(self, query: str) -> bool:
        """True kalo query masih dalam domain BPS"""
        s = self.score(query)
        ok = s >= _THRESHOLD
        print(f"[BM25] '{query[:40]}' = {s:.2f} → {'✅' if ok else '❌'}")
        return ok


# Singleton
_checker = BM25DomainChecker()


def build_bm25(questions: list[str]):
    _checker.build(questions)


def check_domain(query: str) -> bool:
    return _checker.check(query)


def get_bm25_score(query: str) -> float:
    """Kembalikan raw BM25 score"""
    return _checker.score(query)


def get_bm25_scores_all(query: str) -> list[float]:
    """Kembalikan BM25 score per dokumen (buat hybrid)"""
    return _checker.score_all(query)
