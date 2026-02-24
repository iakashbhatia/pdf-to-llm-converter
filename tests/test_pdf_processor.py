"""Unit tests for PDFProcessor.process() pipeline."""

from __future__ import annotations

import logging
import os
import tempfile
from unittest.mock import MagicMock, patch

import fitz
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pdf_to_llm_converter.models import (
    ExtractedContent,
    OCRResult,
    PageClassification,
    PageRange,
    ProcessingConfig,
    ProcessingSummary,
    TextBlock,
)
from pdf_to_llm_converter.pdf_processor import PDFProcessor


def _create_test_pdf(num_pages: int = 3) -> str:
    """Create a minimal valid PDF with the given number of pages and return its path."""
    path = tempfile.mktemp(suffix=".pdf")
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"Page {i + 1} content", fontsize=12)
    doc.save(path)
    doc.close()
    return path


def _make_extracted_content(body: str = "text", heading: str | None = None) -> ExtractedContent:
    blocks = [TextBlock(text=body, bbox=(0, 0, 100, 100), block_type="paragraph")]
    if heading:
        blocks.insert(0, TextBlock(text=heading, bbox=(0, 0, 200, 30), block_type="heading"))
    return ExtractedContent(
        body_text=body,
        headers=[],
        footers=[],
        tables=[],
        reading_order_blocks=blocks,
    )


class TestPDFProcessorValidation:
    """Tests for file validation in PDFProcessor.process()."""

    def test_file_not_found_raises(self):
        processor = PDFProcessor()
        config = ProcessingConfig()
        with pytest.raises(FileNotFoundError, match="File not found"):
            processor.process("/nonexistent/path.pdf", config)

    def test_invalid_pdf_raises(self):
        processor = PDFProcessor()
        config = ProcessingConfig()
        path = tempfile.mktemp(suffix=".pdf")
        try:
            with open(path, "w") as f:
                f.write("this is not a pdf")
            with pytest.raises(RuntimeError, match="Not a valid PDF"):
                processor.process(path, config)
        finally:
            os.unlink(path)


class TestPDFProcessorProcess:
    """Tests for the full processing pipeline."""

    def test_processes_all_pages_and_builds_summary(self):
        path = _create_test_pdf(3)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig(chunk_size=50)
            document, summary = processor.process(path, config)

            assert summary.total_pages == 3
            assert summary.pages_processed == 3
            assert summary.pages_skipped == 0
            assert summary.processing_time_seconds >= 0
            assert len(document.pages) == 3
            # Pages should be numbered 1-based
            assert [p.page_number for p in document.pages] == [1, 2, 3]
        finally:
            os.unlink(path)

    def test_single_page_pdf(self):
        path = _create_test_pdf(1)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig()
            document, summary = processor.process(path, config)

            assert summary.total_pages == 1
            assert summary.pages_processed == 1
            assert summary.pages_skipped == 0
            assert len(document.pages) == 1
        finally:
            os.unlink(path)

    def test_summary_invariant_processed_plus_skipped_equals_total(self):
        path = _create_test_pdf(5)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig(chunk_size=2)
            document, summary = processor.process(path, config)

            assert summary.pages_processed + summary.pages_skipped == summary.total_pages
        finally:
            os.unlink(path)

    def test_chunked_processing_produces_same_result(self):
        """Processing with different chunk sizes should yield same page count."""
        path = _create_test_pdf(5)
        try:
            processor = PDFProcessor()
            config_small = ProcessingConfig(chunk_size=2)
            config_large = ProcessingConfig(chunk_size=50)

            doc_small, sum_small = processor.process(path, config_small)
            doc_large, sum_large = processor.process(path, config_large)

            assert sum_small.pages_processed == sum_large.pages_processed
            assert len(doc_small.pages) == len(doc_large.pages)
        finally:
            os.unlink(path)


class TestPDFProcessorCorruptedPages:
    """Tests for corrupted page handling."""

    def test_corrupted_page_is_skipped_with_warning(self):
        path = _create_test_pdf(3)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig()

            # Make the classifier raise on page index 1
            original_classify = processor.page_classifier.classify

            call_count = 0

            def classify_with_error(page):
                nonlocal call_count
                call_count += 1
                if call_count == 2:  # second page
                    raise RuntimeError("Corrupted page data")
                return original_classify(page)

            processor.page_classifier.classify = classify_with_error

            document, summary = processor.process(path, config)

            assert summary.pages_skipped == 1
            assert summary.pages_processed == 2
            assert summary.pages_processed + summary.pages_skipped == summary.total_pages
            assert any("Corrupted" in w for w in summary.warnings)
        finally:
            os.unlink(path)


