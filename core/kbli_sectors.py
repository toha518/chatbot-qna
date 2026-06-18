"""
kbli_sectors.py — Mapping kode KBLI 2-digit ke kategori sektor (A-V)
Berdasarkan KBLI 2025 (ISIC Rev.5 — diadopsi BPS via Peraturan BPS No.7/2025)
"""

# Mapping: 2-digit prefix (sebagai integer) → (Kategori, Nama Sektor)
# Format: (div_start, div_end): ("Kategori", "Nama Sektor Indonesia")
SECTOR_RANGES = [
    (1, 3,   "A", "Pertanian, Kehutanan, dan Perikanan"),
    (5, 9,   "B", "Pertambangan dan Penggalian"),
    (10, 33, "C", "Industri"),
    (35, 35, "D", "Penyediaan Listrik, Gas, Uap/Air Panas, dan Udara Dingin"),
    (36, 39, "E", "Penyediaan Air, Pengelolaan Air Limbah, Penanganan Limbah, dan Remediasi"),
    (41, 43, "F", "Konstruksi"),
    (45, 47, "G", "Perdagangan Besar dan Eceran"),
    (49, 53, "H", "Transportasi dan Penyimpanan"),
    (55, 56, "I", "Aktivitas Penyediaan Akomodasi dan Makan Minum"),
    (58, 60, "J", "Aktivitas Penerbitan, Penyiaran, serta Produksi dan Distribusi Konten"),
    (61, 63, "K", "Aktivitas Telekomunikasi, Pemrograman Komputer, Konsultansi, Infrastruktur Komputasi, dan Jasa Informasi Lainnya"),
    (64, 66, "L", "Aktivitas Keuangan dan Asuransi"),
    (68, 68, "M", "Aktivitas Real Estat"),
    (69, 75, "N", "Aktivitas Profesional, Ilmiah, dan Teknis"),
    (77, 82, "O", "Aktivitas Administratif dan Penunjang Usaha"),
    (84, 84, "P", "Administrasi Pemerintahan dan Pertahanan, serta Jaminan Sosial Wajib"),
    (85, 85, "Q", "Pendidikan"),
    (86, 88, "R", "Aktivitas Kesehatan Manusia dan Aktivitas Sosial"),
    (90, 93, "S", "Kesenian, Olahraga, dan Rekreasi"),
    (94, 96, "T", "Aktivitas Jasa Lainnya"),
    (97, 98, "U", "Aktivitas Rumah Tangga sebagai Pemberi Kerja"),
    (99, 99, "V", "Aktivitas Badan Internasional dan Badan Ekstra Internasional Lainnya"),
]

# Build lookup: division_int → (kategori, nama_sektor)
_LOOKUP = {}
for start, end, kat, nama in SECTOR_RANGES:
    for div in range(start, end + 1):
        _LOOKUP[div] = (kat, nama)


def get_sector(kbli_code: str) -> tuple[str, str] | None:
    """
    Cari sektor/kategori dari kode KBLI 2 digit pertama.
    Contoh: get_sector("56101") → ("I", "Aktivitas Penyediaan Akomodasi dan Makan Minum")
    """
    if not kbli_code or len(kbli_code) < 2:
        return None
    try:
        div = int(kbli_code[:2])
        return _LOOKUP.get(div)
    except (ValueError, IndexError):
        return None


def get_sector_label(kbli_code: str) -> str:
    """
    Return label sektor pendek. Contoh: "Sektor I — Aktivitas Penyediaan Akomodasi dan Makan Minum"
    """
    result = get_sector(kbli_code)
    if not result:
        return ""
    kat, nama = result
    # Truncate nama if too long
    if len(nama) > 45:
        nama = nama[:42] + "..."
    return f"{kat} — {nama}"
