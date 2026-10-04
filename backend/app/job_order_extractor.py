import re


def _clean(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def detect_required_tests(text: str) -> list:
    compact = re.sub(r"\s+", "", (text or "").upper())
    tests = []

    if (
        "SPECTROCHEMICAL" in compact
        or "CHEMICALANALYSIS" in compact
        or "SPECTROANALYSIS" in compact
        or ("SPECTRO" in compact and "CHEMICAL" in compact)
    ):
        tests.append("chemical_test_report")

    if "IMPACTTEST" in compact or "CHARPYIMPACT" in compact or "CHARPYVNOTCH" in compact:
        tests.append("impact_test_report")

    if (
        "FULLTENSILETEST" in compact
        or "FULLTENSILE" in compact
        or "TENSILETEST" in compact
    ):
        tests.append("tensile_test_report")

    if (
        "BENDTEST" in compact
        or "SIDEBEND" in compact
        or "ROOTBEND" in compact
        or "FACEBEND" in compact
    ):
        tests.append("bend_test_report")

    if (
        "HARDNESSSURVEY" in compact
        or "HARDNESSTEST" in compact
        or "BRINELL" in compact
        or "VICKERS" in compact
        or "HV10" in compact
        or "BHN" in compact
    ):
        tests.append("hardness_test_report")

    if (
        "MICROSTRUCTUREEXAMINATION" in compact
        or "MICROSTRUCTURETEST" in compact
    ):
        tests.append("microstructure_test_report")

    if "MACROEXAMINATION" in compact or "MACROTEST" in compact:
        tests.append("macro_test_report")

    if "PROOFLOAD" in compact:
        tests.append("proof_load_test_report")

    if "FERRITECONTENT" in compact or "FERRITOSCOPE" in compact or "ASTME562" in compact:
        tests.append("ferrite_test_report")

    if (
        "FERRICCHLORIDECORROSION" in compact
        or "PITTINGRESISTANCE" in compact
        or "ASTMG48" in compact
        or "ASTMA923" in compact
    ):
        tests.append("corrosion_test_report")

    return list(dict.fromkeys(tests))


def _extract_sample_nature(block: str):
    tail = (block or "")[-350:]
    checks = [
        (r"Heavy\s*Hex\s*Bolt", "Heavy Hex Bolt"),
        (r"Heavy\s*Hex\s*Nut", "Heavy Hex Nut"),
        (r"Plain\s*Washer", "Plain Washer"),
        (r"Welded\s*Plate(?:\s*\(After\s*PWHT\))?", "Welded Plate (After PWHT)"),
        (r"Round\s*Bar", "Round Bar"),
        (r"\bStud\b", "Stud"),
        (r"\bPlate\b", "Plate"),
    ]
    found = []
    for pattern, label in checks:
        for match in re.finditer(pattern, tail, re.IGNORECASE):
            found.append((match.start(), label))
    return max(found, key=lambda item: item[0])[1] if found else None


def _extract_heat_no(block: str):
    patterns = [
        r"Heat\s*No\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9./\-]*)",
        r"\bH\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9./\-]*)",
    ]
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, block or "", re.IGNORECASE):
            found.append((match.start(), match.group(1)))
    return _clean(max(found, key=lambda item: item[0])[1]) if found else None


def _extract_collection_no(text: str):
    """Extract Collection No. without confusing it with a Lab No."""
    patterns = [
        r"Collection\s*(?:No\.?|Number)\s*[:\-]?\s*(26\s*[-–—]\s*\d{6})",
        r"Collection\s*(?:No\.?|Number)[\s\S]{0,80}?\b(26\s*[-–—]\s*\d{6})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return re.sub(r"\s*[-–—]\s*", "-", match.group(1))
    return None


def extract_job_order(text: str) -> dict:
    text = text or ""
    result = {
        "job_order_no": None,
        "collection_no": _extract_collection_no(text),
        "labs": [],
    }

    job_match = re.search(
        r"Job\s*Order\s*(?:No\.?|Number)\s*[:\-]\s*([A-Za-z0-9/\-]+)",
        text,
        re.IGNORECASE,
    )
    if job_match:
        candidate = _clean(job_match.group(1))
        if candidate and candidate.upper() != "F/LMS/24":
            result["job_order_no"] = candidate

    all_number_matches = list(
        re.finditer(r"\b(26\s*[-–—]\s*\d{6})\b", text, re.IGNORECASE)
    )

    collection_normalized = result.get("collection_no")
    lab_matches = []
    for candidate in all_number_matches:
        normalized = re.sub(r"\s*[-–—]\s*", "-", candidate.group(1))
        if collection_normalized and normalized == collection_normalized:
            continue

        # Extra protection when the Collection label/value was split oddly by
        # PDF extraction. A number immediately associated with "Collection"
        # is metadata, never a laboratory row.
        context_start = max(0, candidate.start() - 100)
        context = text[context_start:candidate.start()]
        if re.search(r"Collection\s*(?:No\.?|Number)?[^\n\r]{0,50}$", context, re.IGNORECASE):
            if result["collection_no"] is None:
                result["collection_no"] = normalized
                collection_normalized = normalized
            continue

        lab_matches.append(candidate)

    previous_end = 0
    seen = set()

    for match in lab_matches:
        lab_no = re.sub(r"\s*[-–—]\s*", "-", match.group(1))

        if lab_no in seen:
            previous_end = match.end()
            continue

        block = text[previous_end:match.start()]
        required_tests = detect_required_tests(block)
        sample_nature = _extract_sample_nature(block)
        heat_no = _extract_heat_no(block)

        # A Collection number has no sample/test row. If it escaped the label
        # parser, do not create the familiar fake REVIEW row.
        if (
            not required_tests
            and not sample_nature
            and not heat_no
            and re.search(r"Collection", block[-250:], re.IGNORECASE)
        ):
            if result["collection_no"] is None:
                result["collection_no"] = lab_no
            previous_end = match.end()
            continue

        result["labs"].append({
            "lab_no": lab_no,
            "sample_nature": sample_nature,
            "heat_no": heat_no,
            "required_tests": required_tests,
        })

        seen.add(lab_no)
        previous_end = match.end()

        print(
            "JOB ORDER LAB:",
            lab_no,
            "| heat =", heat_no,
            "| sample =", sample_nature,
            "| required =", required_tests,
        )

    return result

