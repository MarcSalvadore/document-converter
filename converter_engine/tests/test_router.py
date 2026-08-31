"""Unit tests for DocumentRouter."""

import os
import pytest

from converter_engine.core.router import DocumentRouter


def test_router_convert_docx(sample_docx):
    router = DocumentRouter()
    result = router.convert(sample_docx)
    assert "Synthetic Document Title" in result.markdown
    assert "Section One Header" in result.markdown
    assert "**bold text**" in result.markdown
    assert "*italic text*" in result.markdown


def test_router_convert_pptx(sample_pptx):
    router = DocumentRouter()
    result = router.convert(sample_pptx)
    assert "Slide 1: Overview" in result.markdown
    assert "Slide 2: Summary Data" in result.markdown


def test_router_convert_pdf(sample_pdf):
    router = DocumentRouter()
    result = router.convert(sample_pdf)
    assert "PDF Report Title" in result.markdown
    assert "Section One" in result.markdown


def test_router_convert_bytes(sample_docx_bytes, sample_pptx_bytes, sample_pdf_bytes):
    router = DocumentRouter()

    res_docx = router.convert_bytes(sample_docx_bytes, "sample.docx")
    assert "Synthetic Document Title" in res_docx.markdown

    res_pptx = router.convert_bytes(sample_pptx_bytes, "sample.pptx")
    assert "Slide 1: Overview" in res_pptx.markdown

    res_pdf = router.convert_bytes(sample_pdf_bytes, "sample.pdf")
    assert "PDF Report Title" in res_pdf.markdown


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
