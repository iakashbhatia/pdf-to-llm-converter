"""Unit tests for OCREngine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from pdf_to_llm_converter.models import OCRResult
from pdf_to_llm_converter.ocr_engine import OCREngine


def _make_tesseract_data(words: list[tuple[str, int, int, int, int, int]]) -> dict:
    """Build a pytesseract image_to_data dict from (text, conf, left, top, w, h) tuples."""
    data: dict[str, list] = {
        "text": [],
        "conf": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
    }
    for text, conf, left, top, w, h in words:
        data["text"].append(text)
        data["conf"].append(conf)
        data["left"].append(left)
        data["top"].append(top)
        data["width"].append(w)
        data["height"].append(h)
    return data


class TestOCREnginePreprocessing:
    """Tests for the preprocessing pipeline."""

    def test_preprocessing_converts_to_grayscale(self) -> None:
        engine = OCREngine(preprocessing=True)
        rgb_image = Image.new("RGB", (100, 100), color=(255, 0, 0))
        result = engine._preprocess(rgb_image)
        assert result.mode == "L"

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_preprocessing_deskews_rotated_image(self, mock_osd: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 90\nOrientation: 0"
        engine = OCREngine(preprocessing=True)
        img = Image.new("L", (100, 200), color=128)
        result = engine._preprocess(img)
        # Rotated 90 degrees, so dimensions should swap (approximately)
        assert result.size[0] >= 190  # width should now be ~200
        assert result.size[1] >= 90   # height should now be ~100

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_preprocessing_skips_deskew_on_osd_failure(self, mock_osd: MagicMock) -> None:
        import pytesseract
        mock_osd.side_effect = pytesseract.TesseractError("osd", "failed")
        engine = OCREngine(preprocessing=True)
        img = Image.new("L", (100, 100), color=128)
        result = engine._preprocess(img)
        # Should still return an image without crashing
        assert result.mode == "L"
        assert result.size == (100, 100)

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_preprocessing_no_rotation_when_angle_zero(self, mock_osd: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0\nOrientation: 0"
        engine = OCREngine(preprocessing=True)
        img = Image.new("L", (100, 100), color=128)
        result = engine._preprocess(img)
        assert result.size == (100, 100)


class TestOCREngineOCR:
    """Tests for OCR execution and confidence computation."""

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_ocr_page_returns_ocr_result(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("Hello", 95, 10, 10, 50, 20),
            ("world", 90, 70, 10, 50, 20),
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        assert isinstance(result, OCRResult)
        assert result.text == "Hello world"
        assert abs(result.confidence - 0.925) < 0.001
        assert len(result.blocks) == 2

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_confidence_filters_negative_one(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        """Confidence -1 entries (non-word elements) are excluded from mean."""
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("", -1, 0, 0, 0, 0),       # non-word element
            ("Test", 80, 10, 10, 40, 15),
            ("", -1, 0, 0, 0, 0),        # another non-word
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        assert result.text == "Test"
        assert abs(result.confidence - 0.80) < 0.001
        assert len(result.blocks) == 1

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_empty_ocr_returns_zero_confidence(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("", -1, 0, 0, 0, 0),
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        assert result.text == ""
        assert result.confidence == 0.0
        assert len(result.blocks) == 0

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_confidence_is_clamped_to_unit_range(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("word", 100, 0, 0, 10, 10),
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        assert 0.0 <= result.confidence <= 1.0

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    def test_ocr_without_preprocessing(self, mock_data: MagicMock) -> None:
        mock_data.return_value = _make_tesseract_data([
            ("NoPrep", 85, 5, 5, 30, 10),
        ])
        engine = OCREngine(preprocessing=False)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        assert result.text == "NoPrep"
        assert abs(result.confidence - 0.85) < 0.001

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_ocr_embedded_image(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("STAMP", 70, 10, 10, 60, 20),
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_embedded_image(Image.new("RGB", (100, 50)))
        assert isinstance(result, OCRResult)
        assert result.text == "STAMP"
        assert abs(result.confidence - 0.70) < 0.001

    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data")
    @patch("pdf_to_llm_converter.ocr_engine.pytesseract.image_to_osd")
    def test_blocks_have_correct_bboxes(self, mock_osd: MagicMock, mock_data: MagicMock) -> None:
        mock_osd.return_value = "Rotate: 0"
        mock_data.return_value = _make_tesseract_data([
            ("word", 90, 10, 20, 50, 15),
        ])
        engine = OCREngine(preprocessing=True)
        result = engine.ocr_page(Image.new("RGB", (200, 100)))
        block = result.blocks[0]
        assert block.bbox == (10.0, 20.0, 60.0, 35.0)
        assert block.text == "word"
        assert block.block_type == "paragraph"

# Feature: pdf-to-llm-converter, Property 5: OCR confidence score invariant
# Validates: Requirements 4.3
class TestOCRConfidenceInvariant:
    """Property test: For any OCR result, the confidence score is a float in [0.0, 1.0]."""

    @given(
        word_confs=st.lists(
            st.integers(min_value=0, max_value=100),
            min_size=0,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_confidence_in_unit_range_for_any_word_confidences(
        self, word_confs: list[int]
    ) -> None:
        """**Validates: Requirements 4.3**

        Generate random word-level confidence values (0-100 as Tesseract produces)
        and verify the computed OCR confidence is always a float in [0.0, 1.0].
        """
        # Build fake Tesseract image_to_data output with the generated confidences
        words = [
            (f"word{i}", conf, i * 50, 10, 40, 15)
            for i, conf in enumerate(word_confs)
        ]
        # Also include some non-word elements (conf=-1) to test filtering
        words.append(("", -1, 0, 0, 0, 0))

        tesseract_data = _make_tesseract_data(words)

        with patch(
            "pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data",
            return_value=tesseract_data,
        ):
            engine = OCREngine(preprocessing=False)
            result = engine.ocr_page(Image.new("RGB", (800, 100)))

        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    @given(
        word_confs=st.lists(
            st.integers(min_value=0, max_value=100),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_confidence_equals_expected_mean(
        self, word_confs: list[int]
    ) -> None:
        """**Validates: Requirements 4.3**

        When there are words, the confidence should equal the mean of
        word-level confidences divided by 100, clamped to [0.0, 1.0].
        """
        words = [
            (f"w{i}", conf, i * 50, 10, 40, 15)
            for i, conf in enumerate(word_confs)
        ]
        tesseract_data = _make_tesseract_data(words)

        with patch(
            "pdf_to_llm_converter.ocr_engine.pytesseract.image_to_data",
            return_value=tesseract_data,
        ):
            engine = OCREngine(preprocessing=False)
            result = engine.ocr_page(Image.new("RGB", (800, 100)))

        expected = max(0.0, min(1.0, sum(word_confs) / len(word_confs) / 100.0))
        assert abs(result.confidence - expected) < 1e-9


# Feature: pdf-to-llm-converter, Property 6: Low-confidence OCR triggers warning
# Validates: Requirements 4.4
class TestLowConfidenceWarning:
    """Property test: For any OCR result with confidence below the configured threshold,
    a warning should be logged containing the page number and the confidence score."""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        page_number=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_low_confidence_triggers_warning_with_page_and_score(
        self, confidence: float, threshold: float, page_number: int
    ) -> None:
        """**Validates: Requirements 4.4**

        Generate random confidence scores, thresholds, and page numbers.
        When confidence < threshold, verify a warning is produced containing
        the page number and the confidence score.
        When confidence >= threshold, verify no warning is produced.

        Tests the warning logic in PDFProcessor.process() which checks OCR
        confidence against the configured threshold and logs warnings.
        """
        import logging

        from pdf_to_llm_converter.models import (
            ExtractedContent,
            OCRResult,
            PageClassification,
            PageRange,
            ProcessingConfig,
        )
        from pdf_to_llm_converter.pdf_processor import PDFProcessor

        # Build a processor with mocked components so we exercise the real
        # warning logic without needing an actual PDF file.
        processor = PDFProcessor.__new__(PDFProcessor)

        config = ProcessingConfig(ocr_threshold=threshold, chunk_size=100)

        # page_number is 1-indexed; internally PDFProcessor uses 0-indexed page_num
        # and formats the warning as page_num + 1.
        page_idx = page_number - 1

        # Mock chunk_manager to yield a single chunk covering our page
        mock_chunk_mgr = MagicMock()
        mock_chunk_mgr.iter_chunks.return_value = [PageRange(start=page_idx, end=page_idx + 1)]
        processor.chunk_manager = mock_chunk_mgr

        # Mock page_classifier to return SCANNED (triggers OCR path)
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = PageClassification.SCANNED
        processor.page_classifier = mock_classifier

        # Mock text_extractor (not used for SCANNED, but set it)
        processor.text_extractor = MagicMock()

        # Mock content_merger
        processor.content_merger = MagicMock()

        # Mock OCR engine to return the generated confidence
        mock_ocr = MagicMock()
        ocr_result = OCRResult(text="test", confidence=confidence, blocks=[])
        mock_ocr.ocr_page.return_value = ocr_result
        processor.ocr_engine = mock_ocr

        # Mock fitz.open to return a fake document with one page
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__len__ = MagicMock(return_value=page_number)
        mock_doc.close = MagicMock()

        # Capture logger warnings
        proc_logger = logging.getLogger("pdf_to_llm_converter.pdf_processor")

        with (
            patch("pdf_to_llm_converter.pdf_processor.fitz.open", return_value=mock_doc),
            patch("pdf_to_llm_converter.pdf_processor.os.path.exists", return_value=True),
            patch("pdf_to_llm_converter.pdf_processor._render_page_to_image", return_value=Image.new("RGB", (100, 100))),
            patch.object(proc_logger, "warning", wraps=proc_logger.warning) as mock_log_warning,
        ):
            document, summary = processor.process("fake.pdf", config)

        if confidence < threshold:
            # A warning MUST have been produced
            warning_msgs = [w for w in summary.warnings if "Low OCR confidence" in w]
            assert len(warning_msgs) >= 1, (
                f"Expected warning for confidence={confidence:.4f} < threshold={threshold:.4f}"
            )
            warn_msg = warning_msgs[0]
            # Warning must contain the page number (1-indexed)
            assert str(page_number) in warn_msg
            # Warning must contain the confidence score
            assert f"{confidence:.2f}" in warn_msg
            # Logger.warning must have been called
            assert mock_log_warning.call_count >= 1
        else:
            # No low-confidence warning should be produced
            warning_msgs = [w for w in summary.warnings if "Low OCR confidence" in w]
            assert len(warning_msgs) == 0, (
                f"Unexpected warning for confidence={confidence:.4f} >= threshold={threshold:.4f}"
            )

