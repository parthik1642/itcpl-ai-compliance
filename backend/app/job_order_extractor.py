import re


def detect_required_tests(text: str) -> list:
    # Remove spaces/newlines so broken PDF words still match.
    compact = re.sub(r"\s+", "", text.upper())

    tests = []

    if "SPECTROCHEMICAL" in compact:
        tests.append("chemical_test_report")

    if "IMPACTTEST" in compact:
        tests.append("impact_test_report")

    if "TENSILETEST" in compact:
        tests.append("tensile_test_report")

    if "HARDNESSTEST" in compact:
        tests.append("hardness_test_report")

    if "MICROSTRUCTUREEXAMINATION" in compact:
        tests.append("microstructure_test_report")

    if "MACROEXAMINATION" in compact:
        tests.append("macro_test_report")

    if (
        "PROOFLOADTEST" in compact
        or "NUTPROOFLOADTEST" in compact
    ):
        tests.append("proof_load_test_report")

    return list(dict.fromkeys(tests))


def extract_job_order(text: str) -> dict:

    result = {
        "job_order_no": None,
        "collection_no": None,
        "labs": []
    }

    # Job Order number
    match = re.search(
        r"Job Order\s*\n?\s*([A-Za-z0-9\/\-]+)",
        text,
        re.IGNORECASE
    )

    if match:
        result["job_order_no"] = match.group(1).strip()

    # Collection number
    match = re.search(
        r"Collection No\.?\s*([0-9\-]+)",
        text,
        re.IGNORECASE
    )

    if match:
        result["collection_no"] = match.group(1).strip()

    # Actual Lab Numbers only
    lab_matches = list(
        re.finditer(
            r"(26-02\d{4})",
            text
        )
    )

    previous_end = 0

    for match in lab_matches:

        lab_no = match.group(1)

        # IMPORTANT:
        # In this Job Order PDF, the row information appears
        # before the Lab Number in extracted text.
        block = text[previous_end:match.start()]

        required_tests = detect_required_tests(block)

        # Sample nature
        sample_nature = None

        if re.search(r"Round Bar", block, re.IGNORECASE):
            sample_nature = "Round Bar"

        elif re.search(r"Hex Nut", block, re.IGNORECASE):
            sample_nature = "Hex Nut"

        elif re.search(r"\bStud\b", block, re.IGNORECASE):
            sample_nature = "Stud"

        # Heat Number
        heat_no = None

        heat_match = re.search(
            r"Heat No\.?\s*:?\s*([A-Za-z0-9\-]+)",
            block,
            re.IGNORECASE
        )

        if heat_match:
            heat_no = heat_match.group(1).strip()

        result["labs"].append({
            "lab_no": lab_no,
            "sample_nature": sample_nature,
            "heat_no": heat_no,
            "required_tests": required_tests
        })

        previous_end = match.end()

    return result