"""Unit tests for TextExtractor.

Validates:
- Requirement 3.3: Table extraction preserves row/column structure
- Requirement 3.4: Header/footer detection and tagging
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

from pdf_to_llm_converter.models import ExtractedContent, Table
from pdf_to_llm_converter.text_extractor import TextExtractor


# ---------------------------------------------------------------------------
# Helpers to build mock fitz.Page objects
# ---------------------------------------------------------------------------

def _make_span(text: str, size: float = 12.0, flags: int = 0) -> dict:
    """Create a PyMuPDF span dict."""
    return {"text": text, "size": size, "flags": flags}


def _make_block(
    text_lines: list[list[dict]],
    bbox: tuple[float, float, float, float],
    block_type: int = 0,
) -> dict:
    """Create a PyMuPDF text block dict.

    *text_lines* is a list of lines, each line being a list of span dicts.
    """
    lines = [{"spans": spans} for spans in text_lines]
    return {"type": block_type, "bbox": list(bbox), "lines": lines}


def _make_mock_table(rows: list[list[str | None]], bbox: tuple[float, float, float, float]):
    """Create a mock table object matching PyMuPDF's find_tables() result."""
    tbl = MagicMock()
    tbl.extract.return_value = rows
    tbl.bbox = bbox
    return tbl


def _make_page(
    blocks: list[dict],
    tables: list | None = None,
    page_height: float = 1000.0,
    page_width: float = 600.0,
) -> MagicMock:
    """Build a mock fitz.Page with the given text blocks and tables."""
    page = MagicMock()

    # page.rect
    rect = MagicMock()
    type(rect).height = PropertyMock(return_value=page_height)
    type(rect).width = PropertyMock(return_value=page_width)
    type(page).rect = PropertyMock(return_value=rect)

    # page.get_text("dict", ...)
    page.get_text.return_value = {"blocks": blocks}

    # page.find_tables()
    if tables is not None:
        found = MagicMock()
        found.tables = tables
        page.find_tables.return_value = found
    else:
        found = MagicMock()
        found.tables = []
        page.find_tables.return_value = found

    return page


# ---------------------------------------------------------------------------
# Table extraction tests (Requirement 3.3)
# ---------------------------------------------------------------------------

class TestTableExtraction:
    """Table extraction preserves row and column relationships."""

    def test_single_table_preserves_rows_and_columns(self) -> None:
        """A simple 2x3 table should come back with the exact grid."""
        raw_rows = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
        ]
        mock_table = _make_mock_table(raw_rows, bbox=(50, 200, 550, 400))

        page = _make_page(blocks=[], tables=[mock_table])
        result = TextExtractor().extract(page)

        assert len(result.tables) == 1
        table = result.tables[0]
        assert len(table.rows) == 2
        assert len(table.rows[0]) == 3
        assert table.rows[0] == ["Name", "Age", "City"]
        assert table.rows[1] == ["Alice", "30", "NYC"]

    def test_table_with_none_cells_replaced_by_empty_string(self) -> None:
        """None cells (merged/empty) should become empty strings."""
        raw_rows = [
            ["A", None, "C"],
            [None, "B", None],
        ]
        mock_table = _make_mock_table(raw_rows, bbox=(50, 200, 550, 400))

        page = _make_page(blocks=[], tables=[mock_table])
        result = TextExtractor().extract(page)

        assert result.tables[0].rows[0] == ["A", "", "C"]
        assert result.tables[0].rows[1] == ["", "B", ""]

    def test_multiple_tables_extracted_independently(self) -> None:
        """Two tables on the same page should both be extracted."""
        t1 = _make_mock_table([["X", "Y"]], bbox=(50, 100, 300, 200))
        t2 = _make_mock_table([["1", "2"], ["3", "4"]], bbox=(50, 500, 300, 700))

        page = _make_page(blocks=[], tables=[t1, t2])
        result = TextExtractor().extract(page)

        assert len(result.tables) == 2
        assert result.tables[0].rows == [["X", "Y"]]
        assert result.tables[1].rows == [["1", "2"], ["3", "4"]]

    def test_text_blocks_inside_table_region_are_excluded_from_body(self) -> None:
        """Text blocks overlapping a table bbox should not appear in body_text."""
        # Table occupies (50, 200, 550, 400)
        mock_table = _make_mock_table([["cell"]], bbox=(50, 200, 550, 400))

        # A text block sitting entirely inside the table region
        overlapping_block = _make_block(
            [[_make_span("table text")]],
            bbox=(60, 210, 540, 390),
        )
        # A body block outside the table
        body_block = _make_block(
            [[_make_span("body paragraph")]],
            bbox=(50, 450, 550, 500),
        )

        page = _make_page(blocks=[overlapping_block, body_block], tables=[mock_table])
        result = TextExtractor().extract(page)

        assert "table text" not in result.body_text
        assert "body paragraph" in result.body_text

    def test_find_tables_exception_returns_empty_tables(self) -> None:
        """If find_tables() raises, extraction should still succeed with no tables."""
        body_block = _make_block(
            [[_make_span("some text")]],
            bbox=(50, 450, 550, 500),
        )
        page = _make_page(blocks=[body_block])
        page.find_tables.side_effect = RuntimeError("table detection failed")

        result = TextExtractor().extract(page)

        assert result.tables == []
        assert "some text" in result.body_text


# ---------------------------------------------------------------------------
# Header / footer detection tests (Requirement 3.4)
# ---------------------------------------------------------------------------

