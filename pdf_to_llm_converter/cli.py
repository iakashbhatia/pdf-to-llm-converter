"""CLI interface for the PDF-to-LLM converter."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

import click

from pdf_to_llm_converter.models import ProcessingConfig


def _check_dependencies() -> list[str]:
    """Check for missing dependencies and return a list of issues."""
    issues: list[str] = []

    # Check tesseract binary
    if shutil.which("tesseract") is None:
        issues.append(
            "tesseract is not installed or not on PATH. "
            "Install it via your package manager:\n"
            "  macOS:   brew install tesseract\n"
            "  Ubuntu:  sudo apt-get install tesseract-ocr\n"
            "  Windows: download from https://github.com/tesseract-ocr/tesseract"
        )

    # Check required Python packages
    required_packages = {
        "fitz": "PyMuPDF",
        "pytesseract": "pytesseract",
        "PIL": "Pillow",
        "sentence_transformers": "sentence-transformers",
    }
    for module_name, pip_name in required_packages.items():
        try:
            __import__(module_name)
        except ImportError:
            issues.append(
                f"Python package '{pip_name}' is not installed. "
                f"Install it with: pip install {pip_name}"
            )

    return issues


@click.group()
def cli() -> None:
    """PDF-to-LLM Converter: extract structured markdown from PDFs."""


@cli.command()
@click.argument("pdf_path", type=click.Path(exists=False))
@click.option("-o", "--output", "output_path", default=None, type=click.Path(), help="Output file path. Writes to stdout if omitted.")
@click.option("--ocr-threshold", default=0.7, type=float, show_default=True, help="OCR confidence warning threshold.")
@click.option("--chunk-size", default=50, type=int, show_default=True, help="Number of pages per processing chunk.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable detailed progress logging.")
def convert(pdf_path: str, output_path: str | None, ocr_threshold: float, chunk_size: int, verbose: bool) -> None:
    """Convert a PDF file to structured markdown.

    PDF_PATH is the path to the PDF file to convert.
    """
    # Check dependencies first
    issues = _check_dependencies()
    if issues:
        for issue in issues:
            click.echo(issue, err=True)
        raise SystemExit(1)

    import os

    if not os.path.exists(pdf_path):
        click.echo(f"Error: File not found: {pdf_path}", err=True)
        raise SystemExit(1)

    from pdf_to_llm_converter.markdown_converter import MarkdownConverter
    from pdf_to_llm_converter.pdf_processor import PDFProcessor

    config = ProcessingConfig(
        chunk_size=chunk_size,
        ocr_threshold=ocr_threshold,
        verbose=verbose,
    )

    processor = PDFProcessor()
    try:
        document, summary = processor.process(pdf_path, config)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    converter = MarkdownConverter()
    markdown = converter.to_markdown(document)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        click.echo(f"Output written to {output_path}", err=True)
    else:
        click.echo(markdown)

    # Print processing summary to stderr
    click.echo(
        f"\nProcessing summary:\n"
        f"  Total pages:     {summary.total_pages}\n"
        f"  Pages processed: {summary.pages_processed}\n"
        f"  Pages skipped:   {summary.pages_skipped}\n"
        f"  Processing time: {summary.processing_time_seconds:.2f}s\n"
        f"  Warnings:        {len(summary.warnings)}",
        err=True,
    )
    if summary.warnings:
        for w in summary.warnings:
            click.echo(f"  - {w}", err=True)


@cli.command()
@click.argument("questions_pdf", type=click.Path(exists=False))
@click.argument("answers_pdf", type=click.Path(exists=False))
@click.option("--top-n", default=3, type=int, show_default=True, help="Number of top matches per question.")
@click.option("--min-similarity", default=0.5, type=float, show_default=True, help="Minimum similarity threshold.")
@click.option("--ocr-threshold", default=0.7, type=float, show_default=True, help="OCR confidence warning threshold.")
@click.option("--chunk-size", default=50, type=int, show_default=True, help="Number of pages per processing chunk.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable detailed progress logging.")
def compare(
    questions_pdf: str,
    answers_pdf: str,
    top_n: int,
    min_similarity: float,
    ocr_threshold: float,
    chunk_size: int,
    verbose: bool,
) -> None:
    """Compare a questions PDF against an answers PDF.

    Produces a Q&A match report showing the best answer sections for each question.

    QUESTIONS_PDF is the path to the PDF containing questions.
    ANSWERS_PDF is the path to the PDF containing answers.
    """
    # Check dependencies first
    issues = _check_dependencies()
    if issues:
        for issue in issues:
            click.echo(issue, err=True)
        raise SystemExit(1)

    import os

    for path, label in [(questions_pdf, "Questions"), (answers_pdf, "Answers")]:
        if not os.path.exists(path):
            click.echo(f"Error: {label} file not found: {path}", err=True)
            raise SystemExit(1)

    from pdf_to_llm_converter.markdown_converter import MarkdownConverter
    from pdf_to_llm_converter.pdf_processor import PDFProcessor
    from pdf_to_llm_converter.qa_matcher import QAMatcher

    config = ProcessingConfig(
        chunk_size=chunk_size,
        ocr_threshold=ocr_threshold,
        verbose=verbose,
    )

    processor = PDFProcessor()
    converter = MarkdownConverter()

    # Process both PDFs
    if verbose:
        click.echo("Processing questions PDF...", err=True)
    try:
        questions_doc, q_summary = processor.process(questions_pdf, config)
    except RuntimeError as exc:
        click.echo(f"Error processing questions PDF: {exc}", err=True)
        raise SystemExit(1)

    if verbose:
        click.echo("Processing answers PDF...", err=True)
    try:
        answers_doc, a_summary = processor.process(answers_pdf, config)
    except RuntimeError as exc:
        click.echo(f"Error processing answers PDF: {exc}", err=True)
        raise SystemExit(1)

    # Extract questions from the questions document (one per section/page body)
    questions: list[str] = []
    for page in questions_doc.pages:
        text = page.content.body_text.strip()
        if text:
            questions.append(text)

    if not questions:
        click.echo("Warning: No questions extracted from the questions PDF.", err=True)
        raise SystemExit(1)

    # Split answers into sections
    matcher = QAMatcher()
    answer_sections = matcher.split_into_sections(answers_doc)

    if not answer_sections:
        click.echo("Warning: No answer sections found in the answers PDF.", err=True)
        raise SystemExit(1)

    # Match
    results = matcher.match(
        questions=questions,
        answer_sections=answer_sections,
        top_n=top_n,
        min_similarity=min_similarity,
    )

    # Format and output report
    now = datetime.now(timezone.utc).isoformat()
    click.echo(f"Q&A Match Report")
    click.echo(f"Generated: {now}")
    click.echo(f"Questions source: {questions_pdf}")
    click.echo(f"Answers source:   {answers_pdf}")
    click.echo(f"{'=' * 60}")

    for i, qa in enumerate(results, 1):
        click.echo(f"\nQuestion {i}: {qa.question[:200]}")
        if qa.is_unmatched:
            click.echo("  Status: UNMATCHED (no answer above similarity threshold)")
        else:
            for j, match in enumerate(qa.matches, 1):
                click.echo(
                    f"  Match {j}: [{match.section_title}] "
                    f"(pages {match.page_range[0]}-{match.page_range[1]}, "
                    f"similarity: {match.similarity_score:.3f})"
                )
                excerpt = match.text_excerpt[:200].replace("\n", " ")
                click.echo(f"    Excerpt: {excerpt}...")

    click.echo(f"\n{'=' * 60}")
    click.echo(f"Total questions: {len(results)}")
    matched = sum(1 for r in results if not r.is_unmatched)
    click.echo(f"Matched: {matched}, Unmatched: {len(results) - matched}")
