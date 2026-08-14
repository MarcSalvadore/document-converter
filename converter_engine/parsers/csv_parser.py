"""Parser for Comma-Separated Values (.csv) using csv module."""

import csv
import os
from typing import BinaryIO, List, Union

from converter_engine.parsers import BaseParser, ParsedDocumentResult


class CSVParser(BaseParser):
    """Parser for extracting Markdown from CSV files."""

    def parse(self, source: Union[str, bytes, BinaryIO]) -> ParsedDocumentResult:
        """Parse CSV document and return raw Markdown representation.

        Args:
            source: File path (str), raw bytes, or file-like binary stream.

        Returns:
            Markdown text representation of the document.
        """
        try:
            if isinstance(source, str):
                if not os.path.exists(source):
                    raise FileNotFoundError(f"CSV file not found at: {source}")
                with open(source, "rb") as f:
                    file_bytes = f.read()
            elif isinstance(source, bytes):
                file_bytes = source
            else:
                file_bytes = source.read()

        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to load CSV document: {e}") from e

        # Decode bytes
        text_content = ""
        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                text_content = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if not text_content:
            raise ValueError("Failed to decode CSV content with known encodings.")

        lines = text_content.splitlines()
        if not lines:
            return ParsedDocumentResult(markdown="", images={})

        # Use csv.Sniffer to detect delimiter
        sample = "\n".join(lines[:10])
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            # Fallback to default excel dialect if detection fails
            dialect = csv.excel

        reader = csv.reader(lines, dialect)
        rows = list(reader)

        if not rows:
            return ParsedDocumentResult(markdown="", images={})

        # Find header row
        header_idx = -1
        for idx, row in enumerate(rows):
            if any(cell.strip() != "" for cell in row):
                header_idx = idx
                break

        if header_idx == -1:
            return ParsedDocumentResult(markdown="", images={})

        headers = rows[header_idx]
        records = rows[header_idx + 1:]

        def sanitize(cell: str) -> str:
            return cell.replace("\n", "<br>").replace("|", "\\|").strip()

        sanitized_headers = [sanitize(cell) for cell in headers]
        
        separator = ["---"] * len(sanitized_headers)
        
        table_lines = [
            "| " + " | ".join(sanitized_headers) + " |",
            "| " + " | ".join(separator) + " |"
        ]
        
        for row in records:
            # Pad or truncate row to match headers length
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            
            sanitized_row = [sanitize(cell) for cell in row]
            table_lines.append("| " + " | ".join(sanitized_row) + " |")
            
        return ParsedDocumentResult(markdown="\n".join(table_lines), images={})
