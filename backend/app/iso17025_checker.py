import re
from typing import Any


# ============================================================
# ISO/IEC 17025:2017 REPORT-LEVEL CHECKER
# ============================================================
#
# IMPORTANT:
# This module performs an automated DOCUMENT / REPORT check,
# focused mainly on ISO/IEC 17025:2017 reporting requirements
# and report-level NABL indicators.
#
# It does NOT certify the laboratory, does NOT prove that a
# particular test is inside the laboratory's current NABL scope,
# and does NOT replace an accreditation assessment.
#
# Status meanings:
#   PASS           -> automated report-level evidence was found
#   REVIEW         -> applicability/evidence requires human verification
#   NOT_APPLICABLE -> conditional requirement does not apply
#   ISSUE          -> a normally expected report item appears missing
#
# ============================================================


REPORT_ID_PATTERNS = [
    r"\bReport\s*No\.?\s*[:\-]?\s*([A-Z0-9\-/]+)",
    r"\bTest\s*Report\s*No\.?\s*[:\-]?\s*([A-Z0-9\-/]+)",
]

LAB_NO_PATTERNS = [
    r"\bLab\s*No\.?\s*[:\-]?\s*([A-Z0-9\-/]+)",
    r"\bLaboratory\s*No\.?\s*[:\-]?\s*([A-Z0-9\-/]+)",
]

REPORT_DATE_PATTERNS = [
    r"\bReport\s*Date\s*[:\-]?\s*([^\n]+)",
    r"\bDate\s*of\s*Report\s*[:\-]?\s*([^\n]+)",
]

TEST_DATE_PATTERNS = [
    r"\bTesting\s*Date\s*[:\-]?\s*([^\n]+)",
    r"\bTest\s*Completed\s*on\s*[:\-]?\s*([^\n]+)",
    r"\bDate\s*of\s*Test\s*[:\-]?\s*([^\n]+)",
]

METHOD_PATTERNS = [
    r"\bTest\s*Method\s*[:\-]?\s*([^\n]+)",
    r"\bMethod\s*[:\-]?\s*((?:ASTM|IS|ISO|EN|BS|DIN|ASME)[^\n]+)",
]

SPEC_PATTERNS = [
    r"\bSpecification\s*[:\-]?\s*([^\n]+)",
    r"\bSpec\.?\s*[:\-]?\s*((?:ASTM|IS|ISO|EN|BS|DIN|ASME)[^\n]+)",
]


# ============================================================
# HELPERS
# ============================================================

def _clean(value: Any):
    if value is None:
        return None

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    return value or None


def _find_first(text: str, patterns: list[str]):
    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:
            return _clean(match.group(1))

    return None


def _contains_any(text: str, phrases: list[str]) -> bool:
    upper = text.upper()
    return any(phrase.upper() in upper for phrase in phrases)


def _find_phrase(text: str, phrases: list[str]):
    for phrase in phrases:
        match = re.search(
            re.escape(phrase),
            text,
            flags=re.IGNORECASE
        )
        if match:
            return _clean(match.group(0))

    return None


def _valid_customer(value: Any) -> bool:
    value = _clean(value)

    if not value:
        return False

    generic = {
        "ADDRESS",
        "NAME",
        "CUSTOMER",
        "CUSTOMER NAME",
        "CUSTOMER NAME & ADDRESS",
        "CUSTOMER NAME AND ADDRESS",
        "CLIENT",
        "CLIENT NAME",
    }

    if value.upper() in generic:
        return False

    if len(value) < 3:
        return False

    return True


