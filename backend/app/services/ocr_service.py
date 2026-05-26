import io
import logging
from typing import Optional
import pdfplumber
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

def extract_text_from_pdf_native(file_bytes: bytes) -> str:
    """Extract embedded text from a PDF using pdfplumber."""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = " ".join(p.extract_text() or "" for p in pdf.pages)
        return text.strip()
    except Exception as e:
        logger.warning(f"pdfplumber native extraction failed: {e}")
        return ""


def extract_text_from_pdf_ocr(file_bytes: bytes) -> str:
    """Convert PDF to images and extract text using Tesseract OCR with preprocessing."""
    try:
        images = convert_from_bytes(file_bytes, dpi=300)
        text_parts = []
        for img in images:
            processed = _preprocess_image(img)
            text = pytesseract.image_to_string(processed)
            text_parts.append(text)
        return "\n".join(text_parts).strip()
    except Exception as e:
        logger.error(f"pdf2image/pytesseract OCR failed: {e}")
        return ""


def extract_text_from_image(file_bytes: bytes) -> str:
    """Extract text from an image (png, jpeg) using Tesseract OCR with preprocessing."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        processed = _preprocess_image(img)
        text = pytesseract.image_to_string(processed)
        return text.strip()
    except Exception as e:
        logger.error(f"pytesseract image extraction failed: {e}")
        return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Intelligently extract text from a document.
    
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
        
        # If the text is very short, it's likely a scanned PDF image wrapper
        if len(text) < 100:
            logger.info(f"Native extraction yielded <100 chars for {filename}. Falling back to OCR.")
            ocr_text = extract_text_from_pdf_ocr(file_bytes)
            # Combine whatever little text we got with the OCR text
            return text + "\n" + ocr_text
            
        return text
        
    logger.warning(f"Unsupported file type for OCR: {ext}")
    return ""
