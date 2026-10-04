import io
import os

import pymupdf
import pytesseract
from PIL import Image

# 1.4 is a good speed/accuracy balance for the supplied ITCPL scans.
OCR_ZOOM = float(os.getenv("OCR_ZOOM", "1.4"))
MIN_TEXT_LENGTH = 40


def _has_usable_text(text: str) -> bool:
    if not text:
        return False
    cleaned = " ".join(text.split())
    if len(cleaned) < MIN_TEXT_LENGTH:
        return False
    useful_chars = sum(char.isalnum() for char in cleaned)
    return useful_chars >= 20


def _ocr_page(page) -> str:
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(OCR_ZOOM, OCR_ZOOM),
        alpha=False,
    )
    image = Image.open(io.BytesIO(pix.tobytes("jpeg"))).convert("L")
    return pytesseract.image_to_string(image, config="--psm 6")


def extract_text_from_pdf(file_path: str) -> dict:
    document = pymupdf.open(file_path)
    pages = []
    used_ocr = False
    try:
        for page_number, page in enumerate(document):
            page_text = page.get_text("text") or ""
            method = "normal"
            if not _has_usable_text(page_text):
                print(
                    f"Page {page_number + 1}: scanned/weak text detected. "
                    "Running fast OCR..."
                )
                try:
                    page_text = _ocr_page(page)
                    method = "ocr"
                    used_ocr = True
                except Exception as exc:
                    print(f"OCR failed on page {page_number + 1}: {exc}")
                    method = "normal"
            else:
                print(f"Page {page_number + 1}: using embedded PDF text.")
            pages.append({
                "page_number": page_number + 1,
                "method": method,
                "text": page_text or "",
            })
    finally:
        document.close()
    return {
        "extraction_method": "ocr" if used_ocr else "normal",
        "total_pages": len(pages),
        "pages": pages,
    }
