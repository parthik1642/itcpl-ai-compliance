def classify_document(text: str) -> str:
    text_upper = text.upper()

    # Purchase Order
    if "PURCHASE ORDER" in text_upper:
        return "purchase_order"

    # Job Order
    if "JOB ORDER" in text_upper:
        return "job_order"

    # Test Reports
    if "TEST REPORT" in text_upper:

        if "SPECTRO CHEMICAL ANALYSIS" in text_upper:
            return "chemical_test_report"

        if "IMPACT TEST" in text_upper:
            return "impact_test_report"

        if "TENSILE TEST" in text_upper:
            return "tensile_test_report"

        if "HARDNESS TEST" in text_upper:
            return "hardness_test_report"

        if "MICROSTRUCTURE EXAMINATION" in text_upper:
            return "microstructure_test_report"

        if "MACRO EXAMINATION" in text_upper:
            return "macro_test_report"

        return "test_report"

    return "unknown"