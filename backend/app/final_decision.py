def build_final_decisions(
    po_job_comparison: dict,
    report_comparison: dict
) -> dict:

    """
    Final compliance is driven by REQUIRED TEST REPORTS.

    PO extraction/matching problems are supporting warnings.

    PO problems must NOT:
    - create MISSING
    - create FAIL
    - automatically create REVIEW
    """

    final_results = {}

    all_lab_numbers = set()

    all_lab_numbers.update(
        po_job_comparison.get(
            "labs",
            {}
        ).keys()
    )

    all_lab_numbers.update(
        report_comparison.keys()
    )


    for lab_no in all_lab_numbers:

        po_result = (
            po_job_comparison
            .get(
                "labs",
                {}
            )
            .get(
                lab_no,
                {}
            )
        )

        report_result = (
            report_comparison.get(
                lab_no,
                {}
            )
        )


        report_status = (
            report_result.get(
                "final_status",
                "REVIEW"
            )
        )


        # ====================================================
        # REAL COMPLIANCE ISSUES
        # ====================================================

        issues = []


        for item in (
            report_result.get(
                "report_issues",
                []
            )
        ):

            test_name = item.get(
                "test",
                "unknown_test"
            )

            issue = item.get(
                "issue",
                "Unknown issue"
            )

            issues.append(
                f"{test_name}: {issue}"
            )


        for missing_test in (
            report_result.get(
                "missing_tests",
                []
            )
        ):

            issues.append(
                "Missing required report: "
                f"{missing_test}"
            )


        # ====================================================
        # PO WARNINGS
        # ====================================================

        warnings = list(
            po_result.get(
                "issues",
                []
            )
        )


        # ====================================================
        # FINAL STATUS
        # ====================================================

        if report_status == "MISSING":

            final_status = "MISSING"

            reason = (
                "One or more client-required "
                "test reports are missing."
            )


        elif report_status == "FAIL":

            final_status = "FAIL"

            reason = (
                "One or more required tests "
                "failed compliance validation."
            )


        elif report_status == "REVIEW":

            final_status = "REVIEW"

            reason = (
                "One or more required test "
                "results could not be verified "
                "reliably."
            )


        elif report_status == "PASS":

            final_status = "PASS"

            reason = (
                "All client-required tests are "
                "present and all verified test "
                "requirements passed."
            )


        else:

            final_status = "REVIEW"

            reason = (
                "Test compliance status could "
                "not be determined."
            )


        final_results[
            lab_no
        ] = {

            "lab_no":
                lab_no,

            "po_job_status":
                po_result.get(
                    "status",
                    "REVIEW"
                ),

            "report_status":
                report_status,

            "final_status":
                final_status,

            "reason":
                reason,

            # Actual test compliance problems.
            "issues":
                issues,

            # PO/OCR metadata problems only.
            "warnings":
                warnings
        }


    return final_results