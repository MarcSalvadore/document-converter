"""Document Router for file type detection and parser dispatching."""

import io
import os
import zipfile
from typing import Optional

import sys

# Workaround for local 'markitdown' folder conflicting with pip package
_cwd = os.getcwd()
if _cwd in sys.path:
    sys.path.remove(_cwd)
if '' in sys.path:
    sys.path.remove('')
    
from markitdown import MarkItDown

if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

from converter_engine.core.standardizer import Standardizer
from converter_engine.parsers import ParsedDocumentResult


class DocumentRouter:
    """Ingestion & file type router for document to Markdown conversion."""

    def __init__(self):
        self._md = MarkItDown(enable_plugins=False)
        from converter_engine.parsers.pdf_parser import LegalPdfConverter
        from converter_engine.parsers.pptx_parser import PPTXParser
        from converter_engine.parsers.docx_parser import DOCXParser
        from converter_engine.parsers.image_parser import ImageParser
        
        self._md.register_converter(LegalPdfConverter(), priority=-1.0)
        self._md.register_converter(PPTXParser(), priority=-1.0)
        self._md.register_converter(DOCXParser(), priority=-1.0)
        self._md.register_converter(ImageParser(), priority=-1.0)

    def convert(self, file_path: str) -> ParsedDocumentResult:
        """Convert document at file_path to standardized Markdown and images.

        Args:
            file_path: Path to DOCX, PPTX, or PDF document.

        Returns:
            Standardized Markdown text.

        Raises:
            FileNotFoundError: If target file does not exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        result = self._md.convert(file_path)
        raw_markdown = result.text_content if hasattr(result, "text_content") else getattr(result, "markdown", "")
        cleaned_md = Standardizer.standardize(raw_markdown)

        return ParsedDocumentResult(markdown=cleaned_md, images={})

    def convert_bytes(self, file_bytes: bytes, filename: Optional[str] = None) -> ParsedDocumentResult:
        """Convert document from raw bytes in memory to standardized Markdown and images.

        Args:
            file_bytes: Raw binary content of document.
            filename: Optional original filename for extension detection fallback.

        Returns:
            Standardized Markdown text.

        Raises:
            ValueError: If file payload is empty.
        """
        if not file_bytes:
            raise ValueError("Empty file payload received.")

        ext = ""
        if filename and "." in filename:
            ext = filename.rsplit('.', 1)[-1].lower()

        stream = io.BytesIO(file_bytes)
        result = self._md.convert_stream(stream, file_extension=f".{ext}" if ext else None)
        
        raw_markdown = result.text_content if hasattr(result, "text_content") else getattr(result, "markdown", "")
        cleaned_md = Standardizer.standardize(raw_markdown)

        return ParsedDocumentResult(markdown=cleaned_md, images={})
