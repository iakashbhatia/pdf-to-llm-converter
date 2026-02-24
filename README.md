# PDF-to-LLM Converter

Convert large PDF files (140MB+) containing mixed content (native text, scanned images, embedded pictures) into structured markdown suitable for LLM ingestion. Designed for legal documents where accuracy and completeness are critical.

## Features

- **Large PDF Support**: Process 140MB+ PDFs efficiently with chunked processing
- **Mixed Content Handling**: Automatically detects and processes native text, scanned pages, and mixed content
- **High-Accuracy OCR**: Uses Tesseract with preprocessing (deskewing, contrast enhancement, noise reduction)
- **Structured Output**: Generates markdown with preserved document hierarchy, tables, lists, and metadata
- **Q&A Comparison**: Semantically match questions from one PDF against answer sections in another
- **Round-Trip Serialization**: Parse markdown back into document models without loss

## Installation

### Prerequisites

1. **Python 3.10+**
2. **Tesseract OCR**:
   - macOS: `brew install tesseract`
   - Ubuntu: `sudo apt-get install tesseract-ocr`
   - Windows: Download from [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract)

### Install from source

```bash
git clone https://github.com/iakashbhatia/pdf-to-llm-converter.git
cd pdf-to-llm-converter
pip install -e .
```

### Install dependencies only

```bash
pip install -r requirements.txt
```

## Usage

### Convert PDF to Markdown

```bash
# Write to stdout
pdf-to-llm convert document.pdf

# Write to file
pdf-to-llm convert document.pdf -o output.md

# With options
pdf-to-llm convert document.pdf -o output.md --chunk-size 100 --verbose
```

### Compare Questions and Answers PDFs

```bash
pdf-to-llm compare questions.pdf answers.pdf

# With options
pdf-to-llm compare questions.pdf answers.pdf --top-n 5 --min-similarity 0.6
```

### CLI Options

**Convert command:**
- `-o, --output PATH`: Output file path (writes to stdout if omitted)
- `--ocr-threshold FLOAT`: OCR confidence warning threshold (default: 0.7)
- `--chunk-size INTEGER`: Pages per processing chunk (default: 50)
- `-v, --verbose`: Enable detailed progress logging

**Compare command:**
- `--top-n INTEGER`: Number of top matches per question (default: 3)
- `--min-similarity FLOAT`: Minimum similarity threshold (default: 0.5)
- `--ocr-threshold FLOAT`: OCR confidence warning threshold (default: 0.7)
- `--chunk-size INTEGER`: Pages per processing chunk (default: 50)
- `-v, --verbose`: Enable detailed progress logging

## How It Works

1. **PDF Ingestion**: Opens PDF and processes in chunks to avoid memory issues
2. **Page Classification**: Classifies each page as native text (>80% text), scanned (<20% text), or mixed
3. **Content Extraction**:
   - Native text: Direct extraction via PyMuPDF
   - Scanned: OCR via Tesseract with preprocessing
   - Mixed: Both methods, then intelligent merging
4. **Markdown Conversion**: Generates structured markdown with:
   - Table of contents with page references
   - Page number metadata comments
   - Section metadata comments
   - Preserved tables, lists, and headings
5. **Q&A Matching** (optional): Uses sentence-transformers to compute semantic similarity between questions and answer sections

## Architecture

```
PDF → ChunkManager → PageClassifier → TextExtractor/OCREngine → ContentMerger → MarkdownConverter → Output
```

Key components:
- **ChunkManager**: Splits large PDFs into manageable page ranges
- **PageClassifier**: Determines content type (native/scanned/mixed)
- **TextExtractor**: Extracts native text with structure preservation
- **OCREngine**: Performs OCR with preprocessing pipeline
- **ContentMerger**: Merges native text and OCR results for mixed pages
- **MarkdownConverter**: Converts to/from structured markdown
- **QAMatcher**: Semantic similarity matching for Q&A workflow

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Project Structure

```
pdf-to-llm-converter/
├── pdf_to_llm_converter/     # Main package
│   ├── models.py             # Data models
│   ├── chunk_manager.py      # PDF chunking
│   ├── page_classifier.py    # Page classification
│   ├── text_extractor.py     # Native text extraction
│   ├── ocr_engine.py          # OCR processing
│   ├── content_merger.py     # Content merging
│   ├── markdown_converter.py # Markdown conversion
│   ├── pdf_processor.py      # Main pipeline
│   ├── qa_matcher.py         # Q&A matching
│   └── cli.py                # CLI interface
├── tests/                    # Test suite
├── .kiro/specs/              # Design specifications
├── pyproject.toml            # Package configuration
└── README.md                 # This file
```

## Requirements

- Python 3.10+
- PyMuPDF (fitz) >= 1.23.0
- pytesseract >= 0.3.10
- Pillow >= 10.0.0
- sentence-transformers >= 2.2.0
- click >= 8.1.0
- pytest >= 7.4.0 (dev)
- hypothesis >= 6.82.0 (dev)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Acknowledgments

- Built with [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF parsing
- OCR powered by [Tesseract](https://github.com/tesseract-ocr/tesseract)
- Semantic matching via [sentence-transformers](https://www.sbert.net/)
