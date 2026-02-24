"""Unit and property-based tests for extraction routing logic in pdf_processor.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import hypothesis.strategies as st
from hypothesis import given, settings
from PIL import Image

from pdf_to_llm_converter.content_merger import ContentMerger
from pdf_to_llm_converter.models import (
    ExtractedContent,
    OCRResult,
    PageClassification,
    TextBlock,
)
from pdf_to_llm_converter.ocr_engine import OCREngine
from pdf_to_llm_converter.pdf_processor import extract_page_content
from pdf_to_llm_converter.text_extractor import TextExtractor


def _make_extracted_content(body: str = "native text") -> ExtractedContent:
    return ExtractedContent(
        body_text=body,
        headers=["Header"],
        footers=["Footer"],
        tables=[],
        reading_order_blocks=[
            TextBlock(text=body, bbox=(0, 0, 100, 100), block_type="paragraph")
        ],
    )


def _make_ocr_result(text: str = "ocr text", confidence: float = 0.9) -> OCRResult:
    return OCRResult(
        text=text,
        confidence=confidence,
        blocks=[TextBlock(text=text, bbox=(200, 200, 300, 300), block_type="paragraph")],
    )


def _make_merged_content() -> ExtractedContent:
    return ExtractedContent(
        body_text="merged text",
        headers=["Header"],
        footers=["Footer"],
        tables=[],
        reading_order_blocks=[],
    )


class TestExtractPageContent:
    """Tests for the extract_page_content routing function."""

    def _setup_mocks(self):
        page = MagicMock()
        # Set up pixmap mock for page rendering
        pixmap = MagicMock()
        pixmap.width = 100
        pixmap.height = 100
        pixmap.samples = b"\x00" * (100 * 100 * 3)
        page.get_pixmap.return_value = pixmap

        text_extractor = MagicMock(spec=TextExtractor)
        ocr_engine = MagicMock(spec=OCREngine)
        content_merger = MagicMock(spec=ContentMerger)

        return page, text_extractor, ocr_engine, content_merger

    def test_native_text_uses_text_extractor_only(self):
        page, text_extractor, ocr_engine, content_merger = self._setup_mocks()
        expected = _make_extracted_content()
        text_extractor.extract.return_value = expected

        result = extract_page_content(
            page, PageClassification.NATIVE_TEXT,
            text_extractor, ocr_engine, content_merger,
        )

        assert result is expected
        text_extractor.extract.assert_called_once_with(page)
        ocr_engine.ocr_page.assert_not_called()
        content_merger.merge.assert_not_called()

    def test_scanned_uses_ocr_engine_only(self):
        page, text_extractor, ocr_engine, content_merger = self._setup_mocks()
        ocr_result = _make_ocr_result()
        ocr_engine.ocr_page.return_value = ocr_result

        result = extract_page_content(
            page, PageClassification.SCANNED,
            text_extractor, ocr_engine, content_merger,
        )

        assert result.body_text == "ocr text"
        assert result.reading_order_blocks == ocr_result.blocks
        assert result.headers == []
        assert result.footers == []
        assert result.tables == []
        text_extractor.extract.assert_not_called()
        ocr_engine.ocr_page.assert_called_once()
        content_merger.merge.assert_not_called()

    def test_mixed_uses_both_extractors_and_merger(self):
        page, text_extractor, ocr_engine, content_merger = self._setup_mocks()
        native = _make_extracted_content()
        ocr_result = _make_ocr_result()
        merged = _make_merged_content()

        text_extractor.extract.return_value = native
        ocr_engine.ocr_page.return_value = ocr_result
        content_merger.merge.return_value = merged

        result = extract_page_content(
            page, PageClassification.MIXED,
            text_extractor, ocr_engine, content_merger,
        )

        assert result is merged
        text_extractor.extract.assert_called_once_with(page)
        ocr_engine.ocr_page.assert_called_once()
        content_merger.merge.assert_called_once_with(native, ocr_result)

    def test_scanned_renders_page_to_image(self):
        page, text_extractor, ocr_engine, content_merger = self._setup_mocks()
        ocr_engine.ocr_page.return_value = _make_ocr_result()

        extract_page_content(
            page, PageClassification.SCANNED,
            text_extractor, ocr_engine, content_merger,
        )

        page.get_pixmap.assert_called_once()
        # Verify OCR received a PIL Image
        call_args = ocr_engine.ocr_page.call_args
        assert isinstance(call_args[0][0], Image.Image)

    def test_mixed_renders_page_to_image(self):
        page, text_extractor, ocr_engine, content_merger = self._setup_mocks()
        text_extractor.extract.return_value = _make_extracted_content()
        ocr_engine.ocr_page.return_value = _make_ocr_result()
        content_merger.merge.return_value = _make_merged_content()

        extract_page_content(
            page, PageClassification.MIXED,
            text_extractor, ocr_engine, content_merger,
        )

        page.get_pixmap.assert_called_once()
        call_args = ocr_engine.ocr_page.call_args
        assert isinstance(call_args[0][0], Image.Image)


# Feature: pdf-to-llm-converter, Property 4: Extraction method routing matches classification
# Validates: Requirements 2.5, 4.1


def _make_mock_page():
    """Create a mock fitz.Page with a valid pixmap for image rendering."""
    page = MagicMock()
    pixmap = MagicMock()
    pixmap.width = 100
    pixmap.height = 100
    pixmap.samples = b"\x00" * (100 * 100 * 3)
    page.get_pixmap.return_value = pixmap
    return page


# Strategy: sample uniformly from all PageClassification values
page_classifications = st.sampled_from(list(PageClassification))


class TestExtractionRoutingProperty:
    """Property 4: Extraction method routing matches classification.

    For any page classification, extract_page_content should invoke:
    - Text_Extractor for NATIVE_TEXT and MIXED pages
    - OCR_Engine for SCANNED and MIXED pages
    - Both extractors (and Content_Merger) for MIXED pages
    """

    # **Validates: Requirements 2.5, 4.1**

    @given(classification=page_classifications)
    @settings(max_examples=100)
    def test_routing_matches_classification(self, classification: PageClassification):
        """For any PageClassification, the correct extractors are invoked."""
        page = _make_mock_page()
        text_extractor = MagicMock(spec=TextExtractor)
        ocr_engine = MagicMock(spec=OCREngine)
        content_merger = MagicMock(spec=ContentMerger)

        # Set up return values so the function can complete
        native_content = _make_extracted_content("native")
        ocr_result = _make_ocr_result("ocr", 0.95)
        merged_content = _make_merged_content()

        text_extractor.extract.return_value = native_content
        ocr_engine.ocr_page.return_value = ocr_result
        content_merger.merge.return_value = merged_content

        extract_page_content(
            page, classification, text_extractor, ocr_engine, content_merger
        )

        if classification == PageClassification.NATIVE_TEXT:
            # Only Text_Extractor should be called
            text_extractor.extract.assert_called_once_with(page)
            ocr_engine.ocr_page.assert_not_called()
            content_merger.merge.assert_not_called()

        elif classification == PageClassification.SCANNED:
            # Only OCR_Engine should be called
            text_extractor.extract.assert_not_called()
            ocr_engine.ocr_page.assert_called_once()
            content_merger.merge.assert_not_called()

        elif classification == PageClassification.MIXED:
            # Both extractors and the merger should be called
            text_extractor.extract.assert_called_once_with(page)
            ocr_engine.ocr_page.assert_called_once()
            content_merger.merge.assert_called_once_with(native_content, ocr_result)