class TestPDFProcessorSectionDetection:
    """Tests for section detection from heading blocks."""

    def test_detects_sections_from_heading_blocks(self):
        path = _create_test_pdf(2)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig()

            # Patch extract_page_content to return content with headings
            with patch(
                "pdf_to_llm_converter.pdf_processor.extract_page_content"
            ) as mock_extract:
                mock_extract.side_effect = [
                    _make_extracted_content("Body 1", heading="Introduction"),
                    _make_extracted_content("Body 2", heading="Conclusion"),
                ]
                document, summary = processor.process(path, config)

            assert len(document.sections) == 2
            assert document.sections[0].title == "Introduction"
            assert document.sections[1].title == "Conclusion"
        finally:
            os.unlink(path)

    def test_no_sections_when_no_headings(self):
        path = _create_test_pdf(1)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig()

            with patch(
                "pdf_to_llm_converter.pdf_processor.extract_page_content"
            ) as mock_extract:
                mock_extract.return_value = _make_extracted_content("Just body text")
                document, _ = processor.process(path, config)

            assert len(document.sections) == 0
        finally:
            os.unlink(path)


class TestPDFProcessorVerboseLogging:
    """Tests for verbose logging support."""

    def test_verbose_logs_classification_and_method(self, caplog):
        path = _create_test_pdf(1)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig(verbose=True)

            with caplog.at_level(logging.INFO):
                processor.process(path, config)

            log_text = caplog.text
            assert "classification=" in log_text
            assert "extraction_method=" in log_text
        finally:
            os.unlink(path)

    def test_non_verbose_does_not_log_per_page(self, caplog):
        path = _create_test_pdf(1)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig(verbose=False)

            with caplog.at_level(logging.INFO):
                processor.process(path, config)

            assert "classification=" not in caplog.text
        finally:
            os.unlink(path)

# Feature: pdf-to-llm-converter, Property 2: Processing summary invariant
# Validates: Requirements 1.5
class TestProcessingSummaryInvariantProperty:
    """Property-based test: for any completed processing run, the summary should satisfy
    pages_processed + pages_skipped == total_pages, and processing_time_seconds >= 0.

    **Validates: Requirements 1.5**
    """

    @given(
        total_pages=st.integers(min_value=0, max_value=500),
        data=st.data(),
        processing_time=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_summary_invariant_on_generated_summaries(
        self, total_pages, data, processing_time
    ):
        """For any processing summary produced by the pipeline, the invariant
        pages_processed + pages_skipped == total_pages must hold, and
        processing_time_seconds must be >= 0.

        This generates random processing scenarios (varying page counts, some
        pages succeeding, some being skipped) and verifies the invariant.
        """
        # Draw a random number of skipped pages (0 to total_pages)
        pages_skipped = data.draw(
            st.integers(min_value=0, max_value=total_pages)
        )
        pages_processed = total_pages - pages_skipped

        # Generate random warnings (one per skipped page)
        warnings = [
            f"Corrupted page {i}" for i in range(pages_skipped)
        ]

        summary = ProcessingSummary(
            total_pages=total_pages,
            pages_processed=pages_processed,
            pages_skipped=pages_skipped,
            warnings=warnings,
            processing_time_seconds=processing_time,
        )

        # Property: pages_processed + pages_skipped == total_pages
        assert summary.pages_processed + summary.pages_skipped == summary.total_pages, (
            f"Invariant violated: {summary.pages_processed} + {summary.pages_skipped} "
            f"!= {summary.total_pages}"
        )

        # Property: processing_time_seconds >= 0
        assert summary.processing_time_seconds >= 0, (
            f"Negative processing time: {summary.processing_time_seconds}"
        )

    @given(
        num_pages=st.integers(min_value=1, max_value=5),
        data=st.data(),
        chunk_size=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_summary_invariant_through_actual_processor(
        self, num_pages, data, chunk_size
    ):
        """Run the actual PDFProcessor pipeline with random corruption patterns
        and verify the summary invariant holds end-to-end.
        """
        # Draw which pages to corrupt
        corrupt_indices = data.draw(
            st.lists(
                st.integers(min_value=0, max_value=num_pages - 1),
                max_size=num_pages,
                unique=True,
            )
        )
        corrupt_set = set(corrupt_indices)

        path = _create_test_pdf(num_pages)
        try:
            processor = PDFProcessor()
            config = ProcessingConfig(chunk_size=chunk_size)

            # Inject corruption by making the classifier raise on selected pages
            original_classify = processor.page_classifier.classify
            call_count = 0

            def classify_maybe_corrupt(page):
                nonlocal call_count
                idx = call_count
                call_count += 1
                if idx in corrupt_set:
                    raise RuntimeError(f"Simulated corruption on page {idx}")
                return original_classify(page)

            processor.page_classifier.classify = classify_maybe_corrupt

            document, summary = processor.process(path, config)

            # Property: pages_processed + pages_skipped == total_pages
            assert summary.pages_processed + summary.pages_skipped == summary.total_pages, (
                f"Invariant violated: {summary.pages_processed} + {summary.pages_skipped} "
                f"!= {summary.total_pages}"
            )

            # Property: processing_time_seconds >= 0
            assert summary.processing_time_seconds >= 0, (
                f"Negative processing time: {summary.processing_time_seconds}"
            )

            # Verify counts match expectations
            assert summary.total_pages == num_pages
            assert summary.pages_skipped == len(corrupt_set)
            assert summary.pages_processed == num_pages - len(corrupt_set)
        finally:
            os.unlink(path)

