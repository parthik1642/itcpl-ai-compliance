import re


def _clean(value):
    if value is None:
        return None

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" :;|,.")

    return value or None


def _normalize_lab_no(value):
    """
    Normalize common OCR variants such as:
      26 - 020656
      26–020656
      26—020656
    into:
      26-020656
    """
    value = _clean(value)

    if not value:
        return None

    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*-\s*", "-", value)

    match = re.search(r"\b(\d{2})-(\d{6})\b", value)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Reject dates/OCR fragments accidentally captured after the Lab No label.
    return None


def _normalize_heat_no(value):
    value = _clean(value)

    if not value:
        return None

    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*-\s*", "-", value)

    return value


def _first_match(patterns, text, flags=re.IGNORECASE):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return _clean(match.group(1))

    return None


def extract_common_fields(text: str) -> dict:
    """
    Extract common report metadata.

    This parser is intentionally tolerant of table extraction and OCR
    variations used in ITCPL reports. In particular, it accepts:

        Lab No. 26-020656
        Lab No : 26-020656
        Lab No: 26 - 020656
        Lab Number 26-020656

    and similar variants for Heat No., PO No., etc.
    """

    text = text or ""

    data = {
        "report_no": None,
        "lab_no": None,
        "po_no": None,
        "customer": None,
        "specification": None,
        "heat_no": None,
        "test_name": None,
        "test_method": None,
    }

    # ---------------------------------------------------------
    # REPORT NUMBER
    # ---------------------------------------------------------
    data["report_no"] = _first_match(
        [
            r"Report\s*No\.?\s*[:\-]?\s*([A-Za-z0-9_./\-]+)",
            r"Report\s*Number\s*[:\-]?\s*([A-Za-z0-9_./\-]+)",
        ],
        text,
    )

    # ---------------------------------------------------------
    # LAB NUMBER
    # ---------------------------------------------------------
    lab_no = _first_match(
        [
            # Normal ITCPL labels.
            r"Lab\s*No\.?\s*[:\-]?\s*(\d{2}\s*[-–—]\s*\d{6})",
            r"Lab\s*Number\s*[:\-]?\s*(\d{2}\s*[-–—]\s*\d{6})",

            # OCR/table extraction may separate the label and value.
            r"Lab\s*No\.?[^\d]{0,20}(\d{2}\s*[-–—]\s*\d{6})",

            # Last-resort: ITCPL Lab No format anywhere on report page.
            r"\b(26\s*[-–—]\s*\d{6})\b",
        ],
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    data["lab_no"] = _normalize_lab_no(lab_no)

    # ---------------------------------------------------------
    # PO NUMBER
    # ---------------------------------------------------------
    data["po_no"] = _first_match(
        [
            r"P\.?\s*O\.?\s*(?:No|Number)\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)",
            r"PO\s*(?:No|Number)\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)",
        ],
        text,
    )

    # ---------------------------------------------------------
    # CUSTOMER
    # ---------------------------------------------------------
    customer = _first_match(
        [
            r"Customer\s*Name\s*(?:&\s*Address)?\s*[:\-]?\s*(?:\r?\n\s*)?([^\n\r]+)",
            r"Customer\s*[:\-]\s*([^\n\r]+)",
        ],
        text,
    )

    data["customer"] = customer

    # ---------------------------------------------------------
    # SPECIFICATION
    # ---------------------------------------------------------
    specification = _first_match(
        [
            r"Specification\s*[:\-]?\s*(.+?)(?=\s+Test\s*Location|\r?\n)",
            r"Specification\s*[:\-]?\s*([^\n\r]+)",
        ],
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    data["specification"] = specification

    # ---------------------------------------------------------
    # HEAT NUMBER
    # ---------------------------------------------------------
    heat_no = _first_match(
        [
            # Standard label.
            r"Heat\s*No\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9_./\-]*)",
            r"Heat\s*Number\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9_./\-]*)",

            # Common Sample Description line:
            # "Round Bar, Heat No. SSFF-8038"
            r"Heat\s*No\.?[^A-Za-z0-9]{0,10}([A-Za-z0-9][A-Za-z0-9_./\-]*)",
        ],
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    data["heat_no"] = _normalize_heat_no(heat_no)

    # ---------------------------------------------------------
    # TEST NAME
    # ---------------------------------------------------------
    data["test_name"] = _first_match(
        [
            r"Test\s*Name\s*[:\-]?\s*([^\n\r]+)",
        ],
        text,
    )

    # ---------------------------------------------------------
    # TEST METHOD
    # ---------------------------------------------------------
    data["test_method"] = _first_match(
        [
            r"Test\s*Method\s*[:\-]?\s*([^\n\r]+)",
        ],
        text,
    )

    return data
