# -*- coding: utf-8 -*-
"""
Modul deteksi informasi sensitif.
Semua pattern berjalan 100% offline (tidak butuh internet / model eksternal).

Pendekatan yang dipakai adalah RULE-BASED (regex + daftar kata), bukan model
NER statistik. Ini pilihan sadar: model NER umum (mis. spaCy multi-bahasa)
tidak dilatih khusus untuk entitas Bahasa Indonesia (nama PT, alamat gaya
Indonesia, format NPWP/rekening), sehingga akurasinya untuk kasus ini justru
lebih rendah dan lebih sulit diaudit dibanding aturan eksplisit di bawah ini.

KETERBATASAN YANG HARUS DISADARI PENGGUNA:
- Deteksi nama perusahaan otomatis (tanpa daftar) hanya menangkap pola yang
  eksplisit (diawali/diakhiri PT, CV, Tbk, dst). Nama perusahaan yang ditulis
  tanpa embel-embel itu (mis. hanya "Astra" tanpa "PT Astra International")
  TIDAK akan tertangkap kecuali ada di company_list.
- Deteksi no. rekening berbasis kata kunci di sekitarnya + pola digit.
  Nomor 8-16 digit acak tanpa konteks kata kunci berisiko false negative
  (tidak terdeteksi) maupun false positive (angka lain ikut ter-mask).
- Deteksi alamat berbasis kata kunci (Jl., Kel., Kec., RT/RW, dst), bukan
  pemahaman semantik. Alamat yang ditulis tidak baku bisa lolos.
- SELALU review hasil (mode --dry-run) sebelum mempercayai output final,
  terutama untuk dokumen yang akan dibagikan ke pihak eksternal.
"""

import re

LABEL_COMPANY_LIST = "PERUSAHAAN"
LABEL_COMPANY_AUTO = "PERUSAHAAN(AUTO)"
LABEL_NPWP = "NPWP"
LABEL_REKENING = "NO_REKENING"
LABEL_ADDRESS = "ALAMAT"

# Urutan prioritas ketika ada overlap antar match (yang lebih awal menang)
LABEL_PRIORITY = [
    LABEL_COMPANY_LIST,
    LABEL_NPWP,
    LABEL_REKENING,
    LABEL_ADDRESS,
    LABEL_COMPANY_AUTO,
]

_COMPANY_SUFFIX_PATTERN = re.compile(
    r"""\b(?:PT|CV|UD|Firma|Yayasan|Koperasi)\.?\s+
        [A-Z][A-Za-z0-9&.,'\-]*
        (?:\s+[A-Z][A-Za-z0-9&.,'\-]*){0,5}
        (?:\s+Tbk\b)?
    """,
    re.VERBOSE,
)

# Prefix institusi umum di Indonesia yang sering jadi nama entitas walau tanpa
# "PT/CV/Tbk" (bank, kementerian, badan pemerintah, universitas, dsb).
# Tetap ada risiko false positive (mis. "Bank Indonesia" sebagai istilah umum
# ikut ke-mask) -- kalau itu masalah, matikan lewat --no-company-auto dan
# andalkan company-list saja.
_INSTITUTION_PREFIX_PATTERN = re.compile(
    r"""\b(?:Bank|Kementerian|Badan|Lembaga|Universitas|Institut|Otoritas|
        Direktorat(?:\s+Jenderal)?|Dinas|Kantor\s+Wilayah|Komisi|Asosiasi)
        \s+[A-Z][A-Za-z0-9&.,'\-]*
        (?:\s+(?:dan\s+)?[A-Z][A-Za-z0-9&.,'\-]*){0,5}
    """,
    re.VERBOSE,
)

# Frasa multi-kata Title Case yang diikuti "- Tahun XXXX" (pola umum di
# daftar pengalaman proyek/audit, mis. "Indonesia Digital Identity - Tahun
# 2023"). Ini pola paling longgar dan paling rawan salah tangkap -- kalau
# ternyata kata biasa (bukan nama entitas) ikut ke-mask, matikan lewat
# --no-company-auto dan andalkan company-list saja.
_TITLECASE_ENTITY_BEFORE_YEAR_PATTERN = re.compile(
    r"""\b[A-Z][A-Za-z0-9&\-]*
        (?:\s+[A-Z][A-Za-z0-9&\-]*){1,4}
        (?=\s*-\s*Tahun\s+\d{4})
    """,
    re.VERBOSE,
)

