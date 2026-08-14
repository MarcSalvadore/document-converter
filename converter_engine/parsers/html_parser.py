"""Parser for HTML files using BeautifulSoup and markdownify."""

import os
from typing import BinaryIO, Union

from bs4 import BeautifulSoup
import markdownify

from converter_engine.parsers import BaseParser


class HTMLParser(BaseParser):
    """Parser for extracting Markdown from HTML files."""

    def parse(self, source: Union[str, bytes, BinaryIO]) -> str:
        """Parse HTML document and return raw Markdown representation.

        Args:
            source: File path (str), raw bytes, or file-like binary stream.

        Returns:
            Markdown text representation of the document.
        """
        try:
            if isinstance(source, str):
                if not os.path.exists(source):
                    raise FileNotFoundError(f"HTML file not found at: {source}")
                with open(source, "rb") as f:
                    file_bytes = f.read()
            elif isinstance(source, bytes):
                file_bytes = source
            else:
                file_bytes = source.read()

        except FileNotFoundError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to load HTML document: {e}") from e

        # Decode bytes
        html_content = ""
        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                html_content = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not html_content:
            raise ValueError("Failed to decode HTML content with known encodings.")

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unneeded tags
            for tag in soup(["script", "style", "noscript", "header", "footer", "svg"]):
                tag.decompose()
                
            soup_str = str(soup)
            
            # Convert to markdown
            md = markdownify.markdownify(soup_str, heading_style="ATX", strip=['a'])
            
            return md.strip()
        except Exception as e:
            raise ValueError(f"Failed to parse HTML content: {e}") from e
