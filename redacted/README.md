# Alat Redaksi/Masking Dokumen — Offline

Mask otomatis untuk: **nama perusahaan**, **NPWP**, **nomor rekening**, dan **alamat**.
Berjalan 100% offline (tidak ada panggilan internet/API sama sekali saat dipakai).
Mendukung file: `.docx`, `.xlsx`, `.csv`, `.pdf`.

## 1. Install (sekali saja, butuh internet saat instalasi)

```bash
pip install -r requirements.txt --break-system-packages
```

Untuk PDF, perlu **poppler** terpasang di sistem (untuk render halaman):
- Ubuntu/Debian: `sudo apt install poppler-utils`
- macOS: `brew install poppler`
- Windows: download poppler, tambahkan folder `bin`-nya ke PATH.

Setelah semua terpasang, tool ini **tidak butuh internet lagi** — aman dipakai
untuk dokumen rahasia/internal karena tidak ada data yang keluar dari komputer kamu.

## 2. Siapkan daftar nama perusahaan (opsional tapi disarankan)

Edit `companies_example.txt`, isi nama-nama perusahaan spesifik yang kamu tahu
akan muncul di dokumen. Deteksi berbasis daftar ini jauh lebih akurat daripada
deteksi otomatis, terutama untuk nama yang tidak selalu diikuti "PT"/"Tbk".

## 3. Pakai GUI (Windows) atau command line

**Opsi A — GUI:**
```
python gui.py
```
Alurnya: pilih file/folder input → isi/paste daftar nama perusahaan →
centang jenis deteksi yang mau dipakai → klik **"Cek Dulu (Dry-Run)"** →
review tabel hasil → kalau sudah sesuai, pilih folder output dan klik
**"Jalankan Redaksi (Final)"**.

Khusus Windows untuk fitur PDF, download poppler untuk Windows dari:
https://github.com/oschwartz10612/poppler-windows/releases
Extract, lalu tambahkan folder `...\poppler-xx\Library\bin` ke PATH Windows
(Settings → Edit environment variables → Path → New). Tanpa ini, deteksi
untuk .docx/.xlsx/.csv tetap jalan normal, tapi fitur PDF akan error.

**Opsi B — command line** (lebih cocok untuk banyak file sekaligus / dijadwalkan otomatis):

## 3c. Khusus PDF: logo dan watermark yang tidak terdeteksi teks biasa

Beberapa PDF (terutama slide/presentasi) punya nama perusahaan dalam bentuk
**logo (gambar)** atau **watermark diagonal/rotasi**. Keduanya tidak bisa
dideteksi lewat pencocokan teks biasa. Alurnya:

```bash
# 1. Inspeksi dulu -- render tiap halaman + crop tiap gambar embed
python inspect_pdf.py dokumen.pdf --out inspeksi/

# 2. Kalau curiga ada watermark/teks rotasi berisi nama tertentu, cari posisinya:
python inspect_pdf.py dokumen.pdf --out inspeksi/ --search "Nama Yang Dicurigai"
```

Buka folder `inspeksi/`: `page_N.png` untuk lihat tata letak halaman,
`page_N_img_K.png` untuk lihat isi tiap gambar satu-satu (cari mana yang
logo perusahaan), `image_manifest.csv` untuk koordinatnya, dan
`search_report.csv` untuk koordinat kata yang kamu cari lewat `--search`.

**PENTING — ini bukan langkah otomatis:** koordinat dari `image_manifest.csv`
atau `search_report.csv` **wajib dicek dulu apakah areanya menabrak
teks/diagram lain** sebelum dipakai untuk blackout. Watermark besar yang
diagonal, misalnya, bounding box-nya bisa membentang ke seluruh halaman dan
menghitamkan isi diagram kalau langsung dipakai mentah-mentah — perlu
dipecah per bagian yang benar-benar aman.

