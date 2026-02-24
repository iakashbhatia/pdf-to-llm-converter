"""Content merger for combining native text and OCR results."""

from pdf_to_llm_converter.models import ExtractedContent, OCRResult, TextBlock


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    """Compute the area of a bounding box (x0, y0, x1, y1)."""
    width = max(0.0, bbox[2] - bbox[0])
    height = max(0.0, bbox[3] - bbox[1])
    return width * height


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    """Compute the intersection area of two bounding boxes."""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    width = max(0.0, x1 - x0)
    height = max(0.0, y1 - y0)
    return width * height


def _overlap_ratio(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    """Compute the overlap ratio as intersection / min(area_a, area_b).

    Returns a value in [0.0, 1.0]. If either box has zero area, returns 0.0.
    """
    area_a = _bbox_area(a)
    area_b = _bbox_area(b)
    if area_a == 0.0 or area_b == 0.0:
        return 0.0
    intersection = _intersection_area(a, b)
    return intersection / min(area_a, area_b)


class ContentMerger:
    """Merges native text extraction and OCR results for mixed pages."""

    def merge(self, native: ExtractedContent, ocr: OCRResult) -> ExtractedContent:
        """Merge native text and OCR results, deduplicating overlaps.

        For each OCR block, check overlap against all native text blocks.
        If any native block overlaps by more than 50%, the OCR block is
        considered a duplicate and discarded (native is preferred).
        Non-overlapping OCR blocks are appended to the result.
        """
        native_blocks = native.reading_order_blocks

        # Find OCR blocks that don't overlap significantly with native blocks
        new_ocr_blocks: list[TextBlock] = []
        for ocr_block in ocr.blocks:
            is_duplicate = False
            for native_block in native_blocks:
                if _overlap_ratio(native_block.bbox, ocr_block.bbox) > 0.5:
                    is_duplicate = True
                    break
            if not is_duplicate:
                new_ocr_blocks.append(ocr_block)

        # Combine blocks: native first, then non-overlapping OCR blocks
        merged_blocks = list(native_blocks) + new_ocr_blocks

        # Build merged body text: native body + non-overlapping OCR text
        ocr_extra_text = "\n".join(
            block.text for block in new_ocr_blocks if block.text.strip()
        )
        if native.body_text and ocr_extra_text:
            merged_body = native.body_text + "\n" + ocr_extra_text
        elif ocr_extra_text:
            merged_body = ocr_extra_text
        else:
            merged_body = native.body_text

        return ExtractedContent(
            body_text=merged_body,
            headers=list(native.headers),
            footers=list(native.footers),
            tables=list(native.tables),
            reading_order_blocks=merged_blocks,
        )
