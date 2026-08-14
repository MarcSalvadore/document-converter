# -*- coding: utf-8 -*-
"""
Redaksi PDF dengan pendekatan FLATTEN:
1. Ekstrak posisi tiap kata (pdfplumber) untuk tahu koordinat teks sensitif.
2. Render tiap halaman jadi gambar (pdf2image / poppler) pada DPI tertentu.
3. Gambar kotak hitam solid di atas koordinat yang cocok, LANGSUNG di piksel
   gambar (bukan cuma elemen vektor yang bisa dihapus/ditembus).
4. Susun ulang semua gambar halaman jadi PDF baru.

Hasilnya PDF final TIDAK punya layer teks sama sekali (full image-based),
sehingga bagian yang di-redact benar-benar tidak bisa di-copy-paste atau
di-extract lagi. Konsekuensi: seluruh dokumen jadi tidak bisa di-select
teksnya, bukan cuma bagian yang di-redact. Itu trade-off yang disengaja
untuk memastikan tidak ada kebocoran dari layer teks yang lupa dibersihkan.
"""

import pdfplumber
from pdf2image import convert_from_path
from PIL import Image, ImageDraw

from converter_engine.masking.patterns import find_matches, compile_company_list_pattern

DPI = 200


def _page_text_with_offsets(page):
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    text_parts = []
    offsets = []  # (start, end, word_dict)
    cursor = 0
    for w in words:
        token = w["text"]
        start = cursor
        end = start + len(token)
        offsets.append((start, end, w))
        text_parts.append(token)
        cursor = end + 1  # +1 untuk spasi pemisah yang kita sisipkan
    full_text = " ".join(text_parts)
    return full_text, offsets


def _words_overlapping_span(offsets, span_start, span_end):
    hits = []
    for start, end, w in offsets:
        if start < span_end and end > span_start:
            hits.append(w)
    return hits


def redact_pdf(input_path, output_path, company_names=None, manual_regions=None, **detect_opts):
    """
    manual_regions: list of dict {"page": int (1-based), "x0","y0","x1","y1": float}
    dalam satuan point PDF (sama seperti koordinat di image_manifest.csv dari
    inspect_pdf.py). Region ini SELALU di-blackout, terlepas dari hasil
    deteksi teks -- dipakai untuk kasus logo/watermark yang sudah diverifikasi
    manual sebelumnya (lihat inspect_pdf.py).
    """
    company_pattern = compile_company_list_pattern(company_names or [])
    log = []
    manual_regions = manual_regions or []

    images = convert_from_path(input_path, dpi=DPI)
    scale = DPI / 72.0  # pdfplumber pakai satuan point (1/72 inch)

    with pdfplumber.open(input_path) as pdf:
        for page_idx, (page, image) in enumerate(zip(pdf.pages, images)):
            page_num = page_idx + 1
            full_text, offsets = _page_text_with_offsets(page)
            draw = ImageDraw.Draw(image)

            if full_text.strip():
                matches = find_matches(full_text, company_pattern, **detect_opts)
                for m in matches:
                    words = _words_overlapping_span(offsets, m["start"], m["end"])
                    for w in words:
                        x0 = w["x0"] * scale
                        x1 = w["x1"] * scale
                        y0 = w["top"] * scale
                        y1 = w["bottom"] * scale
                        draw.rectangle([x0, y0, x1, y1], fill="black")
                    log.append({
                        "lokasi": f"Halaman {page_num}",
                        "label": m["label"],
                        "teks_asli": m["text"],
                    })

            for region in manual_regions:
                if int(region["page"]) != page_num:
                    continue
                x0, y0 = float(region["x0"]) * scale, float(region["y0"]) * scale
                x1, y1 = float(region["x1"]) * scale, float(region["y1"]) * scale
                draw.rectangle([x0, y0, x1, y1], fill="black")
                log.append({
                    "lokasi": f"Halaman {page_num}",
                    "label": "MANUAL_REGION",
                    "teks_asli": f"(area manual x0={region['x0']},y0={region['y0']},x1={region['x1']},y1={region['y1']})",
                })

    if images:
        images[0].save(
            output_path, "PDF", resolution=DPI,
            save_all=True, append_images=images[1:]
        )
    return log
