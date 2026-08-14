#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alat bantu INSPEKSI (bukan redaksi) untuk PDF yang punya elemen sulit
dideteksi otomatis: logo/gambar dan teks watermark diagonal/rotasi.

Kenapa ini perlu: nama perusahaan yang muncul sebagai LOGO (gambar) atau
watermark yang DIROTASI tidak bisa dideteksi lewat pencocokan teks biasa.
Satu-satunya cara yang aman adalah tandai koordinatnya secara manual setelah
melihat isinya -- alat ini menyiapkan semua bahan untuk itu (render halaman,
crop tiap gambar dengan koordinatnya, daftar teks yang rotasinya aneh),
supaya kamu tinggal lihat & catat, bukan menebak.

Pemakaian:
    python inspect_pdf.py dokumen.pdf --out inspeksi/

Setelah dijalankan, buka folder output:
- page_N.png              -> render halaman N, untuk lihat tata letak penuh
- page_N_img_K.png         -> crop gambar ke-K di halaman N
- image_manifest.csv       -> koordinat tiap gambar (page,index,x0,y0,x1,y1)
- rotated_text_report.csv  -> teks yang terdeteksi tapi TIDAK dalam orientasi
                              horizontal normal (kandidat watermark), dengan
                              bounding box per-karakter

Setelah kamu tentukan area mana yang perlu di-blackout (dari image_manifest
atau rotated_text_report), catat baris yang relevan ke file manual_regions.csv
dengan kolom: file,page,x0,y0,x1,y1 (satuan point PDF, sama seperti di
manifest -- TIDAK perlu dikonversi), lalu jalankan redact_tool.py atau gui.py
dengan opsi --manual-regions manual_regions.csv.
"""

import argparse
import csv
import os

import pdfplumber
from pdf2image import convert_from_path

DPI = 150


def find_literal_occurrences(page, search_terms):
    """
    Cari kemunculan literal search_terms di stream karakter PDF (page.chars),
    TERLEPAS dari apakah teksnya horizontal normal atau dirotasi/diagonal
    (watermark). Ini pendekatan yang sudah terverifikasi manual sebelumnya:
    lebih andal daripada menebak pola "teks aneh" secara generik, karena kita
    tahu persis kata apa yang dicari.

    Return: list of dict {term, x0, y0, x1, y1} -- bounding box gabungan dari
    seluruh karakter yang membentuk kemunculan term tsb.
    """
    if not search_terms:
        return []
    chars = page.chars
    full_text = "".join(c["text"] for c in chars)
    results = []
    for term in search_terms:
        term = term.strip()
        if not term:
            continue
        start = 0
        while True:
            idx = full_text.find(term, start)
            if idx == -1:
                break
            relevant = chars[idx:idx + len(term)]
            if relevant:
                x0 = min(c["x0"] for c in relevant)
                x1 = max(c["x1"] for c in relevant)
                y0 = min(c["top"] for c in relevant)
                y1 = max(c["bottom"] for c in relevant)
                results.append({"term": term, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
            start = idx + 1
    return results


def main():
    parser = argparse.ArgumentParser(description="Inspeksi PDF untuk cari logo/watermark yang tidak terdeteksi otomatis")
    parser.add_argument("input", help="File PDF")
    parser.add_argument("--out", default="inspeksi", help="Folder output")
    parser.add_argument("--search", action="append", default=[],
                         help="Kata/frasa yang mau dicari posisinya walau dirotasi/watermark "
                              "(bisa diulang, mis. --search BDO --search vCISO). Kalau kamu tahu "
                              "ada nama yang tidak muncul di company-list biasa karena rotasi teks, "
                              "cari di sini dulu untuk dapat koordinatnya.")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    scale = DPI / 72.0

    images = convert_from_path(args.input, dpi=DPI)
    image_manifest = []
    search_report = []

    with pdfplumber.open(args.input) as pdf:
        for page_idx, (page, page_img) in enumerate(zip(pdf.pages, images)):
            page_num = page_idx + 1
            page_img.save(os.path.join(args.out, f"page_{page_num}.png"))

            for img_idx, im in enumerate(page.images):
                x0, y0, x1, y1 = im["x0"], im["top"], im["x1"], im["bottom"]
                crop = page_img.crop((x0 * scale, y0 * scale, x1 * scale, y1 * scale))
                crop_name = f"page_{page_num}_img_{img_idx}.png"
                crop.save(os.path.join(args.out, crop_name))
                image_manifest.append({
                    "page": page_num, "index": img_idx, "crop_file": crop_name,
                    "x0": round(x0, 2), "y0": round(y0, 2), "x1": round(x1, 2), "y1": round(y1, 2),
                })

            if args.search:
                for hit in find_literal_occurrences(page, args.search):
                    hit["page"] = page_num
                    search_report.append(hit)

    with open(os.path.join(args.out, "image_manifest.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["page", "index", "crop_file", "x0", "y0", "x1", "y1"])
        w.writeheader()
        w.writerows(image_manifest)

    print(f"Selesai. Hasil ada di folder: {args.out}")
    print(f"  - {len(images)} halaman di-render (page_N.png)")
    print(f"  - {len(image_manifest)} gambar/logo di-crop, lihat image_manifest.csv")

    if args.search:
        with open(os.path.join(args.out, "search_report.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["page", "term", "x0", "y0", "x1", "y1"])
            w.writeheader()
            for r in search_report:
                w.writerow({"page": r["page"], "term": r["term"], "x0": round(r["x0"], 2),
                            "y0": round(r["y0"], 2), "x1": round(r["x1"], 2), "y1": round(r["y1"], 2)})
        print(f"  - {len(search_report)} kemunculan kata yang dicari, lihat search_report.csv")
        print("    (koordinat per-kemunculan; kalau teksnya rotasi/diagonal, bbox mengikuti")
        print("    bentuk hasil rotasi karakternya -- SELALU cek dulu di page_N.png apakah")
        print("    area itu menabrak konten lain sebelum dijadikan manual region)")
    else:
        print("  - (tidak ada kata dicari; pakai --search NAMA untuk cari kata yang mungkin")
        print("    watermark/rotasi, mis. --search BDO --search vCISO)")

    print()
    print("Langkah selanjutnya:")
    print("1. Buka page_N.png untuk lihat tata letak halaman.")
    print("2. Buka crop gambar (page_N_img_K.png) satu-satu untuk cari mana yang logo perusahaan.")
    print("3. Kalau ada watermark/teks rotasi yang dicurigai, jalankan ulang dengan --search.")
    print("4. PENTING: sebelum menandai koordinat sebagai manual region, cek dulu apakah")
    print("   area itu menabrak teks/diagram lain -- kalau kamu ragu, kirim ke saya dan saya")
    print("   bantu verifikasi seperti sebelumnya.")
    print("5. Catat baris yang sudah pasti aman ke manual_regions.csv (file,page,x0,y0,x1,y1)")
    print("   lalu jalankan redaksi dengan --manual-regions manual_regions.csv")


if __name__ == "__main__":
    main()
