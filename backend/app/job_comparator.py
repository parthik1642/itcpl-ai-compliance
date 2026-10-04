import re


TEST_TYPE_ALIASES = {
    "chemical": "chemical_test_report",
    "chemical test": "chemical_test_report",
    "chemical analysis": "chemical_test_report",
    "spectro chemical": "chemical_test_report",
    "spectro chemical analysis": "chemical_test_report",
    "chemical_test": "chemical_test_report",
    "chemical_test_report": "chemical_test_report",
    "impact": "impact_test_report",
    "impact test": "impact_test_report",
    "impact_test": "impact_test_report",
    "impact_test_report": "impact_test_report",
    "tensile": "tensile_test_report",
    "tensile test": "tensile_test_report",
    "full tensile": "tensile_test_report",
    "full tensile test": "tensile_test_report",
    "tensile_test": "tensile_test_report",
    "tensile_test_report": "tensile_test_report",
    "bend": "bend_test_report",
    "bend test": "bend_test_report",
    "side bend": "bend_test_report",
    "bend_test": "bend_test_report",
    "bend_test_report": "bend_test_report",
    "hardness": "hardness_test_report",
    "hardness test": "hardness_test_report",
    "hardness survey": "hardness_test_report",
    "rockwell hardness": "hardness_test_report",
    "vickers hardness": "hardness_test_report",
    "hardness_test": "hardness_test_report",
    "hardness_test_report": "hardness_test_report",
    "proof load": "proof_load_test_report",
    "proof load test": "proof_load_test_report",
    "nut proof load": "proof_load_test_report",
    "nut proof load test": "proof_load_test_report",
    "proof_load_test": "proof_load_test_report",
    "proof_load_test_report": "proof_load_test_report",
    "microstructure": "microstructure_test_report",
    "microstructure examination": "microstructure_test_report",
    "microstructure_test": "microstructure_test_report",
    "microstructure_test_report": "microstructure_test_report",
    "macro": "macro_test_report",
    "macro test": "macro_test_report",
    "macro examination": "macro_test_report",
    "macro_test": "macro_test_report",
    "macro_test_report": "macro_test_report",
    "ferrite": "ferrite_test_report",
    "ferrite test": "ferrite_test_report",
    "ferrite_test": "ferrite_test_report",
    "ferrite_test_report": "ferrite_test_report",
    "corrosion": "corrosion_test_report",
    "corrosion test": "corrosion_test_report",
    "corrosion_test": "corrosion_test_report",
    "corrosion_test_report": "corrosion_test_report",
}


def _normalize_test_type(value):
    if not value:
        return None
    raw = str(value).strip().lower()
    key = raw.replace("-", " ").replace("_", " ")
    key = re.sub(r"\s+", " ", key).strip()
    if key.endswith(" report"):
        key = key[:-7].strip()
    normalized = TEST_TYPE_ALIASES.get(raw) or TEST_TYPE_ALIASES.get(key)
    if normalized:
        return normalized
    if raw.endswith("_test_report"):
        return raw
    if raw.endswith("_test"):
        return raw + "_report"
    return raw


def compare_job_with_reports(job_order_data: dict, report_labs: dict) -> dict:
    results = {}

    for job_lab in job_order_data.get("labs", []):
        lab_no = job_lab.get("lab_no")

        required_tests = list(dict.fromkeys(
            normalized
            for normalized in (
                _normalize_test_type(test)
                for test in (job_lab.get("required_tests") or [])
            )
            if normalized
        ))

        report_lab = report_labs.get(lab_no, {})
        reports = report_lab.get("reports", [])

        uploaded_tests = list(dict.fromkeys(
            normalized
            for normalized in (
                _normalize_test_type(
                    report.get("document_type")
                    or report.get("test_name")
                )
                for report in reports
            )
            if normalized
        ))

        missing_tests = [
            required_test
            for required_test in required_tests
            if required_test not in uploaded_tests
        ]

        report_issues = []
        for report in reports:
            document_type = _normalize_test_type(
                report.get("document_type")
                or report.get("test_name")
            ) or "unknown_test"
            for issue in (report.get("compliance") or {}).get("issues", []):
                report_issues.append({"test": document_type, "issue": issue})

        test_details = []

        for required_test in required_tests:
            matches = [
                report
                for report in reports
                if _normalize_test_type(
                    report.get("document_type")
                    or report.get("test_name")
                ) == required_test
            ]

            if not matches:
                test_details.append({
                    "test": required_test,
                    "completed": False,
                    "status": "MISSING",
                    "page_number": None,
                    "test_name": None,
                    "test_results": {},
                    "issues": ["Required test report not found."],
                })
                continue

            statuses = [
                (report.get("compliance") or {}).get("status", "REVIEW")
                for report in matches
            ]
            if "FAIL" in statuses:
                aggregate_status = "FAIL"
            elif "PASS" in statuses:
                aggregate_status = "PASS"
            else:
                aggregate_status = "REVIEW"

            chosen = next(
                (
                    r for r in matches
                    if (r.get("compliance") or {}).get("status") == aggregate_status
                ),
                matches[0],
            )

            aggregate_issues = []
            if aggregate_status != "PASS":
                for report in matches:
                    if (report.get("compliance") or {}).get("status") == aggregate_status:
                        for issue in (report.get("compliance") or {}).get("issues", []):
                            if issue not in aggregate_issues:
                                aggregate_issues.append(issue)

            test_details.append({
                "test": required_test,
                "completed": True,
                "status": aggregate_status,
                "page_number": chosen.get("page_number"),
                "test_name": chosen.get("test_name"),
                "test_results": chosen.get("test_results", {}),
                "issues": aggregate_issues,
                "matched_pages": [r.get("page_number") for r in matches],
            })

        if missing_tests:
            final_status = "MISSING"
            reason = "One or more required test reports are missing."
        else:
            statuses = [
                detail.get("status", "REVIEW")
                for detail in test_details
                if detail.get("completed")
            ]

            if "FAIL" in statuses:
                final_status = "FAIL"
                reason = "One or more required tests failed."
            elif "REVIEW" in statuses:
                final_status = "REVIEW"
                reason = (
                    "All required reports are present, but one or more "
                    "results require manual review."
                )
            elif required_tests and statuses:
                final_status = "PASS"
                reason = (
                    "All required reports are present and all verified tests passed."
                )
            else:
                final_status = "REVIEW"
                reason = "No required tests could be identified from the Job Order."

        results[lab_no] = {
            "lab_no": lab_no,
            "required_tests": required_tests,
            "uploaded_tests": uploaded_tests,
            "missing_tests": missing_tests,
            "report_issues": report_issues,
            "test_details": test_details,
            "final_status": final_status,
            "reason": reason,
        }

        print(
            "JOB COMPARISON:",
            lab_no,
            "| required =", required_tests,
            "| uploaded =", uploaded_tests,
            "| missing =", missing_tests,
            "| status =", final_status,
        )

    return results
