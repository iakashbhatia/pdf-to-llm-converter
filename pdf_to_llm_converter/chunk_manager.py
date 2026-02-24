"""Chunk manager for splitting large PDFs into manageable processing units."""

from __future__ import annotations

import math
from collections.abc import Iterator

import fitz

from pdf_to_llm_converter.models import PageRange


def get_page_count(pdf_path: str) -> int:
    """Get the total page count of a PDF without loading all pages into memory.

    Opens the PDF, reads the page count from metadata, and closes immediately.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        The number of pages in the PDF.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the file is not a valid PDF.
    """
    doc = fitz.open(pdf_path)
    try:
        count = len(doc)
    finally:
        doc.close()
    return count


class ChunkManager:
    """Splits large PDFs into page-range chunks for sequential processing."""

    def iter_chunks(self, pdf_path: str, chunk_size: int) -> Iterator[PageRange]:
        """Yield PageRange objects covering all pages of the PDF.

        Each PageRange has a start (inclusive) and end (exclusive) that together
        form a complete, non-overlapping partition of all pages.

        Args:
            pdf_path: Path to the PDF file.
            chunk_size: Maximum number of pages per chunk. Must be > 0.

        Yields:
            PageRange objects covering pages [0, total_pages) in order.

        Raises:
            ValueError: If chunk_size is not a positive integer.
            FileNotFoundError: If the file does not exist.
            RuntimeError: If the file is not a valid PDF.
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")

        total_pages = get_page_count(pdf_path)

        for start in range(0, total_pages, chunk_size):
            end = min(start + chunk_size, total_pages)
            yield PageRange(start=start, end=end)
