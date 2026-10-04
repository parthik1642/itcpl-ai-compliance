import re


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").upper())


def detect_test_report_types(text: str) -> list[str]:
    text_upper = (text or "").upper()
    compact = _compact(text)

    detected = []

    checks = [
        (
            "chemical_test_report",
            [
                "SPECTROCHEMICALANALYSIS",
                "SPECTROCHEMICAL",
                "CHEMICALANALYSIS",
                "SPECTROANALYSIS",
            ],
        ),
        (
            "impact_test_report",
            [
                "IMPACTTEST",
                "CHARPYIMPACT",
                "CHARPYVNOTCH",
            ],
        ),
        (
            "tensile_test_report",
            [
                "FULLTENSILETEST",
                "FULLTENSILE",
                "TENSILETEST",
                "ULTIMATETENSILELOAD",
                "ULTIMATETENSILESTRENGTH",
            ],
        ),
        (
            "bend_test_report",
            [
                "BENDTEST",
                "SIDEBEND",
                "ROOTBEND",
                "FACEBEND",
            ],
        ),
        (
            "hardness_test_report",
            [
                "HARDNESSTEST",
                "HARDNESSSURVEY",
                "ROCKWELLHARDNESS",
                "VICKERSHARDNESS",
                "HRC",
                "HRB",
                "HV10",
            ],
        ),
        (
            "proof_load_test_report",
            [
                "NUTPROOFLOADTEST",
                "NUTPROOFLOAD",
                "PROOFLOADTEST",
            ],
        ),
        (
            "microstructure_test_report",
            [
                "MICROSTRUCTUREEXAMINATION",
                "MICROSTRUCTURETEST",
            ],
        ),
        (
            "macro_test_report",
            [
                "MACROEXAMINATION",
                "MACROTEST",
            ],
        ),
        (
            "ferrite_test_report",
            [
                "FERRITECONTENT",
                "FERRITOSCOPE",
                "ASTME562",
            ],
        ),
        (
            "corrosion_test_report",
            [
                "FERRICCHLORIDECORROSION",
                "PITTINGRESISTANCE",
                "ASTMG48",
                "ASTMA923",
            ],
        ),
    ]

    has_report_marker = (
        "TEST REPORT" in text_upper
        or "TESTREPORT" in compact
        or "LAB NO" in text_upper
        or "LABNO" in compact
        or "TEST NAME" in text_upper
        or "TESTNAME" in compact
    )

    for document_type, markers in checks:
        marker_found = any(
            marker in compact
            for marker in markers
        )

        if marker_found and has_report_marker:
            detected.append(document_type)

    return list(dict.fromkeys(detected))


def classify_document(text: str) -> str:
    text_upper = (text or "").upper()
    compact = _compact(text)

    if (
        "PURCHASE ORDER" in text_upper
        or "PURCHASEORDER" in compact
    ):
        return "purchase_order"

    if (
        "JOB ORDER" in text_upper
        or "JOBORDER" in compact
    ):
        return "job_order"

    test_types = detect_test_report_types(text)

    if test_types:
        return test_types[0]

    if (
        "TEST REPORT" in text_upper
        or "TESTREPORT" in compact
    ):
        return "test_report"

    return "unknown"