"""Parser for PPTX presentations using python-pptx."""

import io
import os
from typing import BinaryIO, List, Optional, Union
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.autoshape import Shape
from pptx.text.text import _Paragraph

from converter_engine.parsers import BaseParser


class PPTXParser(BaseParser):
    """Parser for extracting Markdown from PPTX files."""

    def parse(self, source: Union[str, bytes, BinaryIO]) -> str:
        """Parse PPTX presentation and return Markdown representation.

        Args:
            source: File path (str), raw bytes, or file-like binary stream.

        Returns:
            Markdown text representation of the slides.
        """
        try:
            if isinstance(source, str):
                if not os.path.exists(source):
                    raise FileNotFoundError(f"PPTX file not found at: {source}")
                prs = pptx.Presentation(source)
            elif isinstance(source, bytes):
                prs = pptx.Presentation(io.BytesIO(source))
            else:
                prs = pptx.Presentation(source)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to load PPTX presentation: {e}") from e

        slides_md: List[str] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            slide_blocks: List[str] = []

            # Add explicit slide divider header
            slide_header = f"--- \n\n**Slide {slide_num}**"
            
            # Check for slide title
            title_text = ""
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title_text = slide.shapes.title.text_frame.text.strip()
                if title_text:
                    slide_header = f"--- \n\n## Slide {slide_num}: {title_text}"

            slide_blocks.append(slide_header)

            # Process shapes on the slide
            for shape in slide.shapes:
                # Skip title shape if already processed above
                if slide.shapes.title and shape == slide.shapes.title:
                    continue

                if shape.has_text_frame:
                    tf_md = self._parse_text_frame(shape.text_frame)
                    if tf_md.strip():
                        slide_blocks.append(tf_md)
                elif shape.has_table:
                    table_md = self._parse_table(shape.table)
                    if table_md.strip():
                        slide_blocks.append(table_md)

            slides_md.append("\n\n".join(slide_blocks))

        return "\n\n".join(slides_md)

    def _parse_text_frame(self, text_frame) -> str:
        """Format text frame paragraphs into Markdown keeping indent hierarchy."""
        lines: List[str] = []

        for para in text_frame.paragraphs:
            text = self._parse_paragraph_runs(para).strip()
            if not text:
                continue

            level = max(0, para.level if para.level is not None else 0)
            indent = "  " * level
            lines.append(f"{indent}- {text}")

        return "\n".join(lines)

    def _parse_paragraph_runs(self, para: _Paragraph) -> str:
        """Extract text from paragraph runs with inline bold/italic formatting."""
        formatted_pieces: List[str] = []

        for run in para.runs:
            text = run.text
            if not text:
                continue

            l_space = " " if text.startswith(" ") and len(text) > 1 else ""
            r_space = " " if text.endswith(" ") and len(text) > 1 else ""
            core_text = text.strip()

            if not core_text:
                formatted_pieces.append(text)
                continue

            if run.font and (run.font.bold and run.font.italic):
                core_text = f"***{core_text}***"
            elif run.font and run.font.bold:
                core_text = f"**{core_text}**"
            elif run.font and run.font.italic:
                core_text = f"*{core_text}*"

            formatted_pieces.append(f"{l_space}{core_text}{r_space}")

        result = "".join(formatted_pieces)
        return result if result else para.text

    def _parse_table(self, table) -> str:
        """Convert PPTX shape table to Markdown table."""
        if not table.rows:
            return ""

        rows_data: List[List[str]] = []

        for row in table.rows:
            row_cells = []
            for cell in row.cells:
                # Format text frame inside table cell
                cell_text = cell.text.replace("\n", "<br>").replace("|", "\\|").strip()
                row_cells.append(cell_text)
            rows_data.append(row_cells)

        if not rows_data:
            return ""

        header_row = rows_data[0]
        col_count = len(header_row)
        if col_count == 0:
            return ""

        separator_row = ["---"] * col_count

        md_lines = [
            "| " + " | ".join(header_row) + " |",
            "| " + " | ".join(separator_row) + " |",
        ]

        for row in rows_data[1:]:
            padded_row = row + [""] * (col_count - len(row))
            md_lines.append("| " + " | ".join(padded_row[:col_count]) + " |")

        return "\n".join(md_lines)
