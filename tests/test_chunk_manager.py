"""Tests for ChunkManager.iter_chunks() and get_page_count()."""

from __future__ import annotations

import math
import os
import tempfile

import fitz
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pdf_to_llm_converter.chunk_manager import ChunkManager, get_page_count
from pdf_to_llm_converter.models import PageRange


def _create_pdf(num_pages: int) -> str:
    """Create a temporary PDF with the given number of pages and return its path."""
    path = tempfile.mktemp(suffix=".pdf")
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page()
    doc.save(path)
    doc.close()
    return path


class TestGetPageCount:
    def test_returns_correct_count(self):
        path = _create_pdf(5)
        try:
            assert get_page_count(path) == 5
        finally:
            os.unlink(path)

    def test_single_page_pdf(self):
        path = _create_pdf(1)
        try:
            assert get_page_count(path) == 1
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(Exception):
            get_page_count("/nonexistent/path.pdf")


class TestChunkManagerIterChunks:
    def setup_method(self):
        self.cm = ChunkManager()

    def test_single_chunk(self):
        path = _create_pdf(3)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=10))
            assert chunks == [PageRange(start=0, end=3)]
        finally:
            os.unlink(path)

    def test_exact_division(self):
        path = _create_pdf(10)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=5))
            assert chunks == [PageRange(start=0, end=5), PageRange(start=5, end=10)]
        finally:
            os.unlink(path)

    def test_remainder_chunk(self):
        path = _create_pdf(7)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=3))
            assert chunks == [
                PageRange(start=0, end=3),
                PageRange(start=3, end=6),
                PageRange(start=6, end=7),
            ]
        finally:
            os.unlink(path)

    def test_chunk_size_one(self):
        path = _create_pdf(3)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=1))
            assert chunks == [
                PageRange(start=0, end=1),
                PageRange(start=1, end=2),
                PageRange(start=2, end=3),
            ]
        finally:
            os.unlink(path)

    def test_single_page_pdf_single_chunk(self):
        """A 1-page PDF with large chunk_size yields exactly one chunk."""
        path = _create_pdf(1)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=50))
            assert chunks == [PageRange(start=0, end=1)]
        finally:
            os.unlink(path)

    def test_chunk_size_larger_than_pages(self):
        path = _create_pdf(3)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=100))
            assert chunks == [PageRange(start=0, end=3)]
        finally:
            os.unlink(path)

    def test_invalid_chunk_size_zero(self):
        path = _create_pdf(1)
        try:
            with pytest.raises(ValueError, match="chunk_size must be positive"):
                list(self.cm.iter_chunks(path, chunk_size=0))
        finally:
            os.unlink(path)

    def test_invalid_chunk_size_negative(self):
        path = _create_pdf(1)
        try:
            with pytest.raises(ValueError, match="chunk_size must be positive"):
                list(self.cm.iter_chunks(path, chunk_size=-1))
        finally:
            os.unlink(path)

    def test_coverage_is_complete(self):
        """All pages from 0 to N-1 are covered exactly once."""
        path = _create_pdf(13)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=4))
            all_pages = []
            for c in chunks:
                all_pages.extend(range(c.start, c.end))
            assert all_pages == list(range(13))
        finally:
            os.unlink(path)

    def test_chunks_are_disjoint(self):
        """No page appears in more than one chunk."""
        path = _create_pdf(13)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=4))
            all_pages = []
            for c in chunks:
                all_pages.extend(range(c.start, c.end))
            assert len(all_pages) == len(set(all_pages))
        finally:
            os.unlink(path)

    def test_correct_number_of_chunks(self):
        path = _create_pdf(13)
        try:
            chunks = list(self.cm.iter_chunks(path, chunk_size=4))
            assert len(chunks) == math.ceil(13 / 4)
        finally:
            os.unlink(path)

# Feature: pdf-to-llm-converter, Property 1: Chunk coverage is complete and disjoint
# Validates: Requirements 1.2
class TestChunkCoverageProperty:
    """Property 1: For any PDF with N pages and any chunk size C > 0,
    the page ranges produced by ChunkManager should be non-overlapping,
    cover every page from 0 to N-1 exactly once, and total ceil(N/C) chunks.

    **Validates: Requirements 1.2**
    """

    @given(
        num_pages=st.integers(min_value=1, max_value=500),
        chunk_size=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100)
    def test_chunk_coverage_complete_and_disjoint(self, num_pages, chunk_size):
        cm = ChunkManager()
        path = _create_pdf(num_pages)
        try:
            chunks = list(cm.iter_chunks(path, chunk_size=chunk_size))

            # 1. Correct number of chunks: ceil(N / C)
            expected_num_chunks = math.ceil(num_pages / chunk_size)
            assert len(chunks) == expected_num_chunks

            # 2. Collect all covered pages
            all_pages = []
            for c in chunks:
                assert c.start < c.end, "Each chunk must be non-empty"
                all_pages.extend(range(c.start, c.end))

            # 3. Complete coverage: every page from 0 to N-1 is present
            assert sorted(all_pages) == list(range(num_pages))

            # 4. Disjoint: no page appears more than once
            assert len(all_pages) == len(set(all_pages))

            # 5. Chunks are contiguous and ordered
            for i in range(1, len(chunks)):
                assert chunks[i].start == chunks[i - 1].end
        finally:
            os.unlink(path)