class TestHeaderFooterDetection:
    """Headers and footers are detected by vertical position and tagged separately."""

    def test_block_in_top_zone_classified_as_header(self) -> None:
        """A block whose vertical midpoint is in the top 10% is a header."""
        # Page height = 1000, header zone < 100
        header_block = _make_block(
            [[_make_span("Page Header")]],
            bbox=(50, 10, 550, 60),  # mid_y = 35 → header
        )
        body_block = _make_block(
            [[_make_span("Body text")]],
            bbox=(50, 400, 550, 450),  # mid_y = 425 → body
        )

        page = _make_page(blocks=[header_block, body_block])
        result = TextExtractor().extract(page)

        assert "Page Header" in result.headers
        assert "Page Header" not in result.body_text
        assert "Body text" in result.body_text

    def test_block_in_bottom_zone_classified_as_footer(self) -> None:
        """A block whose vertical midpoint is in the bottom 10% is a footer."""
        # Page height = 1000, footer zone > 900
        footer_block = _make_block(
            [[_make_span("Page 1 of 10")]],
            bbox=(50, 940, 550, 990),  # mid_y = 965 → footer
        )
        body_block = _make_block(
            [[_make_span("Body text")]],
            bbox=(50, 400, 550, 450),
        )

        page = _make_page(blocks=[footer_block, body_block])
        result = TextExtractor().extract(page)

        assert "Page 1 of 10" in result.footers
        assert "Page 1 of 10" not in result.body_text

    def test_multiple_headers_and_footers(self) -> None:
        """Multiple blocks in header/footer zones are all captured."""
        h1 = _make_block([[_make_span("Header Line 1")]], bbox=(50, 5, 550, 30))
        h2 = _make_block([[_make_span("Header Line 2")]], bbox=(50, 35, 550, 60))
        f1 = _make_block([[_make_span("Footer A")]], bbox=(50, 950, 300, 980))
        f2 = _make_block([[_make_span("Footer B")]], bbox=(300, 950, 550, 980))
        body = _make_block([[_make_span("Content")]], bbox=(50, 400, 550, 450))

        page = _make_page(blocks=[h1, h2, body, f1, f2])
        result = TextExtractor().extract(page)

        assert len(result.headers) == 2
        assert len(result.footers) == 2
        assert "Header Line 1" in result.headers
        assert "Header Line 2" in result.headers
        assert "Footer A" in result.footers
        assert "Footer B" in result.footers

    def test_body_block_not_in_headers_or_footers(self) -> None:
        """A block in the middle of the page should only be in body_text."""
        body_block = _make_block(
            [[_make_span("Middle content")]],
            bbox=(50, 450, 550, 500),  # mid_y = 475
        )

        page = _make_page(blocks=[body_block])
        result = TextExtractor().extract(page)

        assert result.headers == []
        assert result.footers == []
        assert "Middle content" in result.body_text

    def test_header_footer_stripped_from_body_text(self) -> None:
        """Header/footer text must not leak into body_text."""
        header = _make_block([[_make_span("CONFIDENTIAL")]], bbox=(50, 10, 550, 50))
        footer = _make_block([[_make_span("Page 5")]], bbox=(50, 960, 550, 990))
        body = _make_block([[_make_span("Legal clause here")]], bbox=(50, 300, 550, 350))

        page = _make_page(blocks=[header, body, footer])
        result = TextExtractor().extract(page)

        assert "CONFIDENTIAL" not in result.body_text
        assert "Page 5" not in result.body_text
        assert "Legal clause here" in result.body_text


# ---------------------------------------------------------------------------
# Edge cases and reading order
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases for the extraction pipeline."""

    def test_empty_page_returns_empty_content(self) -> None:
        """A page with no text blocks should return empty ExtractedContent."""
        page = _make_page(blocks=[])
        result = TextExtractor().extract(page)

        assert result.body_text == ""
        assert result.headers == []
        assert result.footers == []
        assert result.tables == []
        assert result.reading_order_blocks == []

    def test_whitespace_only_blocks_are_skipped(self) -> None:
        """Blocks containing only whitespace should not appear in output."""
        ws_block = _make_block([[_make_span("   \n  ")]], bbox=(50, 400, 550, 450))

        page = _make_page(blocks=[ws_block])
        result = TextExtractor().extract(page)

        assert result.body_text == ""
        assert result.reading_order_blocks == []

    def test_reading_order_blocks_include_all_zones(self) -> None:
        """reading_order_blocks should contain header, body, and footer blocks."""
        header = _make_block([[_make_span("H")]], bbox=(50, 10, 550, 50))
        body = _make_block([[_make_span("B")]], bbox=(50, 400, 550, 450))
        footer = _make_block([[_make_span("F")]], bbox=(50, 960, 550, 990))

        page = _make_page(blocks=[header, body, footer])
        result = TextExtractor().extract(page)

        block_texts = [b.text for b in result.reading_order_blocks]
        assert "H" in block_texts
        assert "B" in block_texts
        assert "F" in block_texts

    def test_non_text_blocks_are_ignored(self) -> None:
        """Image blocks (type != 0) should be skipped entirely."""
        image_block = _make_block([], bbox=(50, 400, 550, 600), block_type=1)
        text_block = _make_block(
            [[_make_span("real text")]],
            bbox=(50, 650, 550, 700),
        )

        page = _make_page(blocks=[image_block, text_block])
        result = TextExtractor().extract(page)

        assert "real text" in result.body_text
        assert len(result.reading_order_blocks) == 1
