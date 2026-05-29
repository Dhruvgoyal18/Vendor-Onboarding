import io
import logging
from typing import Optional
import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)


def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocess an image before Tesseract OCR.
    Grayscale → contrast boost → sharpen → binarize.
    Improves Tesseract accuracy by 20-30% on document photos and low-quality scans.
    """
    img = img.convert("L")                              # grayscale
    img = ImageEnhance.Contrast(img).enhance(2.0)       # boost contrast
    img = img.filter(ImageFilter.SHARPEN)               # sharpen edges
    img = img.point(lambda x: 0 if x < 128 else 255)   # binarize (threshold)
    return img


def _tesseract_confidence(img: Image.Image) -> float:
    """Return average word-level confidence (0–1) from Tesseract for a preprocessed image."""
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confs = [c for c in data["conf"] if c > 0]  # -1 = non-text block
    return round(sum(confs) / len(confs) / 100, 3) if confs else 0.0


def extract_text_from_pdf_native(file_bytes: bytes) -> str:
    """Extract embedded text from a PDF using pdfplumber."""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = " ".join(p.extract_text() or "" for p in pdf.pages)
        return text.strip()
    except Exception as e:
        logger.warning(f"pdfplumber native extraction failed: {e}")
        return ""


def extract_text_from_pdf_ocr(file_bytes: bytes) -> tuple[str, float]:
    """Convert PDF to images and extract text + OCR confidence using Tesseract."""
    try:
        images = convert_from_bytes(file_bytes, dpi=300)
        text_parts = []
        all_confs: list[float] = []
        for img in images:
            processed = _preprocess_image(img)
            text_parts.append(pytesseract.image_to_string(processed))
            data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
            all_confs.extend(c for c in data["conf"] if c > 0)
        text = "\n".join(text_parts).strip()
        confidence = round(sum(all_confs) / len(all_confs) / 100, 3) if all_confs else 0.0
        return text, confidence
    except Exception as e:
        logger.error(f"pdf2image/pytesseract OCR failed: {e}")
        return "", 0.0


def extract_text_from_image(file_bytes: bytes) -> tuple[str, float]:
    """Extract text + OCR confidence from an image (png, jpeg) using Tesseract."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        processed = _preprocess_image(img)
        text = pytesseract.image_to_string(processed)
        confidence = _tesseract_confidence(processed)
        return text.strip(), confidence
    except Exception as e:
        logger.error(f"pytesseract image extraction failed: {e}")
        return "", 0.0


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, float]:
    """
    Intelligently extract text + OCR confidence from a document.

    Returns (text, ocr_confidence) where ocr_confidence is:
      - Tesseract word-level average (0–1) for images and scanned PDFs
      - 1.0 for native-text PDFs (embedded text is fully trusted)
      - 0.0 on failure

    Strategy:
    1. If image, run OCR directly.
    2. If PDF, try native extraction (pdfplumber) first.
    3. If native extraction yields very little text (likely a scanned PDF),
       fallback to full OCR (pdf2image + pytesseract).
    """
    ext = filename.lower().rsplit(".", 1)[-1]

    if ext in ("jpg", "jpeg", "png"):
        logger.info(f"Extracting text from image {filename} using OCR")
        return extract_text_from_image(file_bytes)

    if ext == "pdf":
        logger.info(f"Attempting native text extraction for {filename}")
        text = extract_text_from_pdf_native(file_bytes)

        if len(text) < 100:
            logger.info(f"Native extraction yielded <100 chars for {filename}. Falling back to OCR.")
            ocr_text, ocr_conf = extract_text_from_pdf_ocr(file_bytes)
            return text + "\n" + ocr_text, ocr_conf

        return text, 1.0  # native embedded text → fully trusted

    logger.warning(f"Unsupported file type for OCR: {ext}")
    return "", 0.0


def render_document_to_images(file_bytes: bytes, filename: str, max_pages: int = 3) -> list[bytes]:
    """
    Render a document to a list of JPEG image bytes (one per page).
    Uses pypdfium2 for PDFs (no poppler dependency) and PIL for images.
    Returns up to max_pages images. Returns [] on failure.
    """
    ext = filename.lower().rsplit(".", 1)[-1]

    if ext in ("jpg", "jpeg", "png", "webp"):
        try:
            img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return [buf.getvalue()]
        except Exception as e:
            logger.error(f"Failed to read image {filename}: {e}")
            return []

    if ext == "pdf":
        try:
            pdf = pdfium.PdfDocument(file_bytes)
            images = []
            for i, page in enumerate(pdf):
                if i >= max_pages:
                    break
                bitmap = page.render(scale=2.0, rotation=0)  # ~144 DPI
                pil_img = bitmap.to_pil().convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=90)
                images.append(buf.getvalue())
            return images
        except Exception as e:
            logger.error(f"pypdfium2 render failed for {filename}: {e}")
            return []

    logger.warning(f"render_document_to_images: unsupported type .{ext}")
    return []
