def compare_po_with_job_order(
    purchase_order: dict,
    job_order: dict
) -> dict:

    issues = []
    lab_results = {}

    po_heat_numbers = set(
        purchase_order.get(
            "heat_numbers", []
        )
    )

    for lab in job_order.get(
        "labs", []
    ):

        lab_no = lab.get("lab_no")
        heat_no = lab.get("heat_no")

        lab_issues = []

        if heat_no:

            if heat_no not in po_heat_numbers:

                lab_issues.append(
                    f"Heat No. {heat_no} was not found in the Purchase Order."
                )

        else:

            lab_issues.append(
                "Heat No. could not be extracted from the Job Order."
            )

        if lab_issues:

            lab_status = "REVIEW"

            issues.extend(
                [
                    f"{lab_no}: {issue}"
                    for issue in lab_issues
                ]
            )

        else:

            lab_status = "MATCH"

        lab_results[lab_no] = {
            "lab_no": lab_no,
            "heat_no": heat_no,
            "status": lab_status,
            "issues": lab_issues
        }

    overall_status = (
        "MATCH"
        if not issues
        else "REVIEW"
    )

    return {
        "overall_status": overall_status,
        "labs": lab_results,
        "issues": issues
    }