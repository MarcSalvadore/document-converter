"""Document Router for file type detection and parser dispatching."""

import io
import os
import zipfile
from typing import Dict, Optional, Type

from converter_engine.core.standardizer import Standardizer
from converter_engine.parsers import BaseParser
from converter_engine.parsers.docx_parser import DOCXParser
from converter_engine.parsers.pptx_parser import PPTXParser
from converter_engine.parsers.pdf_parser import PDFParser


class DocumentRouter:
    """Ingestion & file type router for document to Markdown conversion."""

    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {
            "docx": DOCXParser(),
            "pptx": PPTXParser(),
            "pdf": PDFParser(),
        }

    def convert(self, file_path: str) -> str:
        """Convert document at file_path to standardized Markdown.

        Args:
            file_path: Path to DOCX, PPTX, or PDF document.

        Returns:
            Standardized Markdown text.

        Raises:
            FileNotFoundError: If target file does not exist.
            ValueError: If file type is unsupported or file is corrupted.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_type = self.detect_file_type(file_path)

        if file_type not in self._parsers:
            raise ValueError(
                f"Unsupported document format '{file_type}'. "
                f"Supported formats: {list(self._parsers.keys())}"
            )

        parser = self._parsers[file_type]
        raw_md = parser.parse(file_path)
        standardized_md = Standardizer.standardize(raw_md)

        return standardized_md

    def convert_bytes(self, file_bytes: bytes, filename: Optional[str] = None) -> str:
        """Convert document from raw bytes in memory to standardized Markdown.

        Args:
            file_bytes: Raw binary content of document.
            filename: Optional original filename for extension detection fallback.

        Returns:
            Standardized Markdown text.

        Raises:
            ValueError: If file type is unsupported or file is corrupted.
        """
        if not file_bytes:
            raise ValueError("Empty file payload received.")

        file_type = self.detect_file_type_from_bytes(file_bytes, filename)

        if file_type not in self._parsers:
            raise ValueError(
                f"Unsupported document format '{file_type}'. "
                f"Supported formats: {list(self._parsers.keys())}"
            )

        parser = self._parsers[file_type]
        raw_md = parser.parse(file_bytes)
        standardized_md = Standardizer.standardize(raw_md)

        return standardized_md

    def detect_file_type(self, file_path: str) -> str:
        """Detect document format via magic bytes and container structure with extension fallback.

        Args:
            file_path: Path to input document file.

        Returns:
            Normalized file type string ('docx', 'pptx', 'pdf').
        """
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")

        try:
            with open(file_path, "rb") as f:
                header = f.read(1024)

            # PDF Detection: %PDF-
            if header.startswith(b"%PDF-"):
                return "pdf"

            # ZIP container detection (DOCX & PPTX)
            if header.startswith(b"PK\x03\x04"):
                try:
                    with zipfile.ZipFile(file_path, "r") as zf:
                        namelist = zf.namelist()
                        if any(name.startswith("word/") for name in namelist):
                            return "docx"
                        if any(name.startswith("ppt/") for name in namelist):
                            return "pptx"
                except zipfile.BadZipFile:
                    pass

        except Exception:
            pass

        # Fallback to extension matching
        if ext in ("docx", "pptx", "pdf"):
            return ext

        return "unknown"

    def detect_file_type_from_bytes(self, file_bytes: bytes, filename: Optional[str] = None) -> str:
        """Detect document format from in-memory byte buffer.

        Args:
            file_bytes: Raw bytes of document.
            filename: Optional filename for fallback extension check.

        Returns:
            Normalized file type string ('docx', 'pptx', 'pdf').
        """
        ext = ""
        if filename:
            ext = os.path.splitext(filename)[1].lower().lstrip(".")

        header = file_bytes[:1024]

        # PDF Detection
        if header.startswith(b"%PDF-"):
            return "pdf"

        # ZIP container detection (DOCX & PPTX)
        if header.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                    namelist = zf.namelist()
                    if any(name.startswith("word/") for name in namelist):
                        return "docx"
                    if any(name.startswith("ppt/") for name in namelist):
                        return "pptx"
            except zipfile.BadZipFile:
                pass

        if ext in ("docx", "pptx", "pdf"):
            return ext

        return "unknown"
