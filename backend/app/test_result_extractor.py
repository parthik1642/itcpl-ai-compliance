import re


def safe_float(value):
    if value is None:
        return None

    value = value.strip()
    value = value.replace(",", ".")

    # Remove anything except numbers, minus sign and decimal point
    value = re.sub(r"[^0-9.\-]", "", value)

    # Prevent invalid values such as ".", "-", or ""
    if value in ["", ".", "-", "-."]:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def extract_impact_test(text: str) -> dict:
    data = {
        "readings": [],
        "average": None,
        "single_minimum": None,
        "average_minimum": None,
        "temperature_c": None,
        "reported_conformity": None
    }

    # Temperature
    match = re.search(
        r"Impact Test\s*@\s*(-?\d+)\s*°?\s*C",
        text,
        re.IGNORECASE
    )

    if match:
        data["temperature_c"] = safe_float(match.group(1))

    # Impact readings
    match = re.search(
        r"Energy Absorbed\s*\(Joules\).*?"
        r"(\d+(?:\.\d+)?)\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        data["readings"] = [
            safe_float(match.group(1)),
            safe_float(match.group(2)),
            safe_float(match.group(3))
        ]

        data["average"] = safe_float(match.group(4))

    # Single minimum
    match = re.search(
        r"Single Minimum\s*:\s*(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )

    if match:
        data["single_minimum"] = safe_float(
            match.group(1)
        )

    # Average minimum
    match = re.search(
        r"Average Minimum\s*:\s*(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )

    if match:
        data["average_minimum"] = safe_float(
            match.group(1)
        )

    # Report conformity
    text_lower = text.lower()

    if (
        "does not meets" in text_lower
        or "does not meet" in text_lower
    ):
        data["reported_conformity"] = "FAIL"

    elif "meets the customer" in text_lower:
        data["reported_conformity"] = "PASS"

    return data


def extract_chemical_test(text: str) -> dict:
    elements = {}

    max_elements = {
        "carbon": "Carbon",
        "silicon": "Silicon",
        "manganese": "Manganese",
        "phosphorus": "Phosphorus",
        "sulphur": "Sulphur"
    }

    symbols = {
        "carbon": "C",
        "silicon": "Si",
        "manganese": "Mn",
        "phosphorus": "P",
        "sulphur": "S"
    }

    for key, name in max_elements.items():

        symbol = symbols[key]

        pattern = (
            rf"%\s*{name}\s*\({symbol}\)"
            rf".*?"
            rf"(\d+(?:\.\d+)?)"
            rf"\s+"
            rf"(\d+(?:[.,]\d+)?)"
            rf"\s*max"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            result = safe_float(match.group(1))
            maximum = safe_float(match.group(2))

            if result is not None and maximum is not None:
                elements[key] = {
                    "result": result,
                    "maximum": maximum
                }

    # Chromium has min and max
    match = re.search(
        r"%\s*Chromium\s*\(Cr\)"
        r".*?"
        r"(\d+(?:\.\d+)?)"
        r"\s+"
        r"(\d+(?:\.\d+)?)"
        r"\s*-\s*"
        r"(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE
    )

    if match:
        result = safe_float(match.group(1))
        minimum = safe_float(match.group(2))
        maximum = safe_float(match.group(3))

        if (
            result is not None
            and minimum is not None
            and maximum is not None
        ):
            elements["chromium"] = {
                "result": result,
                "minimum": minimum,
                "maximum": maximum
            }

    return {
        "elements": elements
    }


def extract_test_results(
    document_type: str,
    text: str
) -> dict:

    if document_type == "impact_test_report":
        return extract_impact_test(text)

    if document_type == "chemical_test_report":
        return extract_chemical_test(text)

    return {}