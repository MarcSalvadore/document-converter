"""Parser for Excel spreadsheets (.xlsx) using openpyxl."""

import io
import os
import datetime
from typing import BinaryIO, List, Union

import openpyxl

from converter_engine.parsers import BaseParser, ParsedDocumentResult


class XLSXParser(BaseParser):
    """Parser for extracting Markdown from XLSX files."""

    def parse(self, source: Union[str, bytes, BinaryIO]) -> ParsedDocumentResult:
        """Parse XLSX document and return raw Markdown representation.

        Args:
            source: File path (str), raw bytes, or file-like binary stream.

        Returns:
            Markdown text representation of the document.
        """
        try:
            if isinstance(source, str):
                if not os.path.exists(source):
                    raise FileNotFoundError(f"XLSX file not found at: {source}")
                with open(source, "rb") as f:
                    file_bytes = f.read()
            elif isinstance(source, bytes):
                file_bytes = source
            else:
                file_bytes = source.read()

            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to load XLSX document: {e}") from e

        md_blocks: List[str] = []

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            
            # Read all rows and columns
            raw_data = []
            for row in sheet.iter_rows(values_only=True):
                formatted_row = []
                for cell in row:
                    if cell is None:
                        formatted_row.append("")
                    elif isinstance(cell, datetime.datetime):
                        formatted_row.append(cell.strftime("%Y-%m-%d %H:%M:%S"))
                    elif isinstance(cell, datetime.date):
                        formatted_row.append(cell.strftime("%Y-%m-%d"))
                    elif isinstance(cell, float):
                        formatted_row.append(f"{cell:g}") # use general format for floats to avoid trailing zeros
                    else:
                        formatted_row.append(str(cell))
                raw_data.append(formatted_row)

            # Drop trailing empty rows
            while raw_data and all(cell == "" for cell in raw_data[-1]):
                raw_data.pop()
                
            if not raw_data:
                continue

            # Drop completely blank columns
            num_cols = len(raw_data[0])
            cols_to_keep = []
            for col_idx in range(num_cols):
                if any(row[col_idx] != "" for row in raw_data if col_idx < len(row)):
                    cols_to_keep.append(col_idx)

            if not cols_to_keep:
                continue
                
            cleaned_data = []
            for row in raw_data:
                cleaned_row = [row[i] if i < len(row) else "" for i in cols_to_keep]
                
                # Sanitize content
                sanitized_row = [cell.replace("\n", "<br>").replace("|", "\\|").strip() for cell in cleaned_row]
                cleaned_data.append(sanitized_row)

            # Find the first non-empty row to use as header
            header_idx = -1
            for idx, row in enumerate(cleaned_data):
                if any(cell != "" for cell in row):
                    header_idx = idx
                    break
                    
            if header_idx == -1:
                continue

            headers = cleaned_data[header_idx]
            records = cleaned_data[header_idx + 1:]

            md_blocks.append(f"## Sheet: {sheet_name}\n")
            
            # Build Markdown table
            separator = ["---"] * len(headers)
            
            table_lines = [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(separator) + " |"
            ]
            
            for row in records:
                table_lines.append("| " + " | ".join(row) + " |")
                
            md_blocks.append("\n".join(table_lines))

        return ParsedDocumentResult(markdown="\n\n".join(md_blocks), images={})
