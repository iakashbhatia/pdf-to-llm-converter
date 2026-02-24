# Implementation Plan: PDF-to-LLM Converter

## Overview

Incremental implementation of a Python CLI/library for converting large PDFs to structured markdown and performing Q&A comparison. Each task builds on the previous, with property tests validating correctness at each stage.

## Tasks

- [x] 1. Set up project structure and core data models
  - [x] 1.1 Create project directory structure, `pyproject.toml` with dependencies (pymupdf, pytesseract, Pillow, sentence-transformers, click, hypothesis, pytest), and `__init__.py` files
    - Directory: `pdf_to_llm_converter/` with modules for each component
    - _Requirements: 8.1, 8.2_
  - [x] 1.2 Define all core data model dataclasses in `pdf_to_llm_converter/models.py`
    - `PageClassification` enum, `TextBlock`, `Table`, `ExtractedContent`, `PageContent`, `DocumentSection`, `Document`, `ProcessingConfig`, `ProcessingSummary`, `OCRResult`, `QAMatch`, `MatchResult`, `QAReport`, `PageRange`
    - _Requirements: 2.1, 5.5, 7.5_

- [x] 2. Implement Chunk_Manager
  - [x] 2.1 Implement `ChunkManager.iter_chunks()` in `pdf_to_llm_converter/chunk_manager.py`
    - Accept pdf_path and chunk_size, yield `PageRange` objects covering all pages
    - Use PyMuPDF to get page count without loading all pages
    - _Requirements: 1.1, 1.2_
  - [x] 2.2 Write property test for chunk coverage (Property 1)
    - **Property 1: Chunk coverage is complete and disjoint**
    - **Validates: Requirements 1.2**

- [x] 3. Implement Page_Classifier
  - [x] 3.1 Implement `PageClassifier.classify()` in `pdf_to_llm_converter/page_classifier.py`
    - Compute text coverage ratio using PyMuPDF text extraction area vs page area
    - Return classification based on threshold boundaries (0.2, 0.8)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [x] 3.2 Write property test for classification correctness (Property 3)
    - **Property 3: Page classification correctness by coverage ratio**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [x] 4. Implement Text_Extractor
  - [x] 4.1 Implement `TextExtractor.extract()` in `pdf_to_llm_converter/text_extractor.py`
    - Use PyMuPDF `page.get_text("dict")` for block-level extraction with bounding boxes
    - Use `page.find_tables()` for table detection
    - Detect headers/footers by vertical position heuristics
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 4.2 Write unit tests for Text_Extractor
    - Test table extraction preserves row/column structure
    - Test header/footer detection and tagging
    - _Requirements: 3.3, 3.4_

- [x] 5. Implement OCR_Engine
  - [x] 5.1 Implement `OCREngine` in `pdf_to_llm_converter/ocr_engine.py`
    - Implement preprocessing pipeline: grayscale, deskew, contrast enhancement, noise reduction
    - Use pytesseract `image_to_data` for word-level OCR with confidence
    - Compute mean confidence score from word-level results
    - Support OCR on embedded images
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 5.2 Write property test for OCR confidence invariant (Property 5)
    - **Property 5: OCR confidence score invariant**
    - **Validates: Requirements 4.3**
  - [x] 5.3 Write property test for low-confidence warning (Property 6)
    - **Property 6: Low-confidence OCR triggers warning**
    - **Validates: Requirements 4.4**

- [x] 6. Implement Content_Merger and extraction routing
  - [x] 6.1 Implement `ContentMerger.merge()` in `pdf_to_llm_converter/content_merger.py`
    - Merge native text and OCR results using bounding box overlap detection
    - Prefer native text blocks when overlap > 50%
    - _Requirements: 2.5_
  - [x] 6.2 Implement extraction routing logic in `pdf_to_llm_converter/pdf_processor.py`
    - Route pages to Text_Extractor, OCR_Engine, or both based on classification
    - Wire Content_Merger for mixed pages
    - _Requirements: 2.5, 4.1_
  - [x] 6.3 Write property test for extraction routing (Property 4)
    - **Property 4: Extraction method routing matches classification**
    - **Validates: Requirements 2.5, 4.1**

