def compare_job_with_reports(
    job_order_data: dict,
    report_labs: dict
) -> dict:

    results = {}

    job_labs = job_order_data.get(
        "labs",
        []
    )

    for job_lab in job_labs:

        lab_no = job_lab.get("lab_no")

        required_tests = job_lab.get(
            "required_tests",
            []
        )

        report_lab = report_labs.get(
            lab_no,
            {}
        )

        reports = report_lab.get(
            "reports",
            []
        )

        uploaded_tests = [
            report.get("document_type")
            for report in reports
        ]

        missing_tests = [
            required_test
            for required_test in required_tests
            if required_test not in uploaded_tests
        ]

        # --------------------------------
        # COLLECT REPORT ISSUES
        # --------------------------------

        report_issues = []

        for report in reports:

            document_type = report.get(
                "document_type",
                "unknown_test"
            )

            compliance = report.get(
                "compliance",
                {}
            )

            compliance_issues = compliance.get(
                "issues",
                []
            )

            for issue in compliance_issues:

                report_issues.append({
                    "test": document_type,
                    "issue": issue
                })

        # --------------------------------
        # FINAL STATUS
        # --------------------------------

        if missing_tests:

            final_status = "MISSING"

            reason = (
                "One or more required test "
                "reports are missing."
            )

        else:

            statuses = [
                report.get(
                    "compliance",
                    {}
                ).get(
                    "status",
                    "REVIEW"
                )
                for report in reports
            ]

            if "REVIEW" in statuses:

                final_status = "REVIEW"

                reason = (
                    "One or more reports require "
                    "manual review."
                )

            elif "FAIL" in statuses:

                final_status = "FAIL"

                reason = (
                    "One or more required tests failed."
                )

            elif required_tests:

                final_status = "PASS"

                reason = (
                    "All required reports are present "
                    "and all verified tests passed."
                )

            else:

                final_status = "REVIEW"

                reason = (
                    "No required tests could be "
                    "identified from the Job Order."
                )

        results[lab_no] = {
            "lab_no": lab_no,
            "required_tests": required_tests,
            "uploaded_tests": uploaded_tests,
            "missing_tests": missing_tests,
            "report_issues": report_issues,
            "final_status": final_status,
            "reason": reason
        }

    return results