def _extract_customer(text: str, extracted_data: dict):
    """
    Avoid false values such as:
        customer = "Address"

    Common ITCPL layout:
        Customer Name &
        Address
        CU-BUILT RENEWABLE ENERGY PVT. LTD.

    or:
        Customer Name & Address
        Petro Valves Private Limited
    """

    candidates = [
        extracted_data.get("customer"),
        extracted_data.get("customer_name"),
    ]

    for candidate in candidates:
        if _valid_customer(candidate):
            return _clean(candidate)

    # Same-line customer value.
    same_line_patterns = [
        r"Customer\s*Name\s*&\s*Address\s*[:\-]\s*([^\n]+)",
        r"Customer\s*Name\s+and\s+Address\s*[:\-]\s*([^\n]+)",
        r"Client\s*Name\s*[:\-]\s*([^\n]+)",
    ]

    for pattern in same_line_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match and _valid_customer(match.group(1)):
            return _clean(match.group(1))

    # Multi-line layout.
    lines = [
        _clean(line)
        for line in text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    for index, line in enumerate(lines):
        upper = line.upper()

        if (
            "CUSTOMER NAME" in upper
            or "CLIENT NAME" in upper
        ):
            # Search the next few lines and skip header words.
            for next_line in lines[index + 1:index + 5]:
                if _valid_customer(next_line):
                    # Skip obvious labels.
                    next_upper = next_line.upper()
                    if next_upper in {
                        "ADDRESS",
                        "CUSTOMER ADDRESS",
                        "NAME & ADDRESS",
                        "NAME AND ADDRESS",
                    }:
                        continue

                    return next_line

    return None


def _laboratory_identity(text: str, extracted_data: dict):
    """
    Detect ITCPL/laboratory identity more reliably.

    ITCPL reports may show the full name, the ITCPL acronym/logo
    text, website/email, or laboratory address in extracted text.
    """

    lab_name = (
        extracted_data.get("laboratory")
        or extracted_data.get("laboratory_name")
        or extracted_data.get("lab_name")
    )

    if lab_name:
        return _clean(lab_name)

    evidence = _find_phrase(
        text,
        [
            "Industrial Testing Center Private Limited",
            "Industrial Testing Centre Private Limited",
            "Industrial Testing Center Pvt. Ltd.",
            "Industrial Testing Centre Pvt. Ltd.",
            "ITCPL",
            "itcplab.com",
            "industrialtestingcenter",
            "industrialtestingcentre",
        ]
    )

    return evidence


def _has_result_content(text: str, test_results: dict | None) -> bool:
    test_results = test_results or {}

    meaningful_keys = [
        "readings",
        "average",
        "elements",
        "results",
        "result",
        "parameters",
        "sample_results",
        "applied_load",
        "required_load",
        "yield_strength",
        "tensile_strength",
        "elongation",
        "reduction_of_area",
        "observation",
        "bend_angle",
    ]

    for key in meaningful_keys:
        value = test_results.get(key)
        if value not in [None, "", [], {}]:
            return True

    return bool(
        re.search(
            r"\b(?:Result|Reading|Average|Parameter|Observation)\b",
            text,
            flags=re.IGNORECASE
        )
    )


def _has_units(text: str, test_results: dict | None) -> tuple[bool, str | None]:
    test_results = test_results or {}

    structured_unit = (
        test_results.get("unit")
        or test_results.get("units")
        or test_results.get("scale")
    )

    if structured_unit:
        return True, _clean(structured_unit)

    # Includes forms such as HV10, HV 10, HRC, MPa, kN, J, mm, °C.
    unit_patterns = [
        r"\bHV\s*\d+(?:\.\d+)?\b",
        r"\bHRC\b",
        r"\bHRB\b",
        r"\bHBW\b",
        r"\bMPa\b",
        r"\bkN\b",
        r"\bN/mm(?:2|²)\b",
        r"\bJ\b",
        r"\bmm\b",
        r"°\s*C\b",
        r"\bdeg(?:ree)?\s*C\b",
        r"%",
    ]

    for pattern in unit_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:
            return True, _clean(match.group(0))

    return False, None


def _has_authorization(text: str) -> tuple[bool, str | None]:
    evidence = _find_phrase(
        text,
        [
            "Authorized by",
            "Authorised by",
            "Authorized Signatory",
            "Authorised Signatory",
            "Digitally signed",
            "Digital signature",
        ]
    )

    return bool(evidence), evidence


def _has_page_identity(text: str) -> bool:
    return bool(
        re.search(
            r"\bPage\s+\d+\s+(?:of|/)\s*\d+\b",
            text,
            flags=re.IGNORECASE
        )
    )


def _has_end_marker(text: str) -> bool:
    return _contains_any(
        text,
        [
            "END OF REPORT",
            "END OF TEST REPORT",
        ]
    )


def _statement_of_conformity(text: str, test_results: dict | None):
    test_results = test_results or {}

    value = (
        test_results.get("reported_conformity")
        or test_results.get("statement_of_conformity")
    )

    if value:
        return _clean(value)

    match = re.search(
        r"Statement\s+of\s+conformity\s*[:\-]?\s*([^\n]+)",
        text,
        flags=re.IGNORECASE
    )

    if match:
        return _clean(match.group(1))

    return None


def _decision_rule_evidence(text: str):
    return _find_phrase(
        text,
        [
            "decision rule",
            "measurement uncertainty is not considered",
            "measurement uncertainty considered",
            "uncertainty is not considered",
            "uncertainty considered",
        ]
    )


def _measurement_uncertainty_evidence(text: str):
    return _find_phrase(
        text,
        [
            "measurement uncertainty",
            "uncertainty of measurement",
            "expanded uncertainty",
        ]
    )


def _nabl_evidence(text: str):
    """
    PASS only when there is explicit accreditation evidence.

    IMPORTANT:
    'Scope & Certificate' alone is NOT enough to prove NABL evidence.
    It may just be a generic report link/QR label.
    """

    strong_phrases = [
        "NABL",
        "National Accreditation Board for Testing and Calibration Laboratories",
        "ISO/IEC 17025",
        "ISO 17025",
        "NABL Accredited",
        "NABL Accreditation",
        "Accreditation No.",
        "Accreditation Number",
    ]

    return _find_phrase(
        text,
        strong_phrases
    )


def _add_check(
    checks: list,
    code: str,
    label: str,
    status: str,
    clause: str,
    detail: str,
    evidence: Any = None,
):
    checks.append({
        "code": code,
        "label": label,
        "status": status,
        "clause": clause,
        "detail": detail,
        "evidence": evidence,
    })


# ============================================================
# MAIN CHECKER
# ============================================================

def check_iso17025_report(
    text: str,
    extracted_data: dict | None = None,
    test_results: dict | None = None,
    document_type: str | None = None,
) -> dict:
    """
    Perform a conservative automated report-level check.

    Technical PASS/FAIL and ISO/NABL report-document checks stay
    completely separate.

    This function NEVER changes the technical test result.
    """

    text = text or ""
    extracted_data = extracted_data or {}
    test_results = test_results or {}

    checks = []

    # --------------------------------------------------------
    # ISO/IEC 17025:2017 - REPORT INFORMATION
    # --------------------------------------------------------

    report_title_present = _contains_any(
        text,
        [
            "TEST REPORT",
            "CALIBRATION CERTIFICATE",
        ]
    )

    _add_check(
        checks,
        "report_title",
        "Report title",
        "PASS" if report_title_present else "ISSUE",
        "7.8.2",
        "The document should be clearly identified as a report/certificate.",
        "TEST REPORT" if report_title_present else None,
    )

    report_no = (
        extracted_data.get("report_no")
        or extracted_data.get("report_number")
        or _find_first(text, REPORT_ID_PATTERNS)
    )

    _add_check(
        checks,
        "unique_report_id",
        "Unique report identification",
        "PASS" if report_no else "ISSUE",
        "7.8.2",
        "A unique report identifier should be present.",
        report_no,
    )

    laboratory = _laboratory_identity(
        text,
        extracted_data
    )

    _add_check(
        checks,
        "laboratory_identity",
        "Laboratory identity",
        "PASS" if laboratory else "ISSUE",
        "7.8.2",
        "The report should identify the laboratory issuing the result.",
        laboratory,
    )

    customer = _extract_customer(
        text,
        extracted_data
    )

    _add_check(
        checks,
        "customer_identification",
        "Customer identification",
        "PASS" if customer else "ISSUE",
        "7.8.2",
        "The report should identify the customer where applicable.",
        customer,
    )

    lab_no = (
        extracted_data.get("lab_no")
        or test_results.get("lab_no")
        or _find_first(text, LAB_NO_PATTERNS)
    )

    _add_check(
        checks,
        "sample_identification",
        "Sample / item identification",
        "PASS" if lab_no else "ISSUE",
        "7.8.2",
        "The tested item/sample should be unambiguously identified.",
        lab_no,
    )

    sample_description_match = re.search(
        r"(?:Sample\s*Description|Nature\s*Of\s*Sample|Nature\s*of\s*Sample)"
        r"\s*[:\-]?\s*([^\n]+)",
        text,
        flags=re.IGNORECASE
    )

    sample_description = (
        _clean(sample_description_match.group(1))
        if sample_description_match
        else None
    )

    sample_description_present = bool(
        sample_description
        or _contains_any(
            text,
            [
                "Sample Description",
                "Nature Of Sample",
                "Nature of Sample",
            ]
        )
    )

    _add_check(
        checks,
        "sample_description",
        "Sample description",
        "PASS" if sample_description_present else "REVIEW",
        "7.8.2",
        "The report should provide an unambiguous description of the tested item where relevant.",
        sample_description,
    )

    method = (
        test_results.get("test_method")
        or extracted_data.get("test_method")
        or _find_first(text, METHOD_PATTERNS)
    )

    _add_check(
        checks,
        "test_method",
        "Test method identification",
        "PASS" if method else "ISSUE",
        "7.8.2 / 7.8.3",
        "The method used for testing should be identified.",
        method,
    )

    specification = (
        test_results.get("specification")
        or extracted_data.get("specification")
        or _find_first(text, SPEC_PATTERNS)
    )

    _add_check(
        checks,
        "specification",
        "Specification / requirement reference",
        "PASS" if specification else "REVIEW",
        "7.8.2 / 7.8.3",
        "Specification/customer requirement identification is checked when applicable.",
        specification,
    )

    report_date = _find_first(
        text,
        REPORT_DATE_PATTERNS
    )

    _add_check(
        checks,
        "report_date",
        "Report issue date",
        "PASS" if report_date else "ISSUE",
        "7.8.2",
        "The date of issue of the report should be identifiable.",
        report_date,
    )

    test_date = _find_first(
        text,
        TEST_DATE_PATTERNS
    )

    _add_check(
        checks,
        "testing_date",
        "Testing / completion date",
        "PASS" if test_date else "REVIEW",
        "7.8.2",
        "The date(s) the laboratory activity was performed should be identifiable when relevant.",
        test_date,
    )

    results_present = _has_result_content(
        text,
        test_results
    )

    _add_check(
        checks,
        "results",
        "Test results present",
        "PASS" if results_present else "ISSUE",
        "7.8.2 / 7.8.3",
        "The report should contain the test result(s).",
        None,
    )

    units_present, unit_evidence = _has_units(
        text,
        test_results
    )

    qualitative_test = document_type in {
        "macro_test_report",
        "microstructure_test_report",
        "macro_report",
        "microstructure_report",
    }

    unit_status = (
        "PASS"
        if units_present
        else (
            "REVIEW"
            if qualitative_test
            else "ISSUE"
        )
    )

    _add_check(
        checks,
        "units",
        "Result units",
        unit_status,
        "7.8.2 / 7.8.3",
        "Results should include appropriate units where applicable.",
        unit_evidence,
    )

    page_identity = _has_page_identity(
        text
    )

    end_marker = _has_end_marker(
        text
    )

    completeness_evidence = (
        "page numbering"
        if page_identity
        else (
            "end marker"
            if end_marker
            else None
        )
    )

    _add_check(
        checks,
        "report_completeness_marker",
        "Page / end-of-report identification",
        "PASS" if (page_identity or end_marker) else "REVIEW",
        "7.8.2",
        "Report pages should support clear identification of report completeness.",
        completeness_evidence,
    )

    authorized, authorization_evidence = _has_authorization(
        text
    )

    _add_check(
        checks,
        "authorization",
        "Authorized report release",
        "PASS" if authorized else "ISSUE",
        "7.8.2",
        "The person(s) authorizing the report should be identifiable.",
        authorization_evidence,
    )

    # --------------------------------------------------------
    # ISO/IEC 17025:2017 - STATEMENT OF CONFORMITY
    # --------------------------------------------------------

    conformity = _statement_of_conformity(text, test_results)

    if conformity:
        _add_check(
            checks, "statement_of_conformity", "Statement of conformity",
            "PASS", "7.8.6",
            "A statement of conformity is present.", conformity,
        )

        decision_rule_evidence = _decision_rule_evidence(text)

        if decision_rule_evidence:
            decision_rule_status = "PASS"
            decision_rule_detail = (
                "Decision-rule or uncertainty-handling evidence is explicitly documented."
            )
            decision_rule_display_evidence = decision_rule_evidence
        elif specification:
            decision_rule_status = "NOT_APPLICABLE"
            decision_rule_detail = (
                "No separate decision-rule wording was detected. The applicable "
                "specification/requirement is identified, so the decision rule may "
                "be inherent in that requested specification/standard."
            )
            decision_rule_display_evidence = specification
        else:
            decision_rule_status = "REVIEW"
            decision_rule_detail = (
                "A conformity statement is present, but neither explicit decision-rule "
                "wording nor a sufficiently identified specification/requirement was detected."
            )
            decision_rule_display_evidence = None

        _add_check(
            checks, "decision_rule", "Decision rule / uncertainty handling",
            decision_rule_status, "7.8.6", decision_rule_detail,
            decision_rule_display_evidence,
        )
    else:
        _add_check(
            checks, "statement_of_conformity", "Statement of conformity",
            "NOT_APPLICABLE", "7.8.6",
            "No statement of conformity was detected; this conditional check is not applied.",
            None,
        )
        _add_check(
            checks, "decision_rule", "Decision rule / uncertainty handling",
            "NOT_APPLICABLE", "7.8.6",
            "No statement of conformity was detected, so the decision-rule check is not applicable.",
            None,
        )

    # --------------------------------------------------------
    # ISO/IEC 17025:2017 - MEASUREMENT UNCERTAINTY
    # --------------------------------------------------------

    uncertainty_evidence = _measurement_uncertainty_evidence(text)

    uncertainty_required_hint = _contains_any(
        text,
        [
            "uncertainty required",
            "measurement uncertainty required",
            "report uncertainty",
            "include uncertainty",
            "uncertainty shall be reported",
        ]
    )

    if uncertainty_evidence:
        uncertainty_status = "PASS"
        uncertainty_detail = "Measurement uncertainty information is present in the report."
    elif uncertainty_required_hint:
        uncertainty_status = "REVIEW"
        uncertainty_detail = (
            "The report indicates uncertainty may be required, but no "
            "measurement-uncertainty evidence was detected."
        )
    else:
        uncertainty_status = "NOT_APPLICABLE"
        uncertainty_detail = (
            "No evidence was found that measurement uncertainty must be reported "
            "for this result; it is treated as a conditional reporting requirement."
        )

    _add_check(
        checks, "measurement_uncertainty", "Measurement uncertainty information",
        uncertainty_status, "7.8.3", uncertainty_detail, uncertainty_evidence,
    )

    # --------------------------------------------------------
    # NABL REPORT-LEVEL INDICATOR
    # --------------------------------------------------------

    nabl_evidence = _nabl_evidence(
        text
    )

    _add_check(
        checks,
        "nabl_accreditation_reference",
        "NABL / accreditation reference",
        "PASS" if nabl_evidence else "REVIEW",
        "NABL report-level indicator",
        (
            "Explicit NABL/accreditation evidence is checked on the report. "
            "A generic 'Scope & Certificate' label alone is not treated as proof. "
            "Even when evidence is present, this automated check cannot prove that "
            "the reported test is inside the laboratory's current accredited scope."
        ),
        nabl_evidence,
    )

    # --------------------------------------------------------
    # OVERALL REPORT-LEVEL STATUS
    # --------------------------------------------------------

    issue_count = sum(
        1
        for check in checks
        if check["status"] == "ISSUE"
    )

    review_count = sum(
        1
        for check in checks
        if check["status"] == "REVIEW"
    )

    pass_count = sum(
        1
        for check in checks
        if check["status"] == "PASS"
    )

    not_applicable_count = sum(
        1
        for check in checks
        if check["status"] == "NOT_APPLICABLE"
    )

    if issue_count:
        overall_status = "ISSUE"
    elif review_count:
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"

    return {
        "standard":
            "ISO/IEC 17025:2017",

        "scope":
            (
                "Automated report-level check focused on reporting requirements "
                "and NABL indicators; not an accreditation decision."
            ),

        "document_type":
            document_type,

        "overall_status":
            overall_status,

        "pass_count":
            pass_count,

        "review_count":
            review_count,

        "issue_count":
            issue_count,

        "not_applicable_count":
            not_applicable_count,

        "checks":
            checks,

        "limitations": [
            (
                "This does not certify the laboratory or independently confirm "
                "current NABL accreditation."
            ),
            (
                "The laboratory's current NABL scope cannot be proven from "
                "report text alone."
            ),
            (
                "Some ISO/IEC 17025 requirements concern laboratory systems, "
                "technical competence, equipment, traceability and records "
                "outside the test report."
            ),
            (
                "Conditional requirements remain REVIEW when applicability "
                "cannot be established from the uploaded documents."
            ),
        ],
    }
