#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI desktop untuk alat redaksi/masking dokumen offline.
Pakai tkinter (bawaan Python, tidak perlu install tambahan untuk GUI-nya).

Jalankan dengan:
    python gui.py

Butuh file-file berikut ada di folder yang sama:
    patterns.py, redact_docx.py, redact_spreadsheet.py, redact_pdf.py
"""

import os
import sys
import csv
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from patterns import compile_company_list_pattern
from redact_docx import redact_docx
from redact_spreadsheet import redact_xlsx, redact_csv
from redact_pdf import redact_pdf

SUPPORTED_EXT = {".docx", ".xlsx", ".csv", ".pdf"}


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
    if not path or not os.path.isfile(path):
        return {}
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

    if dry_run:
        import tempfile
        target = os.path.join(tempfile.mkdtemp(), base)
    else:
        target = os.path.join(output_dir, base)

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


class RedactApp:
    def __init__(self, root):
        self.root = root
        root.title("Alat Redaksi Dokumen Offline")
        root.geometry("900x650")

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.manual_regions_path = tk.StringVar()
        self.detect_company_auto = tk.BooleanVar(value=True)
        self.detect_npwp = tk.BooleanVar(value=True)
        self.detect_rekening = tk.BooleanVar(value=True)
        self.detect_address = tk.BooleanVar(value=True)

        self.msg_queue = queue.Queue()
        self.last_results = []  # hasil dry-run terakhir, dipakai saat apply

        self._build_ui()
        self.root.after(100, self._poll_queue)

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        # --- Input ---
        frame_in = ttk.LabelFrame(self.root, text="1. Dokumen yang mau di-redact")
        frame_in.pack(fill="x", **pad)
        ttk.Entry(frame_in, textvariable=self.input_path).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(frame_in, text="Pilih File...", command=self._pick_file).pack(side="left", padx=4)
        ttk.Button(frame_in, text="Pilih Folder...", command=self._pick_folder).pack(side="left", padx=4)

        # --- Company list ---
        frame_company = ttk.LabelFrame(
            self.root,
            text="2. Daftar nama perusahaan spesifik (satu nama per baris) — opsional tapi disarankan"
        )
        frame_company.pack(fill="both", **pad)
        btn_row = ttk.Frame(frame_company)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Muat dari file .txt...", command=self._load_company_file).pack(side="left", padx=4, pady=4)
        self.company_text = tk.Text(frame_company, height=5)
        self.company_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # --- Detection options ---
        frame_opts = ttk.LabelFrame(self.root, text="3. Jenis informasi yang dideteksi")
        frame_opts.pack(fill="x", **pad)
        ttk.Checkbutton(frame_opts, text="Nama perusahaan otomatis (pola PT/CV/Tbk/Group/dll)",
                         variable=self.detect_company_auto).pack(anchor="w", padx=6)
        ttk.Checkbutton(frame_opts, text="NPWP", variable=self.detect_npwp).pack(anchor="w", padx=6)
        ttk.Checkbutton(frame_opts, text="Nomor rekening", variable=self.detect_rekening).pack(anchor="w", padx=6)
        ttk.Checkbutton(frame_opts, text="Alamat", variable=self.detect_address).pack(anchor="w", padx=6)
        ttk.Label(frame_opts, text="(Daftar nama perusahaan di atas selalu dicek, terlepas dari opsi ini)",
                  foreground="#666").pack(anchor="w", padx=6, pady=(0, 4))

        # --- Manual regions (untuk logo/watermark di PDF) ---
        frame_manual = ttk.LabelFrame(
            self.root,
            text="4. (Opsional, khusus PDF) Region manual untuk logo/watermark yang tidak terdeteksi teks"
        )
        frame_manual.pack(fill="x", **pad)
        ttk.Entry(frame_manual, textvariable=self.manual_regions_path).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(frame_manual, text="Pilih manual_regions.csv...", command=self._pick_manual_regions).pack(side="left", padx=4)
        ttk.Button(frame_manual, text="Buka Alat Inspeksi PDF...", command=self._run_inspect).pack(side="left", padx=4)

        # --- Actions ---
        frame_action = ttk.Frame(self.root)
        frame_action.pack(fill="x", **pad)
        ttk.Button(frame_action, text="Cek Dulu (Dry-Run) — tidak mengubah file",
                   command=self._run_dry_run).pack(side="left", padx=4)

        ttk.Label(frame_action, text="Folder output:").pack(side="left", padx=(20, 4))
        ttk.Entry(frame_action, textvariable=self.output_path, width=30).pack(side="left")
        ttk.Button(frame_action, text="Pilih...", command=self._pick_output).pack(side="left", padx=4)
        ttk.Button(frame_action, text="Jalankan Redaksi (Final)",
                   command=self._run_final).pack(side="left", padx=12)

        self.status_var = tk.StringVar(value="Siap.")
        ttk.Label(self.root, textvariable=self.status_var, foreground="#0055aa").pack(fill="x", padx=8)

        # --- Results table ---
        frame_result = ttk.LabelFrame(self.root, text="4. Hasil deteksi (review sebelum percaya hasilnya)")
        frame_result.pack(fill="both", expand=True, **pad)

        columns = ("file", "lokasi", "label", "teks_asli")
        self.tree = ttk.Treeview(frame_result, columns=columns, show="headings")
        for col, label, width in [
            ("file", "File", 180), ("lokasi", "Lokasi", 160),
            ("label", "Jenis", 130), ("teks_asli", "Teks Asli (belum di-mask)", 300),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(frame_result, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        ttk.Button(self.root, text="Simpan report ini sebagai CSV...",
                   command=self._save_report).pack(anchor="e", padx=8, pady=(0, 8))

        warn = ("Peringatan: report di atas berisi teks ASLI yang sensitif (belum di-mask). "
                "Jangan ikut dibagikan / hapus setelah selesai review.")
        ttk.Label(self.root, text=warn, foreground="#aa3300", wraplength=860).pack(fill="x", padx=8, pady=(0, 6))

    # ---------- Pickers ----------
    def _pick_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Dokumen didukung", "*.docx *.xlsx *.csv *.pdf"), ("Semua file", "*.*")]
        )
        if path:
            self.input_path.set(path)

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.input_path.set(path)

    def _pick_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_path.set(path)

    def _load_company_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text file", "*.txt"), ("Semua file", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        self.company_text.delete("1.0", "end")
        self.company_text.insert("1.0", "\n".join(names))

    def _pick_manual_regions(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Semua file", "*.*")])
        if path:
            self.manual_regions_path.set(path)

    def _run_inspect(self):
        input_path = self.input_path.get().strip()
        if not input_path or not input_path.lower().endswith(".pdf") or not os.path.isfile(input_path):
            messagebox.showinfo(
                "Pilih file PDF dulu",
                "Alat inspeksi ini khusus untuk 1 file PDF -- pilih file PDF di bagian '1. Dokumen' dulu."
            )
            return
        out_dir = filedialog.askdirectory(title="Pilih folder untuk hasil inspeksi")
        if not out_dir:
            return
        try:
            import inspect_pdf
            import sys
            old_argv = sys.argv
            sys.argv = ["inspect_pdf.py", input_path, "--out", out_dir]
            try:
                inspect_pdf.main()
            finally:
                sys.argv = old_argv
            messagebox.showinfo(
                "Selesai",
                f"Hasil inspeksi (render halaman, crop gambar, laporan teks rotasi) ada di:\n{out_dir}\n\n"
                "Buka file-file di folder itu untuk cari logo/watermark, lalu catat koordinatnya "
                "ke manual_regions.csv sebelum dipakai di sini."
            )
        except Exception as e:
            messagebox.showerror("Gagal", f"Alat inspeksi gagal jalan: {e}")
            traceback.print_exc()

    # ---------- Helpers ----------
    def _get_company_names(self):
        raw = self.company_text.get("1.0", "end")
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _get_detect_opts(self):
        return {
            "detect_company_auto": self.detect_company_auto.get(),
            "detect_npwp": self.detect_npwp.get(),
            "detect_rekening": self.detect_rekening.get(),
            "detect_address": self.detect_address.get(),
        }

    def _clear_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

    # ---------- Actions ----------
    def _run_dry_run(self):
        self._run(dry_run=True)

    def _run_final(self):
        if not self.output_path.get():
            messagebox.showwarning("Folder output belum dipilih",
                                    "Pilih folder output dulu sebelum menjalankan redaksi final.")
            return
        if not messagebox.askyesno(
            "Konfirmasi",
            "Ini akan MENULIS file hasil redaksi ke folder output.\n"
            "Sudah cek hasil Dry-Run dan yakin sesuai? Lanjutkan?"
        ):
            return
        self._run(dry_run=False)

    def _run(self, dry_run):
        input_path = self.input_path.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Input tidak valid", "Pilih file atau folder input yang valid dulu.")
            return

        files = collect_files(input_path)
        if not files:
            messagebox.showinfo("Tidak ada file", "Tidak ada file .docx/.xlsx/.csv/.pdf ditemukan di input ini.")
            return

        if not dry_run:
            os.makedirs(self.output_path.get(), exist_ok=True)

        company_names = self._get_company_names()
        detect_opts = self._get_detect_opts()
        manual_regions_by_file = load_manual_regions(self.manual_regions_path.get().strip())

        self._clear_tree()
        self.status_var.set(f"Memproses {len(files)} file...")
        self._set_buttons_enabled(False)

        t = threading.Thread(
            target=self._worker, args=(files, company_names, detect_opts, dry_run, manual_regions_by_file), daemon=True
        )
        t.start()

    def _worker(self, files, company_names, detect_opts, dry_run, manual_regions_by_file):
        all_logs = []
        errors = []
        for path in files:
            try:
                log = process_one_file(path, self.output_path.get(), company_names, detect_opts, dry_run,
                                        manual_regions_by_file)
                all_logs.extend(log)
            except Exception as e:
                errors.append((path, str(e)))
                traceback.print_exc()
        self.msg_queue.put(("done", all_logs, errors, dry_run, len(files)))

    def _set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for child in self.root.winfo_children():
            pass  # dibiarkan sederhana; status_var sudah cukup memberi tahu progres

    def _poll_queue(self):
        try:
            while True:
                kind, all_logs, errors, dry_run, n_files = self.msg_queue.get_nowait()
                self.last_results = all_logs
                for entry in all_logs:
                    self.tree.insert("", "end", values=(
                        os.path.basename(entry.get("file", "")),
                        entry.get("lokasi", ""),
                        entry.get("label", ""),
                        entry.get("teks_asli", ""),
                    ))
                mode = "Dry-run" if dry_run else "Redaksi final"
                status = f"{mode} selesai. {n_files} file diproses, {len(all_logs)} item terdeteksi."
                if errors:
                    status += f" {len(errors)} file gagal (lihat terminal)."
                self.status_var.set(status)
                self._set_buttons_enabled(True)
                if errors:
                    messagebox.showerror(
                        "Beberapa file gagal diproses",
                        "\n".join(f"{p}: {e}" for p, e in errors)
                    )
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _save_report(self):
        if not self.last_results:
            messagebox.showinfo("Belum ada hasil", "Jalankan Dry-Run atau Redaksi Final dulu.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="redact_report.csv"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "lokasi", "label", "teks_asli"])
            writer.writeheader()
            writer.writerows(self.last_results)
        messagebox.showinfo("Tersimpan", f"Report disimpan ke:\n{path}")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    app = RedactApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
