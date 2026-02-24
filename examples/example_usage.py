#!/usr/bin/env python3
"""Example usage of the PDF-to-LLM Converter library."""

from pdf_to_llm_converter.models import ProcessingConfig
from pdf_to_llm_converter.pdf_processor import PDFProcessor
from pdf_to_llm_converter.markdown_converter import MarkdownConverter
from pdf_to_llm_converter.qa_matcher import QAMatcher


def convert_pdf_to_markdown(pdf_path: str, output_path: str) -> None:
    """Convert a PDF file to structured markdown."""
    # Configure processing
    config = ProcessingConfig(
        chunk_size=50,
        ocr_threshold=0.7,
        verbose=True,
    )

    # Process PDF
    processor = PDFProcessor()
    document, summary = processor.process(pdf_path, config)

    # Convert to markdown
    converter = MarkdownConverter()
    markdown = converter.to_markdown(document)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    # Print summary
    print(f"\nProcessing Summary:")
    print(f"  Total pages: {summary.total_pages}")
    print(f"  Processed: {summary.pages_processed}")
    print(f"  Skipped: {summary.pages_skipped}")
    print(f"  Time: {summary.processing_time_seconds:.2f}s")
    print(f"  Warnings: {len(summary.warnings)}")


def compare_qa_pdfs(questions_pdf: str, answers_pdf: str) -> None:
    """Compare questions PDF against answers PDF."""
    config = ProcessingConfig(chunk_size=50, ocr_threshold=0.7, verbose=False)

    # Process both PDFs
    processor = PDFProcessor()
    questions_doc, _ = processor.process(questions_pdf, config)
    answers_doc, _ = processor.process(answers_pdf, config)

    # Extract questions (one per page body text)
    questions = [
        page.content.body_text.strip()
        for page in questions_doc.pages
        if page.content.body_text.strip()
    ]

    # Get answer sections
    matcher = QAMatcher()
    answer_sections = matcher.split_into_sections(answers_doc)

    # Match questions to answers
    results = matcher.match(
        questions=questions,
        answer_sections=answer_sections,
        top_n=3,
        min_similarity=0.5,
    )

    # Print results
    print(f"\nQ&A Match Report")
    print("=" * 60)
    for i, qa in enumerate(results, 1):
        print(f"\nQuestion {i}: {qa.question[:100]}...")
        if qa.is_unmatched:
            print("  Status: UNMATCHED")
        else:
            for j, match in enumerate(qa.matches, 1):
                print(
                    f"  Match {j}: [{match.section_title}] "
                    f"(pages {match.page_range[0]}-{match.page_range[1]}, "
                    f"similarity: {match.similarity_score:.3f})"
                )


def main():
    """Example usage."""
    # Example 1: Convert PDF to markdown
    print("Example 1: Converting PDF to markdown...")
    # convert_pdf_to_markdown("input.pdf", "output.md")

    # Example 2: Compare Q&A PDFs
    print("\nExample 2: Comparing Q&A PDFs...")
    # compare_qa_pdfs("questions.pdf", "answers.pdf")

    print("\nUncomment the function calls above and provide PDF paths to run.")


if __name__ == "__main__":
    main()
