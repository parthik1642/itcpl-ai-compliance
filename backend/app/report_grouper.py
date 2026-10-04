import re


TEST_TYPE_ALIASES = {
    "chemical_test": "chemical_test_report",
    "chemical": "chemical_test_report",
    "chemical analysis": "chemical_test_report",
    "spectro chemical": "chemical_test_report",
    "spectro chemical analysis": "chemical_test_report",
    "impact_test": "impact_test_report",
    "impact": "impact_test_report",
    "impact test": "impact_test_report",
    "tensile_test": "tensile_test_report",
    "tensile": "tensile_test_report",
    "tensile test": "tensile_test_report",
    "full tensile": "tensile_test_report",
    "full tensile test": "tensile_test_report",
    "bend_test": "bend_test_report",
    "bend": "bend_test_report",
    "bend test": "bend_test_report",
    "side bend": "bend_test_report",
    "hardness_test": "hardness_test_report",
    "hardness": "hardness_test_report",
    "hardness test": "hardness_test_report",
    "hardness survey": "hardness_test_report",
    "rockwell hardness": "hardness_test_report",
    "vickers hardness": "hardness_test_report",
    "proof_load_test": "proof_load_test_report",
    "proof load": "proof_load_test_report",
    "proof load test": "proof_load_test_report",
    "nut proof load": "proof_load_test_report",
    "nut proof load test": "proof_load_test_report",
    "microstructure_test": "microstructure_test_report",
    "microstructure": "microstructure_test_report",
    "microstructure examination": "microstructure_test_report",
    "macro_test": "macro_test_report",
    "macro": "macro_test_report",
    "macro test": "macro_test_report",
    "macro examination": "macro_test_report",
    "ferrite": "ferrite_test_report",
    "ferrite test": "ferrite_test_report",
    "ferrite_test": "ferrite_test_report",
    "ferrite_test_report": "ferrite_test_report",
    "corrosion": "corrosion_test_report",
    "corrosion test": "corrosion_test_report",
    "corrosion_test": "corrosion_test_report",
    "corrosion_test_report": "corrosion_test_report",
}


def _clean(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def _normalize_lab_no(value):
    value = _clean(value)
    if not value:
        return None
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*-\s*", "-", value)
    match = re.search(r"\b(\d{2})-(\d{6})\b", value)
    return f"{match.group(1)}-{match.group(2)}" if match else value


def _normalize_heat_no(value):
    value = _clean(value)
    if not value:
        return None
    value = value.replace("–", "-").replace("—", "-")
    return re.sub(r"\s*-\s*", "-", value)


def _normalize_test_type(value):
    value = _clean(value)
    if not value:
        return None
    key = value.lower().replace("-", " ").replace("_", " ")
    key = re.sub(r"\s+", " ", key).strip()
    if key.endswith(" report"):
        key = key[:-7].strip()
    if key.endswith(" test report"):
        key = key[:-7].strip()
    normalized = TEST_TYPE_ALIASES.get(key)
    if normalized:
        return normalized
    raw = value.lower().strip()
    if raw.endswith("_test_report"):
        return raw
    if raw.endswith("_test"):
        return raw + "_report"
    return raw


def group_reports_by_lab(pages: list) -> dict:
    labs = {}

    for page in pages:
        extracted_data = page.get("extracted_data") or {}
        test_results = page.get("test_results") or {}

        lab_no = extracted_data.get("lab_no") or test_results.get("lab_no")
        heat_no = extracted_data.get("heat_no") or test_results.get("heat_no")

        lab_no = _normalize_lab_no(lab_no)
        heat_no = _normalize_heat_no(heat_no)

        if not lab_no:
            print(
                "REPORT GROUPING WARNING: "
                f"page {page.get('page_number')} "
                f"({page.get('document_type')}) has no Lab No."
            )
            continue

        if lab_no not in labs:
            labs[lab_no] = {
                "lab_no": lab_no,
                "customer": extracted_data.get("customer"),
                "po_no": extracted_data.get("po_no"),
                "heat_no": heat_no,
                "specification": (
                    extracted_data.get("specification")
                    or test_results.get("specification")
                ),
                "reports": [],
            }

        if not labs[lab_no].get("heat_no") and heat_no:
            labs[lab_no]["heat_no"] = heat_no

        specification = (
            extracted_data.get("specification")
            or test_results.get("specification")
        )
        if not labs[lab_no].get("specification") and specification:
            labs[lab_no]["specification"] = specification

        if not labs[lab_no].get("customer") and extracted_data.get("customer"):
            labs[lab_no]["customer"] = extracted_data.get("customer")

        if not labs[lab_no].get("po_no") and extracted_data.get("po_no"):
            labs[lab_no]["po_no"] = extracted_data.get("po_no")

        page_types = page.get("document_types") or [page.get("document_type")]
        page_types = [
            _normalize_test_type(value)
            for value in page_types
            if value
        ]
        page_types = list(dict.fromkeys(value for value in page_types if value))

        results_by_type = page.get("test_results_by_type") or {}
        compliance_by_type = page.get("compliance_by_type") or {}

        for document_type in page_types:
            per_type_results = (
                results_by_type.get(document_type)
                or (
                    test_results
                    if _normalize_test_type(page.get("document_type")) == document_type
                    else {}
                )
            )
            per_type_compliance = (
                compliance_by_type.get(document_type)
                or (
                    page.get("compliance") or {}
                    if _normalize_test_type(page.get("document_type")) == document_type
                    else {}
                )
            )

            labs[lab_no]["reports"].append({
                "page_number": page.get("page_number"),
                "document_type": document_type,
                "test_name": (
                    extracted_data.get("test_name")
                    or per_type_results.get("test_name")
                ),
                "lab_no": lab_no,
                "heat_no": heat_no,
                "test_results": per_type_results,
                "compliance": per_type_compliance or {
                    "status": "REVIEW",
                    "issues": [
                        "Report was detected, but its result still requires verification."
                    ],
                },
            })

            print(
                "REPORT GROUPED: "
                f"page {page.get('page_number')} -> "
                f"{lab_no} / {heat_no or 'heat unknown'} / "
                f"{document_type}"
            )

    return labs


def calculate_lab_status(lab: dict) -> dict:
    reports = lab.get("reports", [])
    if not reports:
        return {"status": "REVIEW", "reason": "No test reports found."}

    statuses = [
        (report.get("compliance") or {}).get("status", "REVIEW")
        for report in reports
    ]

    if "FAIL" in statuses:
        return {"status": "FAIL", "reason": "One or more tests failed."}
    if "REVIEW" in statuses:
        return {"status": "REVIEW", "reason": "One or more reports require manual review."}
    if statuses and all(status == "PASS" for status in statuses):
        return {"status": "PASS", "reason": "All available test reports passed."}
    return {"status": "REVIEW", "reason": "Lab status could not be determined."}
