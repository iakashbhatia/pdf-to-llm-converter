"""Unit tests for the CLI interface.

Tests cover:
- convert command with valid/invalid paths (Req 1.3, 8.1, 8.3)
- compare command invocation (Req 8.2)
- Default option values (Req 8.1-8.9)
- --help output (Req 8.8)
- Missing dependency error messages (Req 9.4)
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from click.testing import CliRunner

from pdf_to_llm_converter.cli import cli, _check_dependencies
from pdf_to_llm_converter.models import (
    Document,
    DocumentSection,
    ExtractedContent,
    PageClassification,
    PageContent,
    ProcessingSummary,
)


def _make_dummy_document(num_pages: int = 1) -> Document:
    """Create a minimal Document for mocking processor output."""
    pages = []
    for i in range(num_pages):
        pages.append(
            PageContent(
                page_number=i + 1,
                classification=PageClassification.NATIVE_TEXT,
                content=ExtractedContent(
                    body_text=f"Page {i + 1} body text",
                    headers=[],
                    footers=[],
                    tables=[],
                    reading_order_blocks=[],
                ),
                ocr_confidence=None,
            )
        )
    sections = [
        DocumentSection(
            title="Test Section",
            level=1,
            content="Test content",
            page_start=1,
            page_end=num_pages,
            subsections=[],
        )
    ]
    return Document(sections=sections, pages=pages)


def _make_dummy_summary(num_pages: int = 1) -> ProcessingSummary:
    return ProcessingSummary(
        total_pages=num_pages,
        pages_processed=num_pages,
        pages_skipped=0,
        warnings=[],
        processing_time_seconds=0.5,
    )


# ---------------------------------------------------------------------------
# convert command tests
# ---------------------------------------------------------------------------


class TestConvertCommand:
    """Tests for the `convert` CLI command."""

    def test_convert_nonexistent_file_returns_error(self):
        """Req 1.3: descriptive error for non-existent file path."""
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "/tmp/does_not_exist_abc123.pdf"])
        assert result.exit_code != 0

    @patch("pdf_to_llm_converter.cli._check_dependencies", return_value=[])
    def test_convert_nonexistent_file_after_dep_check(self, mock_deps):
        """Req 1.3: error message when file doesn't exist (deps satisfied)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "/tmp/no_such_file_xyz.pdf"])
        assert result.exit_code != 0
        assert "File not found" in result.output

    @patch("pdf_to_llm_converter.cli._check_dependencies", return_value=[])
    @patch("pdf_to_llm_converter.pdf_processor.PDFProcessor.process")
    @patch("pdf_to_llm_converter.markdown_converter.MarkdownConverter.to_markdown")
    def test_convert_writes_to_stdout_when_no_output(self, mock_to_md, mock_process, mock_deps):
        """Req 8.3: output goes to stdout when --output is omitted."""
        doc = _make_dummy_document()
        summary = _make_dummy_summary()
        mock_process.return_value = (doc, summary)
        mock_to_md.return_value = "# Markdown Output"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            tmp_path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["convert", tmp_path])
            assert result.exit_code == 0
            assert "# Markdown Output" in result.output
        finally:
            os.unlink(tmp_path)

    @patch("pdf_to_llm_converter.cli._check_dependencies", return_value=[])
    @patch("pdf_to_llm_converter.pdf_processor.PDFProcessor.process")
    @patch("pdf_to_llm_converter.markdown_converter.MarkdownConverter.to_markdown")
    def test_convert_writes_to_file_when_output_specified(self, mock_to_md, mock_process, mock_deps):
        """Req 8.1: convert writes to file when --output is given."""
        doc = _make_dummy_document()
        summary = _make_dummy_summary()
        mock_process.return_value = (doc, summary)
        mock_to_md.return_value = "# File Output"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            tmp_pdf = f.name

        out_path = tmp_pdf + ".md"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["convert", tmp_pdf, "--output", out_path])
            assert result.exit_code == 0
            assert os.path.exists(out_path)
            with open(out_path) as fh:
                assert "# File Output" in fh.read()
        finally:
            os.unlink(tmp_pdf)
            if os.path.exists(out_path):
                os.unlink(out_path)


