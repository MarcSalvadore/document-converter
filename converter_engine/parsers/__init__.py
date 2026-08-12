"""Parsers package for document conversion engine."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Union


class BaseParser(ABC):
    """Abstract base class for all document parsers."""

    @abstractmethod
    def parse(self, source: Union[str, bytes, BinaryIO]) -> str:
        """Parse document from file_path, raw bytes, or stream, and return raw Markdown text."""
        pass

