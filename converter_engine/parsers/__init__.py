"""Parsers package for document conversion engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Dict, Union

@dataclass
class ParsedDocumentResult:
    markdown: str
    images: Dict[str, bytes]  # key: relative path (e.g. "assets/img_1.png"), value: raw bytes



class BaseParser(ABC):
    """Abstract base class for all document parsers."""

    @abstractmethod
    def parse(self, source: Union[str, bytes, BinaryIO]) -> ParsedDocumentResult:
        """Parse document from file_path, raw bytes, or stream, and return raw Markdown text and images."""
        pass

