"""Unit tests for DocumentRouter and file type detection."""

import os
import pytest

from converter_engine.core.router import DocumentRouter


def test_detect_file_type(sample_docx, sample_pptx, sample_pdf, unsupported_file):
    router = DocumentRouter()

    assert router.detect_file_type(sample_docx) == "docx"
    assert router.detect_file_type(sample_pptx) == "pptx"
    assert router.detect_file_type(sample_pdf) == "pdf"
    assert router.detect_file_type(unsupported_file) == "unknown"


def test_detect_file_type_from_bytes(sample_docx_bytes, sample_pptx_bytes, sample_pdf_bytes):
    router = DocumentRouter()

    assert router.detect_file_type_from_bytes(sample_docx_bytes, "doc.docx") == "docx"
    assert router.detect_file_type_from_bytes(sample_pptx_bytes, "deck.pptx") == "pptx"
    assert router.detect_file_type_from_bytes(sample_pdf_bytes, "report.pdf") == "pdf"
    assert router.detect_file_type_from_bytes(b"some random text", "file.txt") == "unknown"


def test_router_convert_docx(sample_docx):
    router = DocumentRouter()
    result = router.convert(sample_docx)
    assert "# Synthetic Document Title" in result
    assert "Section One Header" in result
    assert "**bold text**" in result
    assert "*italic text*" in result


def test_router_convert_pptx(sample_pptx):
    router = DocumentRouter()
    result = router.convert(sample_pptx)
    assert "Slide 1: Overview" in result
    assert "Slide 2: Summary Data" in result


def test_router_convert_pdf(sample_pdf):
    router = DocumentRouter()
    result = router.convert(sample_pdf)
    assert "PDF Report Title" in result
    assert "Section One" in result


def test_router_convert_bytes(sample_docx_bytes, sample_pptx_bytes, sample_pdf_bytes):
    router = DocumentRouter()

    res_docx = router.convert_bytes(sample_docx_bytes, "sample.docx")
    assert "# Synthetic Document Title" in res_docx

    res_pptx = router.convert_bytes(sample_pptx_bytes, "sample.pptx")
    assert "Slide 1: Overview" in res_pptx

    res_pdf = router.convert_bytes(sample_pdf_bytes, "sample.pdf")
    assert "PDF Report Title" in res_pdf


def test_router_unsupported_format(unsupported_file):
    router = DocumentRouter()
    with pytest.raises(ValueError) as exc_info:
        router.convert(unsupported_file)
    assert "Unsupported document format" in str(exc_info.value)


def test_router_file_not_found():
    router = DocumentRouter()
    with pytest.raises(FileNotFoundError) as exc_info:
        router.convert("non_existent_file.docx")
    assert "File not found" in str(exc_info.value)


def test_router_empty_bytes():
    router = DocumentRouter()
    with pytest.raises(ValueError) as exc_info:
        router.convert_bytes(b"", "empty.docx")
    assert "Empty file payload" in str(exc_info.value)
