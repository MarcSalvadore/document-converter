# Document-to-Markdown Converter (`converter_engine`)

A production-ready Python tool, CLI, FastAPI REST API, single-page Web UI, and Dockerized service for converting Microsoft Word (`.docx`), PowerPoint (`.pptx`), and PDF (`.pdf`) documents into clean, standardized Markdown format.

---

## Features

- **Modern Web UI**: Single-page web application featuring drag-and-drop file upload, live formatted HTML preview (`marked.js`), raw Markdown code view, one-click copy, and `.md` file download.
- **Multi-Format Ingestion**: Supports `.docx`, `.pptx`, and `.pdf` files.
- **In-Memory Streaming**: Converts documents entirely in memory using byte buffers (`io.BytesIO`) without temporary disk overhead.
- **REST API**: Exposes production FastAPI endpoints (`POST /v1/convert`, `GET /health`) with OpenAPI (`/docs`) interactive documentation.
- **CLI Interface**: Command-line execution via Typer with verbose execution timers and status reporting.
- **Dockerized**: Containerized multi-stage Docker build (`python:3.11-slim`) with non-root security context and Docker Compose orchestration.
- **Automated Test Suite**: 34 Pytest unit/integration tests with synthetic test generators (`reportlab`, `python-docx`, `python-pptx`).

---

## Prerequisites

- **Python**: 3.10+ (Python 3.13 recommended)
- **Docker** (optional, for containerized deployment)
- **Git**

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MarcSalvadore/document-converter.git
   cd document-converter
   ```

2. **Create a virtual environment:**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r converter_engine/requirements.txt
   ```

---

## Quick Start

### 1. Web UI & FastAPI Server

Start the web application server:

```powershell
py -3.13 -m uvicorn converter_engine.api.main:app --host 127.0.0.1 --port 8000
```

```bash
python -m uvicorn converter_engine.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at: **`http://localhost:8000`**

---

### 2. Command-Line Interface (CLI)

```bash
# Convert file to output markdown
python -m converter_engine.main --input document.docx --output output.md

# Convert with verbose logs
python -m converter_engine.main -i presentation.pptx -o output.md --verbose
```

---

### 3. Docker Compose

```bash
docker compose up --build
```

Access Web UI at `http://localhost:8000`.

---

## Automated Tests

Run the Pytest suite:

```bash
pytest converter_engine/tests -v
```

---

## Project Structure

```text
document-converter/
├── converter_engine/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI Application, Static Mounting & Error Handlers
│   │   └── routes.py          # API endpoints (/health, /v1/convert)
│   ├── core/
│   │   ├── router.py          # DocumentRouter file & stream detection
│   │   └── standardizer.py    # Markdown post-processing & cleanup
│   ├── parsers/
│   │   ├── docx_parser.py     # python-docx Parser implementation
│   │   ├── pptx_parser.py     # python-pptx Parser implementation
│   │   └── pdf_parser.py      # pdfplumber PDF layout Parser implementation
│   ├── static/
│   │   └── index.html         # Single-Page Web UI Application
│   ├── tests/                 # Automated Pytest suite (34 tests)
│   │   ├── conftest.py        # Synthetic test file fixtures
│   │   ├── test_router.py
│   │   ├── test_docx_parser.py
│   │   ├── test_pptx_parser.py
│   │   ├── test_pdf_parser.py
│   │   ├── test_standardizer.py
│   │   └── test_ui_routes.py
│   ├── Dockerfile             # Multi-stage Docker build
│   ├── docker-compose.yml
│   └── requirements.txt
└── README.md
```
