# -*- coding: utf-8 -*-
"""
Vector Redaction PDF Masker using PyMuPDF (fitz):
1. Detects text using exact matching and regex patterns.
2. Applies native vector redactions (add_redact_annot & apply_redactions) 
   which removes the text from the underlying binary stream and draws 
   a visual black box or placeholder text.
3. Falls back to a compressed JPEG rasterization (200 DPI) for scanned/image-only PDFs
   to keep file size small while ensuring the visual mask is burned into the image.
"""

import os
import fitz  # PyMuPDF
from converter_engine.masking.patterns import find_matches, compile_company_list_pattern

DPI = 200

def redact_pdf(input_path, output_path, company_names=None, manual_regions=None, **detect_opts):
    """
    manual_regions: list of dict {"page": int (1-based), "x0","y0","x1","y1": float}
    dalam satuan point PDF.
    """
    company_pattern = compile_company_list_pattern(company_names or [])
    log = []
    manual_regions = manual_regions or []

    # Buka dokumen PDF input
    doc = fitz.open(input_path)
    
    # Dokumen PDF output yang akan kita bangun (page per page)
    out_doc = fitz.open()
    
    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        
        # Coba ekstrak teks dari halaman
        text = page.get_text("text")
        
        # Jika halaman kosong dari selectable text, asumsikan ini scanned image
        if not text.strip():
            # 1. Gambar region manual (jika ada) ke atas halaman *sebelum* dirasterisasi
            for region in manual_regions:
                if int(region["page"]) != page_num:
                    continue
                x0, y0, x1, y1 = float(region["x0"]), float(region["y0"]), float(region["x1"]), float(region["y1"])
                page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0,0,0), fill=(0,0,0))
                log.append({
                    "lokasi": f"Halaman {page_num}",
                    "label": "MANUAL_REGION",
                    "teks_asli": f"(area manual x0={region['x0']},y0={region['y0']},x1={region['x1']},y1={region['y1']})",
                })
            
            # 2. Rasterisasi halaman menjadi image dengan resolusi ~200 DPI
            zoom = DPI / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Compress image ke JPEG (Quality 75) untuk menjaga file size (~1-2MB max per page)
            img_bytes = pix.tobytes("jpeg", 75)
            
            # 3. Masukkan ke dokumen output
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)
            
        else:
            # --- Vector Layer Redaction ---
            matches = find_matches(text, company_pattern, **detect_opts)
            
            for m in matches:
                label = m["label"]
                original_text = m["text"]
                
                # Cari semua bounding box untuk teks yang cocok di halaman ini
                # search_for mereturn list of fitz.Rect
                rects = page.search_for(original_text)
                for rect in rects:
                    # Tambahkan anotasi redaksi. 
                    # cross_out=False, fill=black. 
                    # Kita taruh teks [REDACTED:...] agar bisa dibaca oleh parser MarkDown nanti.
                    page.add_redact_annot(rect, text=f"[REDACTED:{label}]", cross_out=False, fill=(0,0,0), text_color=(1,1,1))
                    
                # Pastikan masuk log meski tidak ketemu rect-nya (kadang format aneh)
                if rects:
                    log.append({
                        "lokasi": f"Halaman {page_num}",
                        "label": label,
                        "teks_asli": original_text,
                    })
                    
            # Tambahkan redaksi untuk area manual
            for region in manual_regions:
                if int(region["page"]) != page_num:
                    continue
                x0, y0, x1, y1 = float(region["x0"]), float(region["y0"]), float(region["x1"]), float(region["y1"])
                page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0,0,0))
                log.append({
                    "lokasi": f"Halaman {page_num}",
                    "label": "MANUAL_REGION",
                    "teks_asli": f"(area manual x0={region['x0']},y0={region['y0']},x1={region['x1']},y1={region['y1']})",
                })
                
            # Terapkan semua redaksi. 
            # Ini akan menghapus karakter sensitif dari PDF binary content stream!
            page.apply_redactions()
            
            # Copy halaman yang sudah bersih ke dokumen output
            out_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)

    # Simpan hasil dengan garbage collection untuk optimasi size
    out_doc.save(output_path, garbage=3, deflate=True)
    out_doc.close()
    doc.close()
    return log