Setelah yakin, catat koordinat yang aman ke `manual_regions.csv`:
```csv
file,page,x0,y0,x1,y1
dokumen.pdf,1,170.6,307.2,283.6,349.4
```
(`file` = nama file persis, `page` = nomor halaman mulai dari 1, `x0,y0,x1,y1`
= koordinat dalam satuan point PDF, sama seperti di manifest -- tidak perlu dikonversi)

Lalu jalankan redaksi dengan tambahan region manual ini:
```bash
python redact_tool.py --input dokumen.pdf --company-list companies_example.txt \
    --manual-regions manual_regions.csv --output hasil/
```
Atau di GUI: isi field "Region manual" di bagian 4 dengan file CSV ini.
Tombol "Buka Alat Inspeksi PDF..." di GUI menjalankan langkah 1 di atas untukmu.

## 4. WAJIB: jalankan dry-run dulu

```bash
python redact_tool.py --input ./folder_dokumen --company-list companies_example.txt --dry-run
```

Ini tidak mengubah file apa pun. Cek `redact_report.csv` yang dihasilkan —
lihat kolom `teks_asli` untuk pastikan yang ter-deteksi memang benar-benar
sensitif, dan tidak ada yang penting (misalnya nomor invoice) ikut ke-mask,
atau sebaliknya ada info sensitif yang lolos tidak terdeteksi.

**Catatan:** `redact_report.csv` berisi teks asli yang sensitif (belum di-mask).
Simpan/hapus file ini dengan hati-hati, jangan ikut dibagikan.

## 4. Jalankan redaksi sungguhan

```bash
python redact_tool.py --input ./folder_dokumen --company-list companies_example.txt --output ./hasil_redaksi
```

File hasil akan ada di folder `--output`, dengan nama file sama seperti aslinya.

## Opsi tambahan

```
--no-company-auto   Matikan deteksi otomatis PT/CV/Tbk/Group/dst, hanya pakai company-list
--no-npwp           Matikan deteksi NPWP
--no-rekening       Matikan deteksi nomor rekening
--no-address        Matikan deteksi alamat
```

## Batasan yang perlu kamu sadari (baca sebelum dipakai untuk dokumen penting)

1. **Ini rule-based (regex + daftar kata), bukan AI/NER.** Lebih bisa diprediksi
   dan diaudit dibanding model NER umum, tapi tetap bisa salah:
   - Nama perusahaan tanpa "PT"/"CV"/"Tbk" dan tidak ada di company-list **tidak
     akan terdeteksi**. Selalu lengkapi company-list dengan semua nama yang kamu tahu.
   - Nomor rekening dideteksi dari kata kunci di dekatnya ("No. Rekening", dst).
     Angka 8-16 digit tanpa konteks kata kunci di dekatnya bisa lolos.
   - Alamat dideteksi dari kata kunci baku (Jl., Kel., Kec., RT/RW, dst). Alamat
     yang ditulis tidak baku bisa lolos.
2. **PDF hasil redaksi kehilangan layer teks sepenuhnya** (jadi gambar). Ini
   sengaja, supaya bagian yang di-redact benar-benar tidak bisa di-copy-paste.
   Konsekuensinya: seluruh dokumen (bukan cuma bagian sensitif) tidak lagi bisa
   di-search/copy teksnya. Kalau butuh PDF yang tetap bisa di-search, itu perlu
   pendekatan berbeda dengan risiko keamanan lebih tinggi (teks asli masih ada
   di balik kotak hitam) — tidak disediakan di tool ini karena tidak aman untuk
   tujuan kerahasiaan.
3. **Format Word tidak 100% dipertahankan** pada paragraf yang kena redaksi —
   variasi bold/italic/warna di dalam satu kalimat yang di-mask akan disederhanakan.
4. **Selalu review manual** (`--dry-run` + cek report) sebelum mengirim dokumen
   hasil redaksi ke pihak luar. Tidak ada tool otomatis yang bisa dijamin 100% —
   terutama untuk kebutuhan compliance/legal, anggap ini sebagai *first pass*,
   bukan pengganti pemeriksaan manusia.
