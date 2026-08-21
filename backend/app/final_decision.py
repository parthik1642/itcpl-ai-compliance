def build_final_decisions(
    po_job_comparison: dict,
    report_comparison: dict
) -> dict:

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
            .get("labs", {})
            .get(lab_no, {})
        )

        report_result = (
            report_comparison
            .get(lab_no, {})
        )

        po_status = po_result.get(
            "status",
            "REVIEW"
        )

        report_status = report_result.get(
            "final_status",
            "REVIEW"
        )

        issues = []

        # PO / Job issues
        issues.extend(
            po_result.get(
                "issues",
                []
            )
        )

        # Report issues
        report_issues = report_result.get(
            "report_issues",
            []
        )

        for item in report_issues:

            test_name = item.get(
                "test",
                "unknown_test"
            )

            issue_text = item.get(
                "issue",
                "Unknown issue"
            )

            issues.append(
                f"{test_name}: {issue_text}"
            )

        # Missing tests
        for missing_test in report_result.get(
            "missing_tests",
            []
        ):

            issues.append(
                f"Missing required report: "
                f"{missing_test}"
            )

        # --------------------------------
        # FINAL DECISION
        # --------------------------------

        if po_status != "MATCH":

            final_status = "REVIEW"

            reason = (
                "Purchase Order and Job Order "
                "require verification."
            )

        elif report_status == "MISSING":

            final_status = "MISSING"

            reason = (
                "One or more required test "
                "reports are missing."
            )

        elif report_status == "FAIL":

            final_status = "FAIL"

            reason = (
                "One or more required tests failed."
            )

        elif report_status == "REVIEW":

            final_status = "REVIEW"

            reason = (
                "One or more reports could not "
                "be verified automatically."
            )

        elif report_status == "PASS":

            final_status = "PASS"

            reason = (
                "Purchase Order, Job Order and "
                "all required test reports "
                "passed validation."
            )

        else:

            final_status = "REVIEW"

            reason = (
                "Final status could not be determined."
            )

        final_results[lab_no] = {
            "lab_no": lab_no,
            "po_job_status": po_status,
            "report_status": report_status,
            "final_status": final_status,
            "reason": reason,
            "issues": issues
        }

    return final_results