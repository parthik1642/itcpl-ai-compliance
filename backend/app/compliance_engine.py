def evaluate_impact_test(test_results: dict) -> dict:
    readings = test_results.get("readings", [])
    average = test_results.get("average")
    single_minimum = test_results.get("single_minimum")
    average_minimum = test_results.get("average_minimum")

    issues = []

    if not readings:
        return {
            "status": "REVIEW",
            "issues": ["Impact readings could not be extracted."]
        }

    if single_minimum is None:
        return {
            "status": "REVIEW",
            "issues": ["Single minimum requirement is missing."]
        }

    if average_minimum is None:
        return {
            "status": "REVIEW",
            "issues": ["Average minimum requirement is missing."]
        }

    # Check every individual reading
    for index, reading in enumerate(readings, start=1):

        if reading < single_minimum:
            issues.append(
                f"Reading {index} failed: "
                f"{reading} J < {single_minimum} J minimum."
            )

    # Check average
    if average is None:
        issues.append("Average value could not be extracted.")

    elif average < average_minimum:
        issues.append(
            f"Average failed: "
            f"{average} J < {average_minimum} J minimum."
        )

    if issues:
        return {
            "status": "FAIL",
            "issues": issues
        }

    return {
        "status": "PASS",
        "issues": []
    }


def evaluate_chemical_test(test_results: dict) -> dict:
    elements = test_results.get("elements", {})

    issues = []

    if not elements:
        return {
            "status": "REVIEW",
            "issues": ["Chemical values could not be extracted."]
        }

    for element_name, values in elements.items():

        result = values.get("result")
        minimum = values.get("minimum")
        maximum = values.get("maximum")

        if result is None:
            issues.append(
                f"{element_name}: result is missing."
            )
            continue

        if minimum is not None and result < minimum:
            issues.append(
                f"{element_name}: {result} is below "
                f"minimum {minimum}."
            )

        if maximum is not None and result > maximum:
            issues.append(
                f"{element_name}: {result} exceeds "
                f"maximum {maximum}."
            )

    if issues:
        return {
            "status": "FAIL",
            "issues": issues
        }

    return {
        "status": "PASS",
        "issues": []
    }


def evaluate_test(
    document_type: str,
    test_results: dict
) -> dict:

    if document_type == "impact_test_report":
        return evaluate_impact_test(test_results)

    if document_type == "chemical_test_report":
        return evaluate_chemical_test(test_results)

    return {
        "status": "REVIEW",
        "issues": [
            f"No compliance rule created yet for {document_type}."
        ]
    }