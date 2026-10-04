import re


def _clean(value: str) -> str:
    if not value:
        return ""

    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" :-")


def _unique(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _valid_po_candidate(value: str) -> bool:
    """Reject headings/customer words accidentally captured as a PO number."""
    value = _clean(value)
    if not value:
        return False

    # Real PO/reference identifiers in the supported ITCPL documents contain
    # at least one digit. This prevents OCR text such as
    # "PURCHASE ORDER Petro Valves..." from producing PO No. "Petro".
    if not re.search(r"\d", value):
        return False

    if len(value) < 3 or len(value) > 60:
        return False

    return True


def _extract_customer_name(text: str):
    patterns = [
        r"(?:CUSTOMER|CLIENT|COMPANY)\s*(?:NAME)?\s*[:\-]\s*([^\n]+)",
        r"CUSTOMER\s+NAME\s*&?\s*(?:ADDRESS)?\s*\n+\s*([^\n]+)",
        r"(?:M/S\.?|M/S)\s*[:\-]?\s*([^\n]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = _clean(match.group(1))
            if value:
                return value

    # Client requirement / offer / testing memo documents often have the
    # customer's legal name as a letterhead rather than a "Customer:" field.
    legal_entity = re.compile(
        r"^\s*([A-Z][A-Z0-9&.,()/'\- ]{3,}"
        r"(?:PRIVATE\s+LIMITED|PVT\.?\s+LTD\.?|LIMITED|LTD\.?))\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    ignored = (
        "INDUSTRIAL TESTING CENTER",
        "ITCPL",
    )

    for match in legal_entity.finditer(text):
        value = _clean(match.group(1))
        if not value:
            continue
        if any(item in value.upper() for item in ignored):
            continue
        return value

    return None


def extract_purchase_order(text: str) -> dict:
    text = text or ""
    upper = text.upper()

    data = {
        "po_no": None,
        "po_numbers": [],
        "reference_number": None,
        "customer_name": None,
        "heat_number": None,
        "heat_numbers": [],
        "plate_number": None,
        "identification": None,
        "welder_number": None,
        "material_grade": None,
        "specification": None,
        "required_tests": [],
        "warnings": [],
    }

    # ========================================================
    # PO NUMBERS
    # ========================================================

    po_patterns = [
        r"P\.?\s*O\.?\s*(?:NO|NUMBER)\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]+)",
        r"PURCHASE\s*ORDER\s*(?:NO|NUMBER)?\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]+)",
    ]

    po_numbers = []

    for pattern in po_patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            value = _clean(match)
            if _valid_po_candidate(value):
                po_numbers.append(value)

    if not po_numbers:
        match = re.search(
            r"PURCHASE\s+ORD(?:ER|TR)[\s\S]{0,120}?[-:\s]+([0-9]{6,}(?:/[0-9A-Z]+)?)",
            text,
            re.IGNORECASE,
        )
        if match:
            value = _clean(match.group(1))
            if _valid_po_candidate(value):
                po_numbers.append(value)

    data["po_numbers"] = _unique(po_numbers)

    if data["po_numbers"]:
        data["po_no"] = data["po_numbers"][0]
        data["reference_number"] = data["po_numbers"][0]
    else:
        data["warnings"].append(
            "PO number could not be confidently extracted. This does not block analysis."
        )

    # ========================================================
    # REFERENCE NUMBER
    # ========================================================

    reference_match = re.search(
        r"(?:REFERENCE|REF\.?)\s*(?:NO|NUMBER)?\.?\s*[:\-]\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if reference_match:
        data["reference_number"] = _clean(reference_match.group(1))

    # ========================================================
    # CUSTOMER
    # ========================================================

    data["customer_name"] = _extract_customer_name(text)

    # ========================================================
    # HEAT NUMBERS
    # ========================================================

    heat_patterns = [
        r"HEAT\s*(?:NO|NUMBER)\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9.\-/]*)",
        r"\bH\s*[:\-]\s*([A-Z0-9][A-Z0-9.\-/]*)",
        r"\bSSFF[\s\-]*([0-9O]{4})\b",
    ]

    heats = []

    for pattern in heat_patterns:
        for value in re.findall(pattern, text, re.IGNORECASE):
            value = _clean(value).upper()

            if re.fullmatch(r"[0-9O]{4}", value):
                value = f"SSFF-{value.replace('O', '0')}"

            if value:
                heats.append(value)

    data["heat_numbers"] = _unique(heats)

    if data["heat_numbers"]:
        data["heat_number"] = data["heat_numbers"][0]

    # ========================================================
    # PLATE NUMBER
    # ========================================================

    plate_match = re.search(
        r"PLATE\s*(?:NO|NUMBER)\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9.\-/]*)",
        text,
        re.IGNORECASE,
    )
    if plate_match:
        data["plate_number"] = _clean(plate_match.group(1)).upper()

    # ========================================================
    # MATERIAL GRADE
    # ========================================================

    material_match = re.search(
        r"(?:MATERIAL\s*GRADE|GRADE)\s*[:\-]?\s*([A-Z0-9+\-]+)",
        text,
        re.IGNORECASE,
    )
    if material_match:
        data["material_grade"] = _clean(material_match.group(1))

    # ========================================================
    # SPECIFICATION
    # ========================================================

    specification_patterns = [
        r"\bASME\s+BPVC\s+SEC(?:TION)?\.?\s*[IVX]+\s+[A-Z]?\s*SA\s*\d+(?:\s+GRADE\s+[A-Z0-9]+)?",
        r"\bSA\s*516\s+GR(?:ADE)?\.?\s*70N?\b",
        r"\bASTM\s+A193(?:/A193M)?(?::\d{4})?(?:\s+GRADE\s+[A-Z0-9]+)?",
        r"\bASTM\s+A194(?:/A194M)?(?::\d{4})?(?:\s+GRADE\s+[A-Z0-9]+)?",
        r"\bASTM\s+A182(?:/A182M)?(?::\d{4})?",
        r"\bASTM\s+A370(?::\d{4})?",
        r"\bEN\s*10025[\-\s]*2(?::\d{4})?",
    ]

    for pattern in specification_patterns:
        match = re.search(pattern, upper, re.IGNORECASE)
        if match:
            data["specification"] = _clean(match.group(0))
            break

    # ========================================================
    # REQUIRED TESTS
    # ========================================================

    compact = re.sub(r"\s+", "", upper)
    required_tests = []

    checks = [
        ("chemical_test_report", ["CHEMICAL", "SPECTRO"]),
        ("impact_test_report", ["IMPACT", "CHARPY"]),
        ("tensile_test_report", ["TENSILE"]),
        ("hardness_test_report", ["HARDNESS", "VICKERS", "ROCKWELL", "BRINELL", "HV10", "BHN"]),
        ("proof_load_test_report", ["PROOFLOAD", "NUTPROOF"]),
        ("macro_test_report", ["MACROEXAMINATION", "MACROTEST"]),
        ("microstructure_test_report", ["MICROSTRUCTURE", "MICROSTRUCTUREEXAMINATION"]),
        ("bend_test_report", ["BENDTEST", "SIDEBEND", "ROOTBEND", "FACEBEND", "BENDINGTEST"]),
    ]

    for test_name, markers in checks:
        if any(marker.replace(" ", "") in compact for marker in markers):
            required_tests.append(test_name)

    data["required_tests"] = _unique(required_tests)

    return data
