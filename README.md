# pdf-to-llm-converter

Convert large PDF files — including scanned pages, embedded images, and native text — into structured Markdown for LLM ingestion. Built for legal documents where accuracy and completeness are critical.

## Features

- **Handles large PDFs (140 MB+)** via chunked, memory-efficient processing
- **Mixed-content detection** — automatically classifies each page as native text, scanned, or mixed
- **OCR with preprocessing** — deskew, contrast enhancement, noise reduction via Tesseract
- **Structured Markdown output** — headings, tables, lists, page metadata comments, and a table of contents
- **Q&A comparison workflow** — semantically match questions from one PDF against answer sections in another using sentence-transformers
- **CLI interface** — `convert` and `compare` commands with sensible defaults

## Requirements

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your PATH

### Install Tesseract

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# Windows
# Download installer from https://github.com/tesseract-ocr/tesseract
```

## Installation

```bash
pip install pdf-to-llm-converter
```

Or install from source:

```bash
git clone https://github.com/YOUR_USERNAME/pdf-to-llm-converter.git
cd pdf-to-llm-converter
pip install -e ".[dev]"
```

## Usage

### Convert a PDF to Markdown

```bash
# Output to stdout
pdf-to-llm convert document.pdf

# Output to file
pdf-to-llm convert document.pdf -o output.md

# With options
pdf-to-llm convert document.pdf -o output.md \
  --chunk-size 25 \
  --ocr-threshold 0.8 \
  --verbose
```

### Compare a Questions PDF against an Answers PDF

```bash
pdf-to-llm compare questions.pdf answers.pdf

# With options
pdf-to-llm compare questions.pdf answers.pdf \
  --top-n 5 \
  --min-similarity 0.4 \
  --verbose
```

### CLI Reference

```
pdf-to-llm convert [OPTIONS] PDF_PATH

  Options:
    -o, --output PATH        Output file path (stdout if omitted)
    --ocr-threshold FLOAT    OCR confidence warning threshold  [default: 0.7]
    --chunk-size INTEGER     Pages per processing chunk        [default: 50]
    -v, --verbose            Detailed progress logging
    --help

pdf-to-llm compare [OPTIONS] QUESTIONS_PDF ANSWERS_PDF

  Options:
    --top-n INTEGER          Top matches per question          [default: 3]
    --min-similarity FLOAT   Minimum similarity threshold      [default: 0.5]
    --ocr-threshold FLOAT    OCR confidence warning threshold  [default: 0.7]
    --chunk-size INTEGER     Pages per processing chunk        [default: 50]
    -v, --verbose            Detailed progress logging
    --help
```

## Output Format

```markdown
<!-- toc -->
- [Section Title](#section-title) (p. 1-5)
- [Another Section](#another-section) (p. 6-10)
<!-- /toc -->

<!-- page: 1 -->
<!-- section: Section Title -->
# Section Title

Body text here...

| Col A | Col B |
|-------|-------|
| val1  | val2  |

<!-- page: 2 -->
...
```

## Architecture

```
PDF file
  └─► ChunkManager        — splits into page-range chunks
        └─► PageClassifier — native_text / scanned / mixed
              ├─► TextExtractor   — PyMuPDF block-level extraction
              ├─► OCREngine       — Tesseract with preprocessing
              └─► ContentMerger   — deduplicates overlapping regions
                    └─► MarkdownConverter — structured markdown output

Q&A workflow:
  Questions PDF + Answers PDF
    └─► PDFProcessor (both)
          └─► QAMatcher — sentence-transformers cosine similarity
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with verbose output
pytest -v
```

## License

MIT — see [LICENSE](LICENSE).
