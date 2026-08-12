"""Unit tests for PDFParser engine."""

import pytest
from converter_engine.parsers.pdf_parser import PDFParser


def test_pdf_parser_extraction(sample_pdf):
    parser = PDFParser()
    md = parser.parse(sample_pdf)

    # Verify heading hierarchy detection
    assert "PDF Report Title" in md
    assert "Section One" in md
    assert "This is body paragraph content inside the generated PDF document." in md


def test_pdf_parser_table(sample_pdf):
    parser = PDFParser()
    md = parser.parse(sample_pdf)

    assert "| Header A | Header B |" in md
    assert "| --- | --- |" in md
    assert "| Cell 1 | Cell 2 |" in md


def test_pdf_parser_bytes(sample_pdf_bytes):
    parser = PDFParser()
    md = parser.parse(sample_pdf_bytes)

    assert "PDF Report Title" in md
    assert "| Header A | Header B |" in md


def test_pdf_parser_file_not_found():
    parser = PDFParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_document.pdf")


def test_pdf_parser_corrupted_file(corrupted_file):
    parser = PDFParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(corrupted_file)
    assert "Failed to parse PDF document" in str(exc_info.value)
