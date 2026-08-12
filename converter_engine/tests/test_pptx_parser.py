"""Unit tests for PPTXParser engine."""

import pytest
from converter_engine.parsers.pptx_parser import PPTXParser


def test_pptx_parser_slides(sample_pptx):
    parser = PPTXParser()
    md = parser.parse(sample_pptx)

    # Verify slide boundary separators
    assert "---" in md
    # Verify slide headings
    assert "Slide 1" in md
    assert "Overview" in md
    assert "Slide 2" in md


def test_pptx_parser_bullets(sample_pptx):
    parser = PPTXParser()
    md = parser.parse(sample_pptx)

    assert "- Main bullet point" in md
    assert "  - Sub-bullet detail item" in md


def test_pptx_parser_table(sample_pptx):
    parser = PPTXParser()
    md = parser.parse(sample_pptx)

    assert "| Metric | Score |" in md
    assert "| --- | --- |" in md
    assert "| Accuracy | 99% |" in md


def test_pptx_parser_bytes(sample_pptx_bytes):
    parser = PPTXParser()
    md = parser.parse(sample_pptx_bytes)

    assert "Slide 1" in md
    assert "| Metric | Score |" in md



def test_pptx_parser_file_not_found():
    parser = PPTXParser()
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_presentation.pptx")


def test_pptx_parser_corrupted_file(corrupted_file):
    parser = PPTXParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(corrupted_file)
    assert "Failed to load PPTX presentation" in str(exc_info.value)
