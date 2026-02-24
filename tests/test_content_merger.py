"""Tests for ContentMerger."""

import pytest

from pdf_to_llm_converter.content_merger import (
    ContentMerger,
    _bbox_area,
    _intersection_area,
    _overlap_ratio,
)
from pdf_to_llm_converter.models import ExtractedContent, OCRResult, Table, TextBlock


# --- Helper geometry tests ---


class TestBboxArea:
    def test_normal_box(self):
        assert _bbox_area((0, 0, 10, 10)) == 100.0

    def test_zero_width(self):
        assert _bbox_area((5, 0, 5, 10)) == 0.0

    def test_zero_height(self):
        assert _bbox_area((0, 5, 10, 5)) == 0.0

    def test_inverted_coords_clamps_to_zero(self):
        assert _bbox_area((10, 10, 0, 0)) == 0.0


class TestIntersectionArea:
    def test_full_overlap(self):
        assert _intersection_area((0, 0, 10, 10), (0, 0, 10, 10)) == 100.0

    def test_partial_overlap(self):
        assert _intersection_area((0, 0, 10, 10), (5, 5, 15, 15)) == 25.0

    def test_no_overlap(self):
        assert _intersection_area((0, 0, 5, 5), (10, 10, 20, 20)) == 0.0

    def test_touching_edge(self):
        assert _intersection_area((0, 0, 5, 5), (5, 0, 10, 5)) == 0.0


