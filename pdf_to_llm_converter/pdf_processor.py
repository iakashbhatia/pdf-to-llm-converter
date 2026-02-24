"""PDF processor orchestrating the full extraction pipeline."""

from __future__ import annotations

import logging
import os
import time

import fitz  # PyMuPDF
from PIL import Image

from pdf_to_llm_converter.chunk_manager import ChunkManager
from pdf_to_llm_converter.content_merger import ContentMerger
from pdf_to_llm_converter.models import (
    Document,
    DocumentSection,
    ExtractedContent,
    OCRResult,
    PageClassification,
    PageContent,
    ProcessingConfig,
    ProcessingSummary,
    TextBlock,
)
from pdf_to_llm_converter.ocr_engine import OCREngine
from pdf_to_llm_converter.page_classifier import PageClassifier
from pdf_to_llm_converter.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


def _render_page_to_image(page: fitz.Page) -> Image.Image:
    """Render a PDF page to a PIL Image via PyMuPDF pixmap."""
    pixmap = page.get_pixmap()
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def extract_page_content(
    page: fitz.Page,
    classification: PageClassification,
    text_extractor: TextExtractor,
    ocr_engine: OCREngine,
    content_merger: ContentMerger,
) -> ExtractedContent:
    """Route a page to the appropriate extractor(s) based on its classification.

    - NATIVE_TEXT → Text_Extractor only
    - SCANNED    → OCR_Engine only (page rendered to image first)
    - MIXED      → both extractors, then Content_Merger to combine results
    """
    if classification == PageClassification.NATIVE_TEXT:
        return text_extractor.extract(page)

    if classification == PageClassification.SCANNED:
        image = _render_page_to_image(page)
        ocr_result = ocr_engine.ocr_page(image)
        return ExtractedContent(
            body_text=ocr_result.text,
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=ocr_result.blocks,
        )

    # MIXED: run both extractors, then merge
    native_content = text_extractor.extract(page)
    image = _render_page_to_image(page)
    ocr_result = ocr_engine.ocr_page(image)
    return content_merger.merge(native_content, ocr_result)


