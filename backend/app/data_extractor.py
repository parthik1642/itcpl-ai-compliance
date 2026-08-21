import re


def extract_common_fields(text: str) -> dict:

    data = {
        "report_no": None,
        "lab_no": None,
        "po_no": None,
        "customer": None,
        "specification": None,
        "heat_no": None,
        "test_name": None,
        "test_method": None
    }

    # Report Number
    match = re.search(
        r"Report No\.\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["report_no"] = match.group(1).strip()

    # Lab Number
    match = re.search(
        r"Lab No\.\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["lab_no"] = match.group(1).strip()

    # PO Number
    match = re.search(
        r"P\.?O\.?\.?\s*NO\.?\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["po_no"] = match.group(1).strip()

    # Customer
    match = re.search(
        r"Customer Name\s*&?\s*(.+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["customer"] = match.group(1).strip()

    # Specification
    match = re.search(
        r"Specification\s+(.+?)(?:Test Location|\n)",
        text,
        re.IGNORECASE
    )
    if match:
        data["specification"] = match.group(1).strip()

    # Heat Number
    match = re.search(
        r"Heat No\.?\s*:?\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["heat_no"] = match.group(1).strip()

    # Test Name
    match = re.search(
        r"Test Name\s*:\s*(.+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["test_name"] = match.group(1).strip()

    # Test Method
    match = re.search(
        r"Test Method\s*:\s*(.+)",
        text,
        re.IGNORECASE
    )
    if match:
        data["test_method"] = match.group(1).strip()

    return data