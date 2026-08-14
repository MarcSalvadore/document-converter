#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alat redaksi/masking dokumen offline.
Mendukung: .docx, .xlsx, .csv, .pdf

Contoh pemakaian:
  # 1. Selalu mulai dengan dry-run untuk lihat apa yang AKAN di-mask
  #    tanpa mengubah file sama sekali:
  python redact_tool.py --input ./dokumen --company-list companies.txt --dry-run

  # 2. Setelah dicek reportnya (redact_report.csv) dan hasilnya sesuai,
  #    baru jalankan sungguhan:
  python redact_tool.py --input ./dokumen --company-list companies.txt --output ./hasil_redaksi

Opsi deteksi bisa dimatikan satu-satu kalau tidak relevan, contoh:
  --no-address       (tidak mendeteksi alamat)
  --no-rekening       (tidak mendeteksi no rekening)
  --no-npwp           (tidak mendeteksi NPWP)
  --no-company-auto   (hanya pakai company-list, tidak auto-detect PT/CV/Tbk dst)
"""

import argparse
import csv
import os
import sys
import traceback

from redact_docx import redact_docx
from redact_spreadsheet import redact_xlsx, redact_csv
from redact_pdf import redact_pdf


SUPPORTED_EXT = {".docx", ".xlsx", ".csv", ".pdf"}


def load_company_list(path):
    if not path:
        return []
    if not os.path.isfile(path):
        print(f"[PERINGATAN] File company-list tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


def collect_files(input_path):
    if os.path.isfile(input_path):
        return [input_path]
    files = []
    for root, _dirs, names in os.walk(input_path):
        for name in names:
            if os.path.splitext(name)[1].lower() in SUPPORTED_EXT:
                files.append(os.path.join(root, name))
    return files


def load_manual_regions(path):
    if not path:
        return []
    if not os.path.isfile(path):
        print(f"[PERINGATAN] File manual-regions tidak ditemukan: {path}")
        return []
    regions_by_file = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("file", "").strip()
            regions_by_file.setdefault(fname, []).append({
                "page": row["page"], "x0": row["x0"], "y0": row["y0"],
                "x1": row["x1"], "y1": row["y1"],
            })
    return regions_by_file


def process_one_file(path, output_dir, company_names, detect_opts, dry_run, manual_regions_by_file=None):
    ext = os.path.splitext(path)[1].lower()
    base = os.path.basename(path)
    out_path = os.path.join(output_dir, base) if output_dir else None

    if dry_run:
        # jalankan ke file sementara supaya tetap dapat log tanpa
        # menimpa/menulis output permanen
        import tempfile
        tmp_out = os.path.join(tempfile.mkdtemp(), base)
        target = tmp_out
    else:
        target = out_path

    if ext == ".docx":
        log = redact_docx(path, target, company_names=company_names, **detect_opts)
    elif ext == ".xlsx":
        log = redact_xlsx(path, target, company_names=company_names, **detect_opts)
    elif ext == ".csv":
        log = redact_csv(path, target, company_names=company_names, **detect_opts)
    elif ext == ".pdf":
        manual_regions = (manual_regions_by_file or {}).get(base, [])
        log = redact_pdf(path, target, company_names=company_names, manual_regions=manual_regions, **detect_opts)
    else:
        return []

    for entry in log:
        entry["file"] = path
    return log


def write_report(all_logs, report_path):
    fieldnames = ["file", "lokasi", "label", "teks_asli"]
    with open(report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in all_logs:
            writer.writerow(entry)


def main():
    parser = argparse.ArgumentParser(description="Redaksi/masking dokumen offline")
    parser.add_argument("--input", required=True, help="File atau folder input")
    parser.add_argument("--output", help="Folder output (wajib kecuali --dry-run)")
    parser.add_argument("--company-list", help="Path .txt berisi nama perusahaan, satu per baris")
    parser.add_argument("--manual-regions",
                         help="Path CSV berisi region PDF yang di-blackout paksa (kolom: file,page,x0,y0,x1,y1). "
                              "Hasil dari inspect_pdf.py + verifikasi manual. Hanya berlaku untuk file .pdf.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Tidak menulis file hasil; hanya membuat report CSV untuk dicek dulu")
    parser.add_argument("--report", default="redact_report.csv",
                         help="Path file report CSV (default: redact_report.csv)")
    parser.add_argument("--no-company-auto", action="store_true")
    parser.add_argument("--no-npwp", action="store_true")
    parser.add_argument("--no-rekening", action="store_true")
    parser.add_argument("--no-address", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.output:
        print("ERROR: --output wajib diisi kecuali memakai --dry-run")
        sys.exit(1)

    if args.output:
        os.makedirs(args.output, exist_ok=True)

    company_names = load_company_list(args.company_list)
    manual_regions_by_file = load_manual_regions(args.manual_regions)
    detect_opts = {
        "detect_company_auto": not args.no_company_auto,
        "detect_npwp": not args.no_npwp,
        "detect_rekening": not args.no_rekening,
        "detect_address": not args.no_address,
    }

    files = collect_files(args.input)
    if not files:
        print("Tidak ada file dengan format didukung (.docx, .xlsx, .csv, .pdf) ditemukan.")
        sys.exit(0)

    print(f"Ditemukan {len(files)} file. Mode: {'DRY-RUN (tidak menulis file)' if args.dry_run else 'PROSES PENUH'}")

    all_logs = []
    for path in files:
        print(f"  Memproses: {path}")
        try:
            log = process_one_file(path, args.output, company_names, detect_opts, args.dry_run,
                                    manual_regions_by_file)
            all_logs.extend(log)
            print(f"    -> {len(log)} item terdeteksi")
        except Exception as e:
            print(f"    [GAGAL] {path}: {e}")
            traceback.print_exc()

    write_report(all_logs, args.report)
    print(f"\nReport lengkap (apa saja yang ter-mask & lokasinya): {args.report}")
    print("PENTING: report ini berisi teks asli yang sensitif -- jangan ikut dibagikan,")
    print("hapus atau amankan setelah selesai review.")

    if args.dry_run:
        print("\nIni baru dry-run. Cek redact_report.csv dulu.")
        print("Kalau hasil deteksi sudah sesuai, jalankan ulang tanpa --dry-run dan dengan --output.")


if __name__ == "__main__":
    main()
