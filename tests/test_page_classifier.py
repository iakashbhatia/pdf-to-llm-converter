"""Tests for the PageClassifier component."""

from __future__ import annotations

import pytest

from pdf_to_llm_converter.models import PageClassification
from pdf_to_llm_converter.page_classifier import PageClassifier, classify_by_ratio


class TestClassifyByRatio:
    """Unit tests for the classify_by_ratio helper function."""

    def test_high_coverage_returns_native_text(self):
        assert classify_by_ratio(0.95) == PageClassification.NATIVE_TEXT

    def test_low_coverage_returns_scanned(self):
        assert classify_by_ratio(0.05) == PageClassification.SCANNED

    def test_mid_coverage_returns_mixed(self):
        assert classify_by_ratio(0.5) == PageClassification.MIXED

    def test_zero_coverage_returns_scanned(self):
        assert classify_by_ratio(0.0) == PageClassification.SCANNED

    def test_full_coverage_returns_native_text(self):
        assert classify_by_ratio(1.0) == PageClassification.NATIVE_TEXT

    def test_boundary_at_0_8_returns_mixed(self):
        """Exactly 0.8 is not > 0.8, so it should be MIXED."""
        assert classify_by_ratio(0.8) == PageClassification.MIXED

    def test_boundary_at_0_2_returns_mixed(self):
        """Exactly 0.2 is not < 0.2, so it should be MIXED."""
        assert classify_by_ratio(0.2) == PageClassification.MIXED

    def test_just_above_0_8_returns_native_text(self):
        assert classify_by_ratio(0.81) == PageClassification.NATIVE_TEXT

    def test_just_below_0_2_returns_scanned(self):
        assert classify_by_ratio(0.19) == PageClassification.SCANNED


class TestPageClassifierWithMock:
    """Tests for PageClassifier.classify() using a mock fitz.Page."""

    def _make_mock_page(self, mocker, page_width, page_height, text_blocks):
        """Create a mock fitz.Page with given dimensions and text blocks."""
        mock_page = mocker.MagicMock()
        mock_rect = mocker.MagicMock()
        mock_rect.width = page_width
        mock_rect.height = page_height
        mock_page.rect = mock_rect
        mock_page.get_text.return_value = text_blocks
        return mock_page

    def test_classify_page_with_full_text_coverage(self, mocker):
        """A page where text covers >80% should be NATIVE_TEXT."""
        # Page is 100x100 = 10000 area
        # Text block covers 95x95 = 9025 area → ratio ~0.9
        blocks = [(2, 2, 97, 97, "Some text", 0, 0)]
        page = self._make_mock_page(mocker, 100, 100, blocks)
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.NATIVE_TEXT

    def test_classify_page_with_no_text(self, mocker):
        """A page with no text blocks should be SCANNED."""
        page = self._make_mock_page(mocker, 100, 100, [])
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.SCANNED

    def test_classify_page_with_small_text(self, mocker):
        """A page with text covering <20% should be SCANNED."""
        # Page is 100x100 = 10000 area
        # Text block covers 10x10 = 100 area → ratio 0.01
        blocks = [(0, 0, 10, 10, "Small text", 0, 0)]
        page = self._make_mock_page(mocker, 100, 100, blocks)
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.SCANNED

    def test_classify_page_with_mixed_content(self, mocker):
        """A page with text covering 20-80% should be MIXED."""
        # Page is 100x100 = 10000 area
        # Text block covers 50x100 = 5000 area → ratio 0.5
        blocks = [(0, 0, 50, 100, "Half page text", 0, 0)]
        page = self._make_mock_page(mocker, 100, 100, blocks)
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.MIXED

    def test_classify_ignores_image_blocks(self, mocker):
        """Image blocks (type 1) should not count toward text area."""
        # Page is 100x100 = 10000 area
        # Image block covers 90x90 = 8100 but type=1, so ignored
        # Text block covers 10x10 = 100 → ratio 0.01
        blocks = [
            (5, 5, 95, 95, "", 0, 1),  # image block
            (0, 0, 10, 10, "Small text", 1, 0),  # text block
        ]
        page = self._make_mock_page(mocker, 100, 100, blocks)
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.SCANNED

    def test_classify_zero_area_page(self, mocker):
        """A page with zero area should return SCANNED."""
        page = self._make_mock_page(mocker, 0, 0, [])
        classifier = PageClassifier()
        assert classifier.classify(page) == PageClassification.SCANNED

# Feature: pdf-to-llm-converter, Property 3: Page classification correctness by coverage ratio
# Validates: Requirements 2.1, 2.2, 2.3, 2.4

from hypothesis import given, settings
from hypothesis import strategies as st


class TestClassificationCorrectnessProperty:
    """Property-based tests for page classification correctness by coverage ratio."""

    @settings(max_examples=100)
    @given(ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    def test_classification_is_always_valid(self, ratio: float):
        """**Validates: Requirements 2.1**

        For any coverage ratio in [0.0, 1.0], the result must be one of exactly
        three valid PageClassification values.
        """
        result = classify_by_ratio(ratio)
        assert result in {
            PageClassification.NATIVE_TEXT,
            PageClassification.SCANNED,
            PageClassification.MIXED,
        }

    @settings(max_examples=100)
    @given(ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False).filter(lambda r: r > 0.8))
    def test_high_coverage_classified_as_native_text(self, ratio: float):
        """**Validates: Requirements 2.2**

        For any coverage ratio > 0.8, the classifier must return NATIVE_TEXT.
        """
        assert classify_by_ratio(ratio) == PageClassification.NATIVE_TEXT

    @settings(max_examples=100)
    @given(ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False).filter(lambda r: r < 0.2))
    def test_low_coverage_classified_as_scanned(self, ratio: float):
        """**Validates: Requirements 2.3**

        For any coverage ratio < 0.2, the classifier must return SCANNED.
        """
        assert classify_by_ratio(ratio) == PageClassification.SCANNED

    @settings(max_examples=100)
    @given(ratio=st.floats(min_value=0.2, max_value=0.8, allow_nan=False, allow_infinity=False))
    def test_mid_coverage_classified_as_mixed(self, ratio: float):
        """**Validates: Requirements 2.4**

        For any coverage ratio in [0.2, 0.8], the classifier must return MIXED.
        """
        assert classify_by_ratio(ratio) == PageClassification.MIXED