- [x] 7. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Markdown_Converter
  - [x] 8.1 Implement `MarkdownConverter.to_markdown()` in `pdf_to_llm_converter/markdown_converter.py`
    - Render headings with correct `#` levels
    - Render tables in markdown table syntax
    - Render lists with nesting
    - Insert `<!-- page: N -->` and `<!-- section: TITLE -->` comments
    - Generate table of contents at document start
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  - [x] 8.2 Implement `MarkdownConverter.from_markdown()` for parsing markdown back to Document model
    - Parse page comments, section comments, headings, tables, lists
    - Reconstruct Document model from parsed markdown
    - _Requirements: 6.1, 6.2_
  - [x] 8.3 Write property test for markdown content rendering (Property 7)
    - **Property 7: Markdown renders all content types correctly**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
  - [x] 8.4 Write property test for metadata comments (Property 8)
    - **Property 8: Markdown includes correct page and section metadata**
    - **Validates: Requirements 5.5, 5.6**
  - [x] 8.5 Write property test for TOC completeness (Property 9)
    - **Property 9: Table of contents lists all sections**
    - **Validates: Requirements 5.7**
  - [x] 8.6 Write property test for round-trip serialization (Property 10)
    - **Property 10: Document model serialization round-trip**
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [x] 9. Implement PDF_Processor pipeline
  - [x] 9.1 Implement `PDFProcessor.process()` in `pdf_to_llm_converter/pdf_processor.py`
    - Wire Chunk_Manager, Page_Classifier, Text_Extractor, OCR_Engine, Content_Merger, Markdown_Converter
    - Handle corrupted pages: log warning, skip, continue
    - Build ProcessingSummary with page counts and timing
    - Support verbose logging per page
    - _Requirements: 1.1, 1.4, 1.5, 9.1, 9.2, 9.3_
  - [x] 9.2 Write property test for processing summary invariant (Property 2)
    - **Property 2: Processing summary invariant**
    - **Validates: Requirements 1.5**

- [x] 10. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement QA_Matcher
  - [x] 11.1 Implement `QAMatcher.match()` in `pdf_to_llm_converter/qa_matcher.py`
    - Split answer document into sections by headings
    - Compute embeddings using sentence-transformers (all-MiniLM-L6-v2)
    - Compute cosine similarity matrix
    - Return top-N matches per question, flag unmatched questions
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6_
  - [x] 11.2 Write property test for similarity score bounds (Property 11)
    - **Property 11: Similarity scores are bounded**
    - **Validates: Requirements 7.3**
  - [x] 11.3 Write property test for match ranking and completeness (Property 12)
    - **Property 12: QA match results are ranked, bounded, and complete**
    - **Validates: Requirements 7.4, 7.5**
  - [x] 11.4 Write property test for unmatched flagging (Property 13)
    - **Property 13: Unmatched questions are correctly flagged**
    - **Validates: Requirements 7.6**

- [x] 12. Implement CLI
  - [x] 12.1 Implement CLI with Click in `pdf_to_llm_converter/cli.py`
    - `convert` command: accepts PDF path, optional output path, writes markdown to file or stdout
    - `compare` command: accepts questions PDF and answers PDF, produces Q&A match report
    - Options: `--ocr-threshold` (default 0.7), `--chunk-size` (default 50), `--top-n` (default 3), `--min-similarity` (default 0.5), `--verbose`, `--help`
    - Dependency checking on startup: report missing tesseract or Python packages
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 9.4_
  - [x] 12.2 Write unit tests for CLI
    - Test `convert` command with valid/invalid paths
    - Test `compare` command invocation
    - Test default option values
    - Test `--help` output
    - Test missing dependency error messages
    - _Requirements: 1.3, 8.1, 8.2, 8.3, 9.4_

- [x] 13. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use Hypothesis with minimum 100 examples per property
- Unit tests cover specific examples and edge cases
- The implementation language is Python, using pytest + Hypothesis for testing
