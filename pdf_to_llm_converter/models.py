"""Core data models for the PDF-to-LLM converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageClassification(Enum):
    """Classification of a PDF page based on text coverage ratio."""

    NATIVE_TEXT = "native_text"
    SCANNED = "scanned"
    MIXED = "mixed"


@dataclass
class TextBlock:
    """A block of text with position and type information."""

    text: str
    bbox: tuple[float, float, float, float]
    block_type: str  # "paragraph", "heading", "list_item", "table_cell"


@dataclass
class Table:
    """A table extracted from a PDF page."""

    rows: list[list[str]]


@dataclass
class ExtractedContent:
    """Content extracted from a single PDF page."""

    body_text: str
    headers: list[str]
    footers: list[str]
    tables: list[Table]
    reading_order_blocks: list[TextBlock]


@dataclass
class PageContent:
    """Content and metadata for a single processed page."""

    page_number: int
    classification: PageClassification
    content: ExtractedContent
    ocr_confidence: float | None


@dataclass
class DocumentSection:
    """A section of the document with hierarchical structure."""

    title: str
    level: int  # 1-6
    content: str
    page_start: int
    page_end: int
    subsections: list[DocumentSection] = field(default_factory=list)


@dataclass
class Document:
    """The complete internal representation of a processed PDF."""

    sections: list[DocumentSection]
    pages: list[PageContent]


@dataclass
class ProcessingConfig:
    """Configuration for PDF processing."""

    chunk_size: int = 50
    ocr_threshold: float = 0.7
    verbose: bool = False


@dataclass
class ProcessingSummary:
    """Summary of a completed processing run."""

    total_pages: int
    pages_processed: int
    pages_skipped: int
    warnings: list[str]
    processing_time_seconds: float


@dataclass
class OCRResult:
    """Result of OCR processing on a page or image."""

    text: str
    confidence: float
    blocks: list[TextBlock]


@dataclass
class QAMatch:
    """A question matched against answer sections."""

    question: str
    matches: list[MatchResult]
    is_unmatched: bool


@dataclass
class MatchResult:
    """A single match between a question and an answer section."""

    section_title: str
    page_range: tuple[int, int]
    similarity_score: float
    text_excerpt: str


@dataclass
class QAReport:
    """Complete Q&A comparison report."""

    questions: list[QAMatch]
    answers_source: str
    questions_source: str
    generated_at: str


@dataclass
class PageRange:
    """A range of pages for chunked processing."""

    start: int  # inclusive
    end: int  # exclusive
