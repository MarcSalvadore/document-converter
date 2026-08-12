"""Unit tests for DOCXParser engine."""

import pytest
from converter_engine.parsers.docx_parser import DOCXParser


def test_docx_parser_headings_and_content(sample_docx):
    parser = DOCXParser()
    md = parser.parse(sample_docx)

    assert "# Synthetic Document Title" in md
    assert "# Section One Header" in md
    assert "## Subsection Header" in md


def test_docx_parser_inline_formatting(sample_docx):
    parser = DOCXParser()
    md = parser.parse(sample_docx)

    assert "**bold text**" in md
    assert "*italic text*" in md


def test_docx_parser_lists(sample_docx):
    parser = DOCXParser()
    md = parser.parse(sample_docx)

    assert "- First bullet item" in md
    assert "- Second bullet item" in md
    assert "1. First numbered item" in md
    assert "1. Second numbered item" in md


def test_docx_parser_table(sample_docx):
    parser = DOCXParser()
    md = parser.parse(sample_docx)

    assert "| Col 1 | Col 2 | Col 3 |" in md
    assert "| --- | --- | --- |" in md
    assert "| Val A | Val B | Val C |" in md


def test_docx_parser_bytes(sample_docx_bytes):
    parser = DOCXParser()
    md = parser.parse(sample_docx_bytes)

    assert "# Synthetic Document Title" in md
    assert "| Col 1 | Col 2 | Col 3 |" in md


def test_docx_parser_file_not_found():
    parser = DOCXParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_document.docx")


def test_docx_parser_corrupted_file(corrupted_file):
    parser = DOCXParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(corrupted_file)
    assert "Failed to load DOCX document" in str(exc_info.value)
