def group_reports_by_lab(pages: list) -> dict:

    labs = {}

    for page in pages:

        extracted_data = page.get(
            "extracted_data", {}
        )

        lab_no = extracted_data.get("lab_no")

        # If we cannot identify the lab number,
        # don't mix it with other reports.
        if not lab_no:
            continue

        # Create the lab group if it doesn't exist
        if lab_no not in labs:

            labs[lab_no] = {
                "lab_no": lab_no,
                "customer": extracted_data.get("customer"),
                "po_no": extracted_data.get("po_no"),
                "heat_no": extracted_data.get("heat_no"),
                "specification": extracted_data.get(
                    "specification"
                ),
                "reports": []
            }

        # Add this report to its Lab Number
        labs[lab_no]["reports"].append({
            "page_number": page.get("page_number"),
            "document_type": page.get("document_type"),
            "test_name": extracted_data.get("test_name"),
            "test_results": page.get("test_results"),
            "compliance": page.get("compliance")
        })

    return labs

def calculate_lab_status(lab: dict) -> dict:

    reports = lab.get("reports", [])

    if not reports:
        return {
            "status": "REVIEW",
            "reason": "No test reports found."
        }

    statuses = []

    for report in reports:

        compliance = report.get(
            "compliance", {}
        )

        status = compliance.get(
            "status", "REVIEW"
        )

        statuses.append(status)

    # REVIEW takes priority because something
    # could not be verified reliably.
    if "REVIEW" in statuses:

        return {
            "status": "REVIEW",
            "reason": "One or more reports require manual review."
        }

    # If everything was readable and at least
    # one test failed, the lab fails.
    if "FAIL" in statuses:

        return {
            "status": "FAIL",
            "reason": "One or more tests failed."
        }

    if all(
        status == "PASS"
        for status in statuses
    ):

        return {
            "status": "PASS",
            "reason": "All available test reports passed."
        }

    return {
        "status": "REVIEW",
        "reason": "Lab status could not be determined."
    }