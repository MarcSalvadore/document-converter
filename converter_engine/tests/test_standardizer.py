"""Unit tests for Standardizer post-processing engine."""

from converter_engine.core.standardizer import Standardizer


def test_standardize_empty_input():
    assert Standardizer.standardize("") == ""
    assert Standardizer.standardize(None) == ""


def test_standardize_bullet_characters():
    raw_md = "* Item 1\n+ Item 2\n  * Nested bullet\n  + Nested bullet 2"
    result = Standardizer.standardize(raw_md)

    assert "- Item 1" in result
    assert "- Item 2" in result
    assert "  - Nested bullet" in result
    assert "  - Nested bullet 2" in result


def test_standardize_consecutive_blank_lines():
    raw_md = "Paragraph 1\n\n\n\nParagraph 2\n\n\n\n\nParagraph 3"
    result = Standardizer.standardize(raw_md)

    expected = "Paragraph 1\n\nParagraph 2\n\nParagraph 3\n"
    assert result == expected


def test_standardize_trailing_whitespace():
    raw_md = "Line with trailing spaces   \nAnother line\t\t\nLine 3"
    result = Standardizer.standardize(raw_md)

    lines = result.splitlines()
    assert lines[0] == "Line with trailing spaces"
    assert lines[1] == "Another line"
    assert lines[2] == "Line 3"


def test_standardize_table_formatting():
    raw_md = "| Header A   |   Header B |\n|---|---|\n| Cell 1 | Cell 2 |"
    result = Standardizer.standardize(raw_md)

    assert "| Header A | Header B |" in result
    assert "| --- | --- |" in result
    assert "| Cell 1 | Cell 2 |" in result
