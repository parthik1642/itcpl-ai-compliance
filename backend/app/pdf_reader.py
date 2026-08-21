import pymupdf
import pytesseract
from PIL import Image
import io


def extract_text_from_pdf(file_path: str) -> dict:
    document = pymupdf.open(file_path)

    pages = []
    used_ocr = False

    for page_number, page in enumerate(document):

        # First try normal text
        page_text = page.get_text()

        method = "normal"

        # OCR fallback for scanned page
        if len(page_text.strip()) < 50:
            print(f"Page {page_number + 1}: scanned page detected. Running OCR...")

            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2)
            )

            image = Image.open(
                io.BytesIO(pix.tobytes("png"))
            )

            page_text = pytesseract.image_to_string(image)

            method = "ocr"
            used_ocr = True

        pages.append({
            "page_number": page_number + 1,
            "method": method,
            "text": page_text
        })

    document.close()

    return {
        "extraction_method": "ocr" if used_ocr else "normal",
        "total_pages": len(pages),
        "pages": pages
    }