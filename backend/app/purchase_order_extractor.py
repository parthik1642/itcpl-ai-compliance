import re


def normalize_ocr_text(text: str) -> str:
    """
    Clean common OCR mistakes without changing
    the meaning of the document.
    """

    cleaned = text.upper()

    # Common OCR mistakes seen in these PO documents
    replacements = {
        "SSf F": "SSFF",
        "SSfF": "SSFF",
        "55FF": "SSFF",
        "S5FF": "SSFF",
        "SSl:F": "SSFF",
        "SSI:F": "SSFF",
        "'": "",
        "\"": ""
    }

    for old, new in replacements.items():
        cleaned = cleaned.replace(
            old.upper(),
            new
        )

    return cleaned


def extract_purchase_order(text: str) -> dict:

    cleaned = normalize_ocr_text(text)

    result = {
        "po_no": None,
        "heat_numbers": [],
        "impact_temperature_c": None,
        "required_tests": []
    }

    # ---------------------------------
    # PO NUMBER
    # ---------------------------------

    # Look specifically for numbers that
    # resemble the Petro Valves PO format.
    po_patterns = [
        r"P\.?\s*O\.?\s*(?:NO\.?)?\s*[:\-]?\s*(\d{6,}(?:\/[A-Z0-9]+)?)",
        r"PURCHASE\s+ORDER.*?(\d{6,}(?:\/[A-Z0-9]+)?)",
        r"\b(2526\d{3,}(?:\/[A-Z0-9]+)?)\b"
    ]

    for pattern in po_patterns:

        match = re.search(
            pattern,
            cleaned,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            result["po_no"] = match.group(1)
            break

    # ---------------------------------
    # HEAT NUMBERS
    # ---------------------------------

    # More tolerant matching for SSFF numbers
    raw_heat_numbers = re.findall(
        r"\b(?:SSFF|S5FF|55FF|SSF[F\s]*)[\s\-]*"
        r"([0-9O]{4})\b",
        cleaned,
        re.IGNORECASE
    )

    heat_numbers = []

    for number in raw_heat_numbers:

        # OCR sometimes reads zero as letter O
        number = number.replace("O", "0")

        heat_no = f"SSFF-{number}"

        if heat_no not in heat_numbers:
            heat_numbers.append(
                heat_no
            )

    result["heat_numbers"] = heat_numbers

    # ---------------------------------
    # IMPACT TEMPERATURE
    # ---------------------------------

    # Look only near words such as IMPACT / TEST.
    temperature_patterns = [
        r"IMPACT.{0,80}?(-\s*29)\s*°?\s*C",
        r"TEST.{0,50}?(-\s*29)\s*°?\s*C",
        r"(-\s*29)\s*°?\s*C"
    ]

    for pattern in temperature_patterns:

        match = re.search(
            pattern,
            cleaned,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            value = match.group(1)

            value = value.replace(
                " ",
                ""
            )

            result["impact_temperature_c"] = int(
                value
            )

            break

    # ---------------------------------
    # REQUIRED TESTS
    # ---------------------------------

    compact = re.sub(
        r"\s+",
        "",
        cleaned
    )

    if (
        "IMPACT" in compact
        or "ASTMA370" in compact
    ):
        result["required_tests"].append(
            "impact_test_report"
        )

    if (
        "SPECTRO" in compact
        or "CHEMICAL" in compact
    ):
        result["required_tests"].append(
            "chemical_test_report"
        )

    if "MACRO" in compact:
        result["required_tests"].append(
            "macro_test_report"
        )

    if (
        "MICRO" in compact
        or "MICROSTRUCTURE" in compact
    ):
        result["required_tests"].append(
            "microstructure_test_report"
        )

    result["required_tests"] = list(
        dict.fromkeys(
            result["required_tests"]
        )
    )

    return result