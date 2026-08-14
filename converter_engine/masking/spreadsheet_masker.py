# -*- coding: utf-8 -*-
import csv
import openpyxl
from converter_engine.masking.patterns import find_matches, mask_text, compile_company_list_pattern


def redact_xlsx(input_path, output_path, company_names=None, **detect_opts):
    company_pattern = compile_company_list_pattern(company_names or [])
    wb = openpyxl.load_workbook(input_path)
    log = []

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None or not isinstance(cell.value, str):
                    continue
                original = cell.value
                matches = find_matches(original, company_pattern, **detect_opts)
                if not matches:
                    continue
                cell.value = mask_text(original, matches, mask_style="label")
                for m in matches:
                    log.append({
                        "lokasi": f"Sheet '{ws.title}' sel {cell.coordinate}",
                        "label": m["label"],
                        "teks_asli": m["text"],
                    })

    wb.save(output_path)
    return log


def redact_csv(input_path, output_path, company_names=None, encoding="utf-8", **detect_opts):
    company_pattern = compile_company_list_pattern(company_names or [])
    log = []

    with open(input_path, "r", encoding=encoding, newline="") as f_in:
        reader = csv.reader(f_in)
        rows = list(reader)

    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            if not value:
                continue
            matches = find_matches(value, company_pattern, **detect_opts)
            if not matches:
                continue
            rows[r_idx][c_idx] = mask_text(value, matches, mask_style="label")
            for m in matches:
                log.append({
                    "lokasi": f"Baris {r_idx+1}, Kolom {c_idx+1}",
                    "label": m["label"],
                    "teks_asli": m["text"],
                })

    with open(output_path, "w", encoding=encoding, newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerows(rows)

    return log
