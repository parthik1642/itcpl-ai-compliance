from app.test_result_extractor import extract_test_results


def extract_with_fallback(
    document_type: str,
    text: str
) -> dict:

    result = extract_test_results(
        document_type,
        text
    )

    result["extraction_source"] = "regex"

    # Critical numerical values must not be guessed.
    if document_type == "impact_test_report":

        readings = result.get("readings", [])

        if len(readings) != 3:
            result["needs_review"] = True
            result["review_reason"] = (
                "Could not reliably extract all 3 impact readings."
            )
        else:
            result["needs_review"] = False

    return result