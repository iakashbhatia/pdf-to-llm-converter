"""Text extractor for native PDF text content.

Uses PyMuPDF for block-level text extraction with bounding boxes
and table detection. Detects headers/footers by vertical position.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from pdf_to_llm_converter.models import ExtractedContent, Table, TextBlock


# Fraction of page height used to detect headers and footers.
_HEADER_ZONE = 0.10  # top 10%
_FOOTER_ZONE = 0.90  # bottom 10%

# Font-size ratio relative to the median that triggers heading detection.
_HEADING_SIZE_RATIO = 1.25


class TextExtractor:
    """Extract native text from a PDF page preserving structure."""

    def extract(self, page: fitz.Page) -> ExtractedContent:
        """Extract native text preserving structure.

        1. Uses ``page.get_text("dict")`` for block-level extraction.
        2. Uses ``page.find_tables()`` for table detection.
        3. Classifies blocks as header/footer/body by vertical position.
        4. Classifies body blocks as heading, list_item, or paragraph.
        5. Preserves reading order (top-to-bottom, left-to-right).
        """
        page_height = page.rect.height
        header_limit = page_height * _HEADER_ZONE
        footer_limit = page_height * _FOOTER_ZONE

        # --- table regions ------------------------------------------------
        tables, table_rects = self._extract_tables(page)

        # --- block-level text ---------------------------------------------
        text_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
        median_size = self._median_font_size(text_dict)

        headers: list[str] = []
        footers: list[str] = []
        body_lines: list[str] = []
        reading_order_blocks: list[TextBlock] = []

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # only text blocks
                continue

            bbox = (block["bbox"][0], block["bbox"][1],
                    block["bbox"][2], block["bbox"][3])

            # Skip blocks that fall inside a detected table region.
            if self._overlaps_any(bbox, table_rects):
                continue

            block_text = self._block_text(block)
            if not block_text.strip():
                continue

            block_type = self._classify_block(block, median_size)

            # Header / footer detection by vertical position.
            mid_y = (bbox[1] + bbox[3]) / 2.0
            if mid_y < header_limit:
                headers.append(block_text.strip())
            elif mid_y > footer_limit:
                footers.append(block_text.strip())
            else:
                body_lines.append(block_text)

            reading_order_blocks.append(
                TextBlock(text=block_text.strip(), bbox=bbox, block_type=block_type)
            )

        return ExtractedContent(
            body_text="\n".join(body_lines).strip(),
            headers=headers,
            footers=footers,
            tables=tables,
            reading_order_blocks=reading_order_blocks,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_tables(
        self, page: fitz.Page
    ) -> tuple[list[Table], list[tuple[float, float, float, float]]]:
        """Detect tables on the page and return Table objects + bounding rects."""
        tables: list[Table] = []
        table_rects: list[tuple[float, float, float, float]] = []

        try:
            found = page.find_tables()
        except Exception:
            return tables, table_rects

        for tbl in found.tables:
            rows: list[list[str]] = []
            for row in tbl.extract():
                rows.append([cell if cell is not None else "" for cell in row])
            tables.append(Table(rows=rows))
            r = tbl.bbox
            table_rects.append((r[0], r[1], r[2], r[3]))

        return tables, table_rects

    @staticmethod
    def _block_text(block: dict) -> str:
        """Concatenate all span texts in a block preserving line breaks."""
        lines: list[str] = []
        for line in block.get("lines", []):
            spans_text = "".join(span.get("text", "") for span in line.get("spans", []))
            lines.append(spans_text)
        return "\n".join(lines)

    @staticmethod
    def _median_font_size(text_dict: dict) -> float:
        """Compute the median font size across all spans on the page."""
        sizes: list[float] = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span.get("size", 0.0))
        if not sizes:
            return 12.0  # sensible default
        sizes.sort()
        mid = len(sizes) // 2
        return sizes[mid]

    @staticmethod
    def _classify_block(block: dict, median_size: float) -> str:
        """Classify a text block as 'heading', 'list_item', or 'paragraph'."""
        # Gather font info from the first line's first span.
        first_span = None
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                first_span = span
                break
            if first_span:
                break

        if first_span is None:
            return "paragraph"

        size = first_span.get("size", 0.0)
        flags = first_span.get("flags", 0)
        text = first_span.get("text", "").lstrip()

        # Bold flag is bit 4 (16) in PyMuPDF span flags.
        is_bold = bool(flags & (1 << 4))

        # Heading: significantly larger font or bold + larger.
        if size > median_size * _HEADING_SIZE_RATIO:
            return "heading"
        if is_bold and size >= median_size:
            return "heading"

        # List item: starts with bullet or numbered pattern.
        if text and (text[0] in "•◦▪▸–-" or _starts_with_number(text)):
            return "list_item"

        return "paragraph"

    @staticmethod
    def _overlaps_any(
        bbox: tuple[float, float, float, float],
        rects: list[tuple[float, float, float, float]],
    ) -> bool:
        """Return True if *bbox* overlaps with any rect by > 50% of its area."""
        bx0, by0, bx1, by1 = bbox
        b_area = max((bx1 - bx0) * (by1 - by0), 1e-6)
        for rx0, ry0, rx1, ry1 in rects:
            ix0 = max(bx0, rx0)
            iy0 = max(by0, ry0)
            ix1 = min(bx1, rx1)
            iy1 = min(by1, ry1)
            if ix0 < ix1 and iy0 < iy1:
                overlap = (ix1 - ix0) * (iy1 - iy0)
                if overlap / b_area > 0.5:
                    return True
        return False


def _starts_with_number(text: str) -> bool:
    """Check if text starts with a numbered-list pattern like '1.' or '1)'."""
    stripped = text.lstrip()
    if not stripped:
        return False
    i = 0
    while i < len(stripped) and stripped[i].isdigit():
        i += 1
    if i == 0:
        return False
    return i < len(stripped) and stripped[i] in ".)"
