"""Page classifier for determining content type of PDF pages."""

from __future__ import annotations

import fitz

from pdf_to_llm_converter.models import PageClassification

# Threshold boundaries for classification
_NATIVE_TEXT_THRESHOLD = 0.8
_SCANNED_THRESHOLD = 0.2


def classify_by_ratio(ratio: float) -> PageClassification:
    """Classify a page based on a pre-computed text coverage ratio.

    Args:
        ratio: Text coverage ratio in [0.0, 1.0].

    Returns:
        PageClassification based on threshold boundaries.
    """
    if ratio > _NATIVE_TEXT_THRESHOLD:
        return PageClassification.NATIVE_TEXT
    if ratio < _SCANNED_THRESHOLD:
        return PageClassification.SCANNED
    return PageClassification.MIXED


class PageClassifier:
    """Classifies PDF pages based on text coverage ratio."""

    def classify(self, page: fitz.Page) -> PageClassification:
        """Classify a page based on text coverage ratio.

        Computes text_coverage = extractable_text_area / total_content_area
        and returns the classification using threshold boundaries.

        Args:
            page: A PyMuPDF page object.

        Returns:
            PageClassification indicating the page content type.
        """
        text_coverage = self._compute_text_coverage(page)
        return classify_by_ratio(text_coverage)

    def _compute_text_coverage(self, page: fitz.Page) -> float:
        """Compute the text coverage ratio for a page.

        Uses the union of text block bounding boxes as the extractable text
        area and the page's media box as the total content area.

        Args:
            page: A PyMuPDF page object.

        Returns:
            A float in [0.0, 1.0] representing text coverage.
        """
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        if page_area <= 0:
            return 0.0

        text_blocks = page.get_text("blocks")
        if not text_blocks:
            return 0.0

        text_area = 0.0
        for block in text_blocks:
            # blocks are tuples: (x0, y0, x1, y1, text, block_no, block_type)
            # block_type 0 = text, 1 = image
            if block[6] == 0:  # text block
                x0, y0, x1, y1 = block[:4]
                block_width = max(0.0, x1 - x0)
                block_height = max(0.0, y1 - y0)
                text_area += block_width * block_height

        ratio = text_area / page_area
        return min(ratio, 1.0)