_COMPANY_SUFFIX_TRAILING_PATTERN = re.compile(
    r"""\b[A-Z][A-Za-z0-9&\-]*
        (?:\s+[A-Z][A-Za-z0-9&\-]*){0,3}
        \s+(?:Tbk|Group|Corp|Corporation|Inc|Ltd|LLC)\b\.?
    """,
    re.VERBOSE,
)

_NPWP_PATTERN = re.compile(
    r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b|\b\d{15,16}\b(?=\D{0,15}NPWP|NPWP\D{0,15}\b)",
    re.IGNORECASE,
)

_REKENING_KEYWORD = re.compile(
    r"(no\.?\s*rek(?:ening)?|nomor\s*rek(?:ening)?|account\s*no\.?|a/n|acc(?:ount)?\s*number)",
    re.IGNORECASE,
)

_DIGIT_RUN = re.compile(r"\b\d{8,16}\b")

_ADDRESS_KEYWORD_PATTERN = re.compile(
    r"""\b(?:Jl\.|Jalan|Kel\.|Kelurahan|Kec\.|Kecamatan|Kab\.|Kabupaten|
        Kota|Desa|Dusun|Perum(?:ahan)?|RT\.?\s*\d{1,3}\s*/?\s*RW\.?\s*\d{1,3})
        [^\n]{0,80}""",
    re.VERBOSE | re.IGNORECASE,
)


def _escape_terms(terms):
    return [re.escape(t.strip()) for t in terms if t.strip()]


def compile_company_list_pattern(company_names):
    """company_names: list[str] dari user (daftar nama perusahaan spesifik)."""
    terms = _escape_terms(company_names)
    if not terms:
        return None
    terms.sort(key=len, reverse=True)  # nama lebih panjang dicoba dulu
    pattern = r"\b(?:" + "|".join(terms) + r")\b"
    return re.compile(pattern, re.IGNORECASE)


def find_matches(text, company_list_pattern=None, detect_company_auto=True,
                  detect_npwp=True, detect_rekening=True, detect_address=True):
    """
    Mengembalikan list of dict: {start, end, label, text}
    Overlap ditangani: match dengan prioritas label lebih tinggi menang,
    kalau prioritas sama ambil yang lebih panjang / muncul lebih dulu.
    """
    raw_matches = []

    if company_list_pattern is not None:
        for m in company_list_pattern.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_COMPANY_LIST, m.group()))

    if detect_npwp:
        for m in _NPWP_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_NPWP, m.group()))

    if detect_rekening:
        for kw in _REKENING_KEYWORD.finditer(text):
            window_start = kw.end()
            window = text[window_start:window_start + 40]
            dm = _DIGIT_RUN.search(window)
            if dm:
                s = window_start + dm.start()
                e = window_start + dm.end()
                raw_matches.append((s, e, LABEL_REKENING, text[s:e]))

    if detect_address:
        for m in _ADDRESS_KEYWORD_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_ADDRESS, m.group().strip()))

    if detect_company_auto:
        for m in _COMPANY_SUFFIX_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_COMPANY_AUTO, m.group().strip()))
        for m in _COMPANY_SUFFIX_TRAILING_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_COMPANY_AUTO, m.group().strip()))
        for m in _INSTITUTION_PREFIX_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_COMPANY_AUTO, m.group().strip()))
        for m in _TITLECASE_ENTITY_BEFORE_YEAR_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), LABEL_COMPANY_AUTO, m.group().strip()))

    if not raw_matches:
        return []

    def sort_key(item):
        start, end, label, _ = item
        prio = LABEL_PRIORITY.index(label) if label in LABEL_PRIORITY else 99
        return (start, prio, -(end - start))

    raw_matches.sort(key=sort_key)

    resolved = []
    last_end = -1
    for start, end, label, matched_text in raw_matches:
        if start < last_end:
            continue  # overlap dengan match sebelumnya yang prioritasnya menang
        resolved.append({"start": start, "end": end, "label": label, "text": matched_text})
        last_end = end

    return resolved


def mask_text(text, matches, mask_style="label"):
    """
    mask_style:
      - "label": [REDACTED:LABEL]
      - "block": ███████ (panjang mengikuti teks asli, kasar)
    """
    if not matches:
        return text
    out = []
    cursor = 0
    for m in matches:
        out.append(text[cursor:m["start"]])
        if mask_style == "block":
            out.append("█" * max(6, m["end"] - m["start"]))
        else:
            out.append(f"[REDACTED:{m['label']}]")
        cursor = m["end"]
    out.append(text[cursor:])
    return "".join(out)
