#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alat bantu (bukan pengganti company-list): memindai dokumen dan mengeluarkan
daftar KANDIDAT frasa yang kemungkinan nama entitas (perusahaan/instansi),
supaya kamu tidak perlu baca dokumen panjang satu-satu untuk menyusun
company-list.

Ini BUKAN detektor otomatis yang dipakai saat redaksi -- ini cuma alat bantu
sebelum redaksi, untuk mempercepat kamu menyusun daftar nama yang lengkap.
Hasilnya berupa CSV berisi frasa + jumlah kemunculan, urut dari yang paling
sering muncul. Review manual tetap wajib: tidak semua kandidat adalah nama
entitas (bisa saja judul jabatan, istilah teknis, dst), dan tidak semua nama
entitas asli akan tertangkap sebagai kandidat.

Pemakaian:
    python extract_candidates.py dokumen.docx
    python extract_candidates.py dokumen.docx --out kandidat.csv
    python extract_candidates.py folder_dokumen/   (proses semua .docx/.pdf/.csv/.xlsx di dalamnya)
"""

import argparse
import csv
import os
import re
from collections import Counter

import docx
import pdfplumber
import openpyxl

# Kata-kata umum Bahasa Indonesia/Inggris berhuruf awal besar yang SERING
# muncul di awal kalimat tapi BUKAN nama entitas -- dikecualikan supaya
# tidak membanjiri hasil dengan kandidat yang jelas bukan nama.
COMMON_STOPWORDS = {
    "Nama", "Posisi", "Pendidikan", "Sertifikasi", "Pengalaman", "Tahun",
    "Implementasi", "Audit", "Pengadaan", "Assessment", "Dan", "Untuk",
    "Dalam", "Yang", "Dengan", "Pada", "Dari", "Oleh", "Sebagai", "Adalah",
    "Konsultan", "Auditor", "Technical", "Writer", "Lead", "No", "Jika",
}

# Frasa 2-6 kata, setiap kata diawali huruf besar (Title Case / ALL CAPS),
# dianggap kandidat nama entitas.
_CANDIDATE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9&.'\-]*(?:\s+(?:dan\s+)?[A-Z][A-Za-z0-9&.'\-]*){1,5}\b"
)


def extract_text_docx(path):
    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def extract_text_pdf(path):
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n".join(parts)


def extract_text_xlsx(path):
    wb = openpyxl.load_workbook(path)
    parts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    parts.append(cell.value)
    return "\n".join(parts)


def extract_text_csv(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


EXTRACTORS = {
    ".docx": extract_text_docx,
    ".pdf": extract_text_pdf,
    ".xlsx": extract_text_xlsx,
    ".csv": extract_text_csv,
}


def find_candidates(text):
    counter = Counter()
    for m in _CANDIDATE_PATTERN.finditer(text):
        phrase = m.group().strip()
        first_word = phrase.split()[0]
        if first_word in COMMON_STOPWORDS:
            continue
        if phrase.isupper() and len(phrase.split()) == 1 and len(phrase) <= 2:
            continue  # singkatan 2 huruf, terlalu sering jadi noise
        counter[phrase] += 1
    return counter


def collect_files(input_path):
    if os.path.isfile(input_path):
        return [input_path]
    files = []
    for root, _dirs, names in os.walk(input_path):
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext in EXTRACTORS:
                files.append(os.path.join(root, name))
    return files


def main():
    parser = argparse.ArgumentParser(description="Ekstrak kandidat nama entitas dari dokumen")
    parser.add_argument("input", help="File atau folder dokumen")
    parser.add_argument("--out", default="kandidat_perusahaan.csv", help="Path CSV output")
    parser.add_argument("--min-count", type=int, default=1,
                         help="Hanya tampilkan frasa yang muncul minimal N kali (default: 1)")
    args = parser.parse_args()

    files = collect_files(args.input)
    if not files:
        print("Tidak ada file .docx/.pdf/.xlsx/.csv ditemukan.")
        return

    total_counter = Counter()
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        print(f"Memindai: {path}")
        try:
            text = EXTRACTORS[ext](path)
            total_counter.update(find_candidates(text))
        except Exception as e:
            print(f"  [GAGAL] {path}: {e}")

    rows = [(phrase, count) for phrase, count in total_counter.items() if count >= args.min_count]
    rows.sort(key=lambda x: (-x[1], x[0]))

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frasa_kandidat", "jumlah_kemunculan", "masukkan_ke_company_list(y/n)"])
        for phrase, count in rows:
            writer.writerow([phrase, count, ""])

    print(f"\n{len(rows)} kandidat ditemukan -> {args.out}")
    print("Buka file itu di Excel, isi kolom terakhir dengan 'y' untuk yang memang nama")
    print("perusahaan/instansi, lalu salin kolom 'frasa_kandidat' yang ditandai 'y' ke")
    print("companies_example.txt (satu nama per baris).")


if __name__ == "__main__":
    main()
