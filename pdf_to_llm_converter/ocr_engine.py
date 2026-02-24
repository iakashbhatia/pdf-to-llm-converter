"""OCR engine for scanned pages and embedded images."""

from __future__ import annotations

import logging

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from pdf_to_llm_converter.models import OCRResult, TextBlock

logger = logging.getLogger(__name__)


class OCREngine:
    """Performs OCR on page images and embedded images with optional preprocessing."""

    def __init__(self, preprocessing: bool = True) -> None:
        self.preprocessing = preprocessing

    def _preprocess(self, image: Image.Image) -> Image.Image:
        """Apply preprocessing pipeline: grayscale, deskew, contrast, noise reduction."""
        # 1. Convert to grayscale
        img = image.convert("L")

        # 2. Deskew via pytesseract OSD angle detection
        try:
            osd = pytesseract.image_to_osd(img)
            angle = 0
            for line in osd.splitlines():
                if line.startswith("Rotate:"):
                    angle = int(line.split(":")[1].strip())
                    break
            if angle != 0:
                img = img.rotate(-angle, expand=True, fillcolor=255)
        except pytesseract.TesseractError:
            logger.debug("OSD detection failed, skipping deskew")

        # 3. Contrast enhancement (adaptive histogram equalization)
        img = ImageOps.autocontrast(img)

        # 4. Noise reduction (median filter)
        img = img.filter(ImageFilter.MedianFilter(size=3))

        return img

    def _run_ocr(self, image: Image.Image) -> OCRResult:
        """Run Tesseract OCR on an image and return structured results."""
        if self.preprocessing:
            image = self._preprocess(image)

        # Get word-level data with confidence scores
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        # Build text blocks and collect confidences
        blocks: list[TextBlock] = []
        word_confidences: list[float] = []
        full_text_parts: list[str] = []

        n_items = len(data["text"])
        for i in range(n_items):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])

            # Skip non-word elements (confidence == -1) and empty text
            if conf == -1 or not text:
                continue

            word_confidences.append(conf)
            full_text_parts.append(text)

            x = float(data["left"][i])
            y = float(data["top"][i])
            w = float(data["width"][i])
            h = float(data["height"][i])

            blocks.append(
                TextBlock(
                    text=text,
                    bbox=(x, y, x + w, y + h),
                    block_type="paragraph",
                )
            )

        full_text = " ".join(full_text_parts)

        # Compute mean confidence (0.0-1.0 scale)
        if word_confidences:
            confidence = sum(word_confidences) / len(word_confidences) / 100.0
        else:
            confidence = 0.0

        # Clamp to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        return OCRResult(text=full_text, confidence=confidence, blocks=blocks)

    def ocr_page(self, page_image: Image.Image) -> OCRResult:
        """Run OCR on a page image with optional preprocessing."""
        return self._run_ocr(page_image)

    def ocr_embedded_image(self, image: Image.Image) -> OCRResult:
        """Run OCR on an embedded image (stamp, annotation)."""
        return self._run_ocr(image)
