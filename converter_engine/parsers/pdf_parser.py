"""Parser for PDF documents using MIT/BSD licensed pdfminer.six and pdfplumber."""

from collections import Counter
import io
import os
from typing import BinaryIO, Dict, List, Optional, Tuple, Union
import pdfplumber
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTTextContainer, LTAnno

from converter_engine.parsers import BaseParser


class PDFParser(BaseParser):
    """Permissively licensed PDF Parser using pdfplumber & pdfminer.six."""

    def parse(self, source: Union[str, bytes, BinaryIO]) -> str:
        """Parse PDF document into Markdown.

        Args:
            source: File path (str), raw bytes, or file-like binary stream.

        Returns:
            Markdown formatted representation of the PDF content.
        """
        try:
            if isinstance(source, str):
                if not os.path.exists(source):
                    raise FileNotFoundError(f"PDF file not found at: {source}")
                pdf_target = source
            elif isinstance(source, bytes):
                pdf_target = io.BytesIO(source)
            else:
                pdf_target = source

            with pdfplumber.open(pdf_target) as pdf:
                if not pdf.pages:
                    return ""

                # 1. Analyze font size frequencies across entire document
                font_thresholds = self._calculate_font_thresholds(pdf)


                # 2. Extract page contents (text lines + tables)
                page_markdowns: List[str] = []
                total_chars_found = 0

                for page_num, page in enumerate(pdf.pages, start=1):
                    chars = page.chars
                    total_chars_found += len(chars)

                    page_md = self._parse_page(page, font_thresholds)
                    if page_md.strip():
                        page_markdowns.append(page_md)

                if total_chars_found == 0:
                    return "[Scanned or Image-Only PDF: No selectable text detected]"

                return "\n\n---\n\n".join(page_markdowns)

        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document: {e}") from e


    def _calculate_font_thresholds(self, pdf: pdfplumber.PDF) -> Dict[str, float]:
        """Collect character font sizes and determine H1, H2, H3 thresholds."""
        size_counter: Counter = Counter()

        for page in pdf.pages:
            for char in page.chars:
                text = char.get("text", "").strip()
                if text:
                    size = round(char.get("size", 0), 1)
                    if size > 0:
                        size_counter[size] += 1

        if not size_counter:
            return {"base": 10.0, "h1": 18.0, "h2": 14.0, "h3": 12.0}

        # Most common font size is the body text base size
        base_size = size_counter.most_common(1)[0][0]

        # Get unique font sizes larger than base size sorted descending
        larger_sizes = sorted([s for s in size_counter.keys() if s > base_size], reverse=True)

        h1_thresh = larger_sizes[0] if len(larger_sizes) > 0 else base_size * 1.4
        h2_thresh = larger_sizes[1] if len(larger_sizes) > 1 else (base_size * 1.25 if len(larger_sizes) > 0 else base_size * 1.25)
        h3_thresh = larger_sizes[2] if len(larger_sizes) > 2 else (base_size * 1.1 if len(larger_sizes) > 0 else base_size * 1.1)

        return {
            "base": base_size,
            "h1": h1_thresh,
            "h2": h2_thresh,
            "h3": h3_thresh,
        }

    def _parse_page(self, page: pdfplumber.page.Page, font_thresholds: Dict[str, float]) -> str:
        """Parse individual PDF page combining text layout and extracted tables."""
        # Find tables on the page
        tables = page.find_tables()
        table_bboxes = [t.bbox for t in tables]
        extracted_tables = page.extract_tables()

        # Collect page elements: (top_coordinate, type, content)
        elements: List[Tuple[float, str, str]] = []

        # Add tables to page elements
        for bbox, table_data in zip(table_bboxes, extracted_tables):
            top = bbox[1]  # top y-coordinate
            table_md = self._format_table(table_data)
            if table_md:
                elements.append((top, "table", table_md))

        # Extract text chars outside table bboxes
        chars_outside_tables = []
        for char in page.chars:
            top = char.get("top", 0)
            x0 = char.get("x0", 0)
            # Check if char falls inside any table bbox (x0, top, x1, bottom)
            in_table = any(
                (b[0] <= x0 <= b[2] and b[1] <= top <= b[3]) for b in table_bboxes
            )
            if not in_table:
                chars_outside_tables.append(char)

        # Group text chars into lines based on vertical 'top' coordinate (~3px tolerance)
        lines_data = self._group_chars_into_lines(chars_outside_tables)

        for line_top, line_text, avg_size, is_bold in lines_data:
            if not line_text.strip():
                continue

            # Classify header level or bold
            if avg_size >= font_thresholds["h1"]:
                formatted_line = f"# {line_text}"
            elif avg_size >= font_thresholds["h2"]:
                formatted_line = f"## {line_text}"
            elif avg_size >= font_thresholds["h3"]:
                formatted_line = f"### {line_text}"
            elif is_bold:
                formatted_line = f"**{line_text}**"
            else:
                formatted_line = line_text

            elements.append((line_top, "text", formatted_line))

        # Sort all page elements by vertical top position
        elements.sort(key=lambda item: item[0])

        page_blocks = [item[2] for item in elements]
        return "\n\n".join(page_blocks)

    def _group_chars_into_lines(self, chars: List[dict]) -> List[Tuple[float, str, float, bool]]:
        """Group characters into lines by top coordinate."""
        if not chars:
            return []

        # Sort chars by top y-coordinate, then x0
        sorted_chars = sorted(chars, key=lambda c: (round(c.get("top", 0), 1), c.get("x0", 0)))

        lines: List[List[dict]] = []
        current_line: List[dict] = []
        current_top: float = -1.0

        for c in sorted_chars:
            top = c.get("top", 0)
            if current_top < 0 or abs(top - current_top) <= 3.0:
                current_line.append(c)
                if current_top < 0:
                    current_top = top
            else:
                lines.append(current_line)
                current_line = [c]
                current_top = top

        if current_line:
            lines.append(current_line)

        result: List[Tuple[float, str, float, bool]] = []
        for line in lines:
            # Sort chars horizontally by x0
            line.sort(key=lambda c: c.get("x0", 0))
            text = "".join(c.get("text", "") for c in line).strip()
            if not text:
                continue

            sizes = [c.get("size", 10.0) for c in line]
            avg_size = sum(sizes) / len(sizes) if sizes else 10.0

            fontnames = [c.get("fontname", "").lower() for c in line]
            is_bold = any(("bold" in f or "black" in f or "heavy" in f) for f in fontnames)

            line_top = line[0].get("top", 0.0)
            result.append((line_top, text, avg_size, is_bold))

        return result

    def _format_table(self, table_data: List[List[Optional[str]]]) -> str:
        """Convert pdfplumber extracted 2D table grid to Markdown table."""
        if not table_data:
            return ""

        cleaned_rows: List[List[str]] = []
        for row in table_data:
            cleaned_row = []
            for cell in row:
                cell_text = (cell or "").replace("\n", "<br>").replace("|", "\\|").strip()
                cleaned_row.append(cell_text)
            cleaned_rows.append(cleaned_row)

        if not cleaned_rows:
            return ""

        header_row = cleaned_rows[0]
        col_count = len(header_row)
        if col_count == 0:
            return ""

        separator_row = ["---"] * col_count

        md_lines = [
            "| " + " | ".join(header_row) + " |",
            "| " + " | ".join(separator_row) + " |",
        ]

        for row in cleaned_rows[1:]:
            padded_row = row + [""] * (col_count - len(row))
            md_lines.append("| " + " | ".join(padded_row[:col_count]) + " |")

        return "\n".join(md_lines)