class TestOverlapRatio:
    def test_identical_boxes(self):
        assert _overlap_ratio((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_no_overlap(self):
        assert _overlap_ratio((0, 0, 5, 5), (10, 10, 20, 20)) == 0.0

    def test_zero_area_box(self):
        assert _overlap_ratio((0, 0, 0, 0), (0, 0, 10, 10)) == 0.0

    def test_small_inside_large(self):
        # Small box (2x2=4) fully inside large box (10x10=100)
        # intersection=4, min(4,100)=4, ratio=1.0
        assert _overlap_ratio((0, 0, 10, 10), (3, 3, 5, 5)) == 1.0

    def test_half_overlap(self):
        # Box A: (0,0,10,10) area=100, Box B: (5,0,15,10) area=100
        # intersection: (5,0,10,10) = 50, min(100,100)=100, ratio=0.5
        assert _overlap_ratio((0, 0, 10, 10), (5, 0, 15, 10)) == 0.5


# --- ContentMerger tests ---


def _make_block(text: str, bbox: tuple[float, float, float, float], block_type: str = "paragraph") -> TextBlock:
    return TextBlock(text=text, bbox=bbox, block_type=block_type)


def _make_native(
    body: str = "",
    blocks: list[TextBlock] | None = None,
    headers: list[str] | None = None,
    footers: list[str] | None = None,
    tables: list[Table] | None = None,
) -> ExtractedContent:
    return ExtractedContent(
        body_text=body,
        headers=headers or [],
        footers=footers or [],
        tables=tables or [],
        reading_order_blocks=blocks or [],
    )


def _make_ocr(
    text: str = "",
    confidence: float = 0.9,
    blocks: list[TextBlock] | None = None,
) -> OCRResult:
    return OCRResult(text=text, confidence=confidence, blocks=blocks or [])


class TestContentMerger:
    def setup_method(self):
        self.merger = ContentMerger()

    def test_no_ocr_blocks_returns_native(self):
        native = _make_native(body="Hello world", blocks=[_make_block("Hello world", (0, 0, 100, 20))])
        ocr = _make_ocr(text="", blocks=[])
        result = self.merger.merge(native, ocr)
        assert result.body_text == "Hello world"
        assert len(result.reading_order_blocks) == 1

    def test_no_native_blocks_returns_ocr(self):
        native = _make_native(body="", blocks=[])
        ocr_block = _make_block("OCR text", (0, 0, 100, 20))
        ocr = _make_ocr(text="OCR text", blocks=[ocr_block])
        result = self.merger.merge(native, ocr)
        assert "OCR text" in result.body_text
        assert len(result.reading_order_blocks) == 1

    def test_overlapping_blocks_prefers_native(self):
        native_block = _make_block("Native text", (0, 0, 100, 50))
        ocr_block = _make_block("OCR text", (0, 0, 100, 50))  # identical bbox
        native = _make_native(body="Native text", blocks=[native_block])
        ocr = _make_ocr(text="OCR text", blocks=[ocr_block])
        result = self.merger.merge(native, ocr)
        assert result.body_text == "Native text"
        assert len(result.reading_order_blocks) == 1
        assert result.reading_order_blocks[0].text == "Native text"

    def test_non_overlapping_ocr_blocks_appended(self):
        native_block = _make_block("Native", (0, 0, 100, 50))
        ocr_block = _make_block("OCR extra", (200, 200, 300, 250))
        native = _make_native(body="Native", blocks=[native_block])
        ocr = _make_ocr(text="OCR extra", blocks=[ocr_block])
        result = self.merger.merge(native, ocr)
        assert "Native" in result.body_text
        assert "OCR extra" in result.body_text
        assert len(result.reading_order_blocks) == 2

    def test_partial_overlap_below_threshold_keeps_ocr(self):
        # Native: (0,0,10,10) area=100
        # OCR: (8,0,18,10) area=100, intersection=(8,0,10,10)=20
        # overlap_ratio = 20/min(100,100) = 0.2 < 0.5 → keep OCR
        native_block = _make_block("Native", (0, 0, 10, 10))
        ocr_block = _make_block("OCR", (8, 0, 18, 10))
        native = _make_native(body="Native", blocks=[native_block])
        ocr = _make_ocr(blocks=[ocr_block])
        result = self.merger.merge(native, ocr)
        assert len(result.reading_order_blocks) == 2

    def test_partial_overlap_above_threshold_discards_ocr(self):
        # Native: (0,0,10,10) area=100
        # OCR: (4,0,14,10) area=100, intersection=(4,0,10,10)=60
        # overlap_ratio = 60/100 = 0.6 > 0.5 → discard OCR
        native_block = _make_block("Native", (0, 0, 10, 10))
        ocr_block = _make_block("OCR", (4, 0, 14, 10))
        native = _make_native(body="Native", blocks=[native_block])
        ocr = _make_ocr(blocks=[ocr_block])
        result = self.merger.merge(native, ocr)
        assert len(result.reading_order_blocks) == 1
        assert result.reading_order_blocks[0].text == "Native"

    def test_preserves_native_headers_footers_tables(self):
        table = Table(rows=[["a", "b"], ["c", "d"]])
        native = _make_native(
            body="Body",
            blocks=[],
            headers=["Header 1"],
            footers=["Footer 1"],
            tables=[table],
        )
        ocr = _make_ocr(blocks=[])
        result = self.merger.merge(native, ocr)
        assert result.headers == ["Header 1"]
        assert result.footers == ["Footer 1"]
        assert len(result.tables) == 1
        assert result.tables[0].rows == [["a", "b"], ["c", "d"]]

    def test_empty_native_and_empty_ocr(self):
        native = _make_native()
        ocr = _make_ocr()
        result = self.merger.merge(native, ocr)
        assert result.body_text == ""
        assert result.reading_order_blocks == []

    def test_multiple_ocr_blocks_mixed_overlap(self):
        native_block = _make_block("Native", (0, 0, 100, 50))
        ocr_dup = _make_block("Dup", (0, 0, 100, 50))  # overlaps → discarded
        ocr_new = _make_block("New", (200, 200, 300, 250))  # no overlap → kept
        native = _make_native(body="Native", blocks=[native_block])
        ocr = _make_ocr(blocks=[ocr_dup, ocr_new])
        result = self.merger.merge(native, ocr)
        assert len(result.reading_order_blocks) == 2
        texts = [b.text for b in result.reading_order_blocks]
        assert "Native" in texts
        assert "New" in texts
        assert "Dup" not in texts