# ---------------------------------------------------------------------------
# compare command tests
# ---------------------------------------------------------------------------


class TestCompareCommand:
    """Tests for the `compare` CLI command."""

    def test_compare_nonexistent_questions_file(self):
        """Req 1.3: error when questions PDF doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["compare", "/tmp/no_q.pdf", "/tmp/no_a.pdf"])
        assert result.exit_code != 0

    @patch("pdf_to_llm_converter.cli._check_dependencies", return_value=[])
    def test_compare_nonexistent_questions_after_dep_check(self, mock_deps):
        """Error message for missing questions file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["compare", "/tmp/no_q.pdf", "/tmp/no_a.pdf"])
        assert result.exit_code != 0
        assert "not found" in result.output

    @patch("pdf_to_llm_converter.cli._check_dependencies", return_value=[])
    def test_compare_nonexistent_answers_file(self, mock_deps):
        """Error message for missing answers file when questions file exists."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            q_path = f.name
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["compare", q_path, "/tmp/no_answers.pdf"])
            assert result.exit_code != 0
            assert "not found" in result.output
        finally:
            os.unlink(q_path)


# ---------------------------------------------------------------------------
# Default option values
# ---------------------------------------------------------------------------


class TestDefaultOptions:
    """Verify default values for CLI options."""

    def test_convert_help_shows_defaults(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "0.7" in result.output   # --ocr-threshold default
        assert "50" in result.output    # --chunk-size default

    def test_compare_help_shows_defaults(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["compare", "--help"])
        assert result.exit_code == 0
        assert "3" in result.output     # --top-n default
        assert "0.5" in result.output   # --min-similarity default
        assert "0.7" in result.output   # --ocr-threshold default
        assert "50" in result.output    # --chunk-size default


# ---------------------------------------------------------------------------
# --help output
# ---------------------------------------------------------------------------


class TestHelpOutput:
    """Req 8.8: --help displays usage information."""

    def test_main_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "convert" in result.output
        assert "compare" in result.output

    def test_convert_help_describes_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "PDF_PATH" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--ocr-threshold" in result.output
        assert "--chunk-size" in result.output
        assert "--verbose" in result.output or "-v" in result.output

    def test_compare_help_describes_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["compare", "--help"])
        assert result.exit_code == 0
        assert "QUESTIONS_PDF" in result.output
        assert "ANSWERS_PDF" in result.output
        assert "--top-n" in result.output
        assert "--min-similarity" in result.output


# ---------------------------------------------------------------------------
# Missing dependency error messages
# ---------------------------------------------------------------------------


class TestMissingDependencies:
    """Req 9.4: report missing dependencies with installation guidance."""

    @patch("shutil.which", return_value=None)
    def test_missing_tesseract_reported(self, mock_which):
        """_check_dependencies detects missing tesseract."""
        issues = _check_dependencies()
        tesseract_issues = [i for i in issues if "tesseract" in i.lower()]
        assert len(tesseract_issues) >= 1
        assert any("install" in i.lower() for i in tesseract_issues)

    @patch("builtins.__import__", side_effect=ImportError("no module"))
    @patch("shutil.which", return_value="/usr/bin/tesseract")
    def test_missing_python_package_reported(self, mock_which, mock_import):
        """_check_dependencies detects missing Python packages."""
        issues = _check_dependencies()
        assert len(issues) > 0
        assert any("pip install" in i for i in issues)

    @patch("pdf_to_llm_converter.cli._check_dependencies")
    def test_convert_exits_on_missing_deps(self, mock_deps):
        """Convert command exits with code 1 when dependencies are missing."""
        mock_deps.return_value = ["tesseract is not installed"]
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "dummy.pdf"])
        assert result.exit_code != 0
        assert "tesseract" in result.output

    @patch("pdf_to_llm_converter.cli._check_dependencies")
    def test_compare_exits_on_missing_deps(self, mock_deps):
        """Compare command exits with code 1 when dependencies are missing."""
        mock_deps.return_value = ["PyMuPDF is not installed"]
        runner = CliRunner()
        result = runner.invoke(cli, ["compare", "q.pdf", "a.pdf"])
        assert result.exit_code != 0
        assert "PyMuPDF" in result.output
