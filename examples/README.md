# Examples

This directory contains example usage of the PDF-to-LLM Converter.

## example_usage.py

Demonstrates programmatic usage of the library:
- Converting a PDF to markdown
- Comparing questions and answers PDFs

To run:
```bash
python examples/example_usage.py
```

Edit the file to uncomment the function calls and provide your PDF paths.

## CLI Examples

### Basic Conversion
```bash
# Convert to stdout
pdf-to-llm convert document.pdf

# Convert to file
pdf-to-llm convert document.pdf -o output.md
```

### Advanced Conversion
```bash
# With custom chunk size and verbose output
pdf-to-llm convert large_document.pdf -o output.md --chunk-size 100 --verbose

# With custom OCR threshold
pdf-to-llm convert scanned_doc.pdf -o output.md --ocr-threshold 0.8
```

### Q&A Comparison
```bash
# Basic comparison
pdf-to-llm compare questions.pdf answers.pdf

# With custom parameters
pdf-to-llm compare questions.pdf answers.pdf --top-n 5 --min-similarity 0.6 --verbose
```

## Sample Output

### Markdown Output Structure
```markdown
<!-- toc -->
- [Introduction](#introduction) (p. 1-3)
- [Methods](#methods) (p. 4-8)
<!-- /toc -->

<!-- page: 1 -->
<!-- section: Introduction -->
# Introduction

Body text here...

| Column A | Column B |
| --- | --- |
| Value 1 | Value 2 |

<!-- page: 2 -->
...
```

### Q&A Report Structure
```
Q&A Match Report
Generated: 2024-01-15T10:30:00Z
Questions source: questions.pdf
Answers source:   answers.pdf
============================================================

Question 1: What are the legal terms?
  Match 1: [Legal Terms] (pages 5-10, similarity: 0.892)
    Excerpt: This section defines legal terms and conditions...
  Match 2: [Definitions] (pages 2-4, similarity: 0.745)
    Excerpt: The following definitions apply throughout...

Question 2: How to file a claim?
  Match 1: [Claims Process] (pages 15-18, similarity: 0.934)
    Excerpt: To file a claim, follow these steps...
```
