# Contributing

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/pdf-to-llm-converter.git
cd pdf-to-llm-converter
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v
```

## Project Structure

```
pdf_to_llm_converter/
  models.py           — all dataclasses and enums
  chunk_manager.py    — chunked PDF page iteration
  page_classifier.py  — native_text / scanned / mixed detection
  text_extractor.py   — PyMuPDF native text extraction
  ocr_engine.py       — Tesseract OCR with preprocessing
  content_merger.py   — merge native + OCR for mixed pages
  markdown_converter.py — to_markdown() and from_markdown()
  pdf_processor.py    — full pipeline orchestration
  qa_matcher.py       — semantic Q&A matching
  cli.py              — Click CLI entry points

tests/
  test_chunk_manager.py
  test_page_classifier.py
  test_text_extractor.py
  test_ocr_engine.py
  test_content_merger.py
  test_extraction_routing.py
  test_markdown_converter.py
  test_pdf_processor.py
  test_qa_matcher.py
  test_cli.py
```

## Pull Requests

- Keep changes focused and minimal
- Add or update tests for any new behaviour
- Ensure `pytest` passes before opening a PR