class PDFProcessor:
    """Orchestrates the full PDF processing pipeline.

    Wires together ChunkManager, PageClassifier, TextExtractor, OCREngine,
    ContentMerger to process a PDF file into a Document model with a
    ProcessingSummary.
    """

    def __init__(self) -> None:
        self.chunk_manager = ChunkManager()
        self.page_classifier = PageClassifier()
        self.text_extractor = TextExtractor()
        self.ocr_engine = OCREngine()
        self.content_merger = ContentMerger()

    def process(
        self, pdf_path: str, config: ProcessingConfig
    ) -> tuple[Document, ProcessingSummary]:
        """Process a PDF file and return a Document model and summary.

        Args:
            pdf_path: Path to the PDF file.
            config: Processing configuration.

        Returns:
            A tuple of (Document, ProcessingSummary).

        Raises:
            FileNotFoundError: If the file does not exist.
            RuntimeError: If the file is not a valid PDF.
        """
        start_time = time.monotonic()

        # Validate file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File not found: {pdf_path}")

        # Validate it's a PDF by attempting to open it
        try:
            test_doc = fitz.open(pdf_path)
            total_pages = len(test_doc)
            test_doc.close()
        except Exception as exc:
            raise RuntimeError(f"Not a valid PDF: {pdf_path}") from exc

        warnings: list[str] = []
        pages: list[PageContent] = []
        pages_skipped = 0

        for page_range in self.chunk_manager.iter_chunks(pdf_path, config.chunk_size):
            doc = fitz.open(pdf_path)
            try:
                for page_num in range(page_range.start, page_range.end):
                    try:
                        page = doc[page_num]

                        # Classify
                        classification = self.page_classifier.classify(page)
                        if config.verbose:
                            logger.info(
                                "Page %d: classification=%s",
                                page_num + 1,
                                classification.value,
                            )

                        # Extract content
                        content = extract_page_content(
                            page,
                            classification,
                            self.text_extractor,
                            self.ocr_engine,
                            self.content_merger,
                        )

                        # Determine OCR confidence
                        ocr_confidence: float | None = None
                        if classification in (
                            PageClassification.SCANNED,
                            PageClassification.MIXED,
                        ):
                            image = _render_page_to_image(page)
                            ocr_result = self.ocr_engine.ocr_page(image)
                            ocr_confidence = ocr_result.confidence
                            if ocr_confidence < config.ocr_threshold:
                                warn_msg = (
                                    f"Low OCR confidence on page {page_num + 1}: "
                                    f"{ocr_confidence:.2f}"
                                )
                                warnings.append(warn_msg)
                                logger.warning(warn_msg)

                        if config.verbose:
                            method = (
                                "text_extractor"
                                if classification == PageClassification.NATIVE_TEXT
                                else "ocr_engine"
                                if classification == PageClassification.SCANNED
                                else "text_extractor+ocr_engine"
                            )
                            logger.info(
                                "Page %d: extraction_method=%s",
                                page_num + 1,
                                method,
                            )

                        pages.append(
                            PageContent(
                                page_number=page_num + 1,
                                classification=classification,
                                content=content,
                                ocr_confidence=ocr_confidence,
                            )
                        )

                    except Exception as exc:
                        warn_msg = (
                            f"Corrupted/unreadable page {page_num + 1}: {exc}"
                        )
                        warnings.append(warn_msg)
                        logger.warning(warn_msg)
                        pages_skipped += 1
            finally:
                doc.close()

        # Build sections from heading blocks across all pages
        sections = self._detect_sections(pages)

        document = Document(sections=sections, pages=pages)

        elapsed = time.monotonic() - start_time
        summary = ProcessingSummary(
            total_pages=total_pages,
            pages_processed=len(pages),
            pages_skipped=pages_skipped,
            warnings=warnings,
            processing_time_seconds=elapsed,
        )

        # Log warning summary
        if warnings:
            logger.warning(
                "Processing completed with %d warning(s):", len(warnings)
            )
            for w in warnings:
                logger.warning("  %s", w)

        return document, summary

    def _detect_sections(
        self, pages: list[PageContent]
    ) -> list[DocumentSection]:
        """Detect sections from heading blocks across all pages.

        Scans reading_order_blocks for blocks with block_type="heading"
        and builds a hierarchical section tree.
        """
        flat_sections: list[DocumentSection] = []

        for page in pages:
            for block in page.content.reading_order_blocks:
                if block.block_type != "heading":
                    continue

                title = block.text.strip()
                if not title:
                    continue

                level = self._estimate_heading_level(block)

                flat_sections.append(
                    DocumentSection(
                        title=title,
                        level=level,
                        content="",
                        page_start=page.page_number,
                        page_end=page.page_number,
                        subsections=[],
                    )
                )

        return self._build_section_hierarchy(flat_sections)

    @staticmethod
    def _estimate_heading_level(block: TextBlock) -> int:
        """Estimate heading level from a TextBlock.

        If the text already starts with markdown heading markers (e.g. "## Title"),
        use that level. Otherwise default to level 1.
        """
        text = block.text.strip()
        # Check for markdown-style heading prefix
        if text.startswith("#"):
            hashes = 0
            for ch in text:
                if ch == "#":
                    hashes += 1
                else:
                    break
            if 1 <= hashes <= 6:
                return hashes
        return 1

    @staticmethod
    def _build_section_hierarchy(
        flat_sections: list[DocumentSection],
    ) -> list[DocumentSection]:
        """Build a hierarchical section tree from a flat list based on levels."""
        if not flat_sections:
            return []

        root: list[DocumentSection] = []
        stack: list[DocumentSection] = []

        for section in flat_sections:
            while stack and stack[-1].level >= section.level:
                stack.pop()

            if stack:
                parent = stack[-1]
                parent.subsections.append(section)
                if section.page_end > parent.page_end:
                    parent.page_end = section.page_end
            else:
                root.append(section)

            stack.append(section)

        return root
