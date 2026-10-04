def evaluate_impact_test(test_results: dict) -> dict:

    readings = test_results.get("readings", [])

    average = test_results.get("average")

    single_minimum = test_results.get("single_minimum")

    average_minimum = test_results.get("average_minimum")

    reported = test_results.get("reported_conformity")



    if reported == "FAIL":

        return {

            "status": "FAIL",

            "issues": [

                "The test report states that the result does not meet "

                "the customer requirement."

            ],

        }



    issues = []



    # If all numerical values were extracted,

    # verify them independently.

    if (

        len(readings) == 3

        and single_minimum is not None

        and average_minimum is not None

    ):

        for index, reading in enumerate(readings, start=1):

            if reading is not None and reading < single_minimum:

                issues.append(

                    f"Reading {index} failed: "

                    f"{reading} J < {single_minimum} J minimum."

                )



        if average is None:

            issues.append(

                "Average value could not be extracted."

            )



        elif average < average_minimum:

            issues.append(

                f"Average failed: "

                f"{average} J < {average_minimum} J minimum."

            )



        if issues:

            return {

                "status": "FAIL",

                "issues": issues,

            }



        return {

            "status": "PASS",

            "issues": [],

        }



    # If numerical extraction is incomplete but

    # the signed report explicitly says PASS,

    # accept the completed report.

    if reported == "PASS":

        return {

            "status": "PASS",

            "issues": [],

        }



    return {

        "status": "REVIEW",

        "issues": [

            "Impact report is present, but its numerical "

            "result could not be fully verified automatically."

        ],

    }





def evaluate_chemical_test(test_results: dict) -> dict:

    elements = test_results.get("elements", {})

    reported = test_results.get("reported_conformity")



    issues = []



    if reported == "FAIL":

        return {

            "status": "FAIL",

            "issues": [

                "The test report states that the result does "

                "not meet the customer requirement."

            ],

        }



    if elements:

        for element_name, values in elements.items():

            result = values.get("result")

            minimum = values.get("minimum")

            maximum = values.get("maximum")



            if result is None:

                issues.append(

                    f"{element_name}: result is missing."

                )

                continue



            if (

                minimum is not None

                and result < minimum

            ):

                issues.append(

                    f"{element_name}: {result} is below "

                    f"minimum {minimum}."

                )



            if (

                maximum is not None

                and result > maximum

            ):

                issues.append(

                    f"{element_name}: {result} exceeds "

                    f"maximum {maximum}."

                )



        if issues:

            return {

                "status": "FAIL",

                "issues": issues,

            }



        return {

            "status": "PASS",

            "issues": [],

        }



    if reported == "PASS":

        return {

            "status": "PASS",

            "issues": [],

        }



    return {

        "status": "REVIEW",

        "issues": [

            "Chemical report is present, but its values "

            "could not be fully verified automatically."

        ],

    }





def evaluate_bend_test(test_results: dict) -> dict:

    reported = test_results.get("reported_conformity")

    if reported == "FAIL":

        return {"status": "FAIL", "issues": ["The signed bend report states failure."]}

    samples = [str(v).strip().lower() for v in (test_results.get("sample_results") or [])]

    if samples and all("satisfactory" in value for value in samples):

        return {"status": "PASS", "issues": []}

    if test_results.get("no_opening_observed_count", 0) > 0:

        return {"status": "PASS", "issues": []}

    return evaluate_reported_result("bend_test_report", test_results)





def evaluate_tensile_test(test_results: dict) -> dict:

    if test_results.get("reported_conformity") == "FAIL":

        return {"status": "FAIL", "issues": ["The signed tensile report states failure."]}



    parameters = test_results.get("parameters") or []

    checked = 0

    issues = []

    for item in parameters:

        result = item.get("result")

        minimum = item.get("minimum")

        maximum = item.get("maximum")

        if result is None or (minimum is None and maximum is None):

            continue

        checked += 1

        label = item.get("parameter") or "Tensile parameter"

        unit = item.get("unit") or ""

        if minimum is not None and result < minimum:

            issues.append(f"{label}: {result} {unit} < {minimum} {unit} minimum.")

        if maximum is not None and result > maximum:

            issues.append(f"{label}: {result} {unit} > {maximum} {unit} maximum.")

    if issues:

        return {"status": "FAIL", "issues": issues}

    if checked:

        return {"status": "PASS", "issues": []}

    return evaluate_reported_result("tensile_test_report", test_results)





def evaluate_hardness_test(test_results: dict) -> dict:

    if test_results.get("reported_conformity") == "FAIL":

        return {"status": "FAIL", "issues": ["The signed hardness report states failure."]}

    values = [v for v in (test_results.get("readings") or []) if v is not None]

    average = test_results.get("average")

    minimum = test_results.get("minimum")

    maximum = test_results.get("maximum")

    check_values = values or ([average] if average is not None else [])

    if check_values and (minimum is not None or maximum is not None):

        issues=[]

        for idx, value in enumerate(check_values, 1):

            if minimum is not None and value < minimum:

                issues.append(f"Hardness reading {idx}: {value} < {minimum} minimum.")

            if maximum is not None and value > maximum:

                issues.append(f"Hardness reading {idx}: {value} > {maximum} maximum.")

        return {"status": "FAIL" if issues else "PASS", "issues": issues}

    return evaluate_reported_result("hardness_test_report", test_results)





def evaluate_proof_load_test(test_results: dict) -> dict:

    if test_results.get("reported_conformity") == "FAIL":

        return {"status": "FAIL", "issues": ["The signed proof-load report states failure."]}

    applied = test_results.get("applied_load_kn")

    required = test_results.get("required_load_kn")

    if applied is not None and required is not None:

        if applied < required:

            return {"status": "FAIL", "issues": [f"Applied proof load {applied} kN < required {required} kN."]}

        return {"status": "PASS", "issues": []}

    return evaluate_reported_result("proof_load_test_report", test_results)





def evaluate_reported_result(

    document_type: str,

    test_results: dict,

) -> dict:



    # Support both the OLD extractor and the NEW extractor.

    #

    # Old project:

    # reported_conformity = PASS

    #

    # New extractor:

    # status = PASS

    reported = (

        test_results.get("reported_conformity")

        or test_results.get("status")

    )



    if reported == "FAIL":

        return {

            "status": "FAIL",

            "issues": [

                "The signed test report states that the "

                "result does not meet the customer requirement."

            ],

        }



    if reported == "PASS":

        return {

            "status": "PASS",

            "issues": [],

        }



    # --------------------------------------------------

    # Check conformity text directly

    # --------------------------------------------------



    conformity = (

        test_results.get("statement_of_conformity")

        or ""

    ).upper()



    negative_phrases = [

        "DOES NOT MEET",

        "NOT MEET",

        "NOT ACCEPTED",

        "UNSATISFACTORY",

        "FAILED",

    ]



    positive_phrases = [

        "MEETS THE REQUIREMENT",

        "MEETS THE CUSTOMERS REQUIREMENT",

        "MEETS THE CUSTOMER REQUIREMENT",

        "RESULTS ARE ACCEPTED",

        "RESULT IS ACCEPTED",

        "ACCEPTED AS PER",

        "SATISFACTORY",

    ]



    if any(

        phrase in conformity

        for phrase in negative_phrases

    ):

        return {

            "status": "FAIL",

            "issues": [

                "The test report conformity statement "

                "indicates failure."

            ],

        }



    if any(

        phrase in conformity

        for phrase in positive_phrases

    ):

        return {

            "status": "PASS",

            "issues": [],

        }



    # --------------------------------------------------

    # Report exists but conclusion could not be verified

    # --------------------------------------------------



    ignored_fields = {

        "reported_conformity",

        "status",

        "statement_of_conformity",

    }



    has_output = any(

        value not in (None, "", [], {})

        for key, value in test_results.items()

        if key not in ignored_fields

    )



    if has_output:

        return {

            "status": "REVIEW",

            "issues": [

                "Test report is present and output was "

                "extracted, but the conformity statement "

                "needs manual verification."

            ],

        }



    return {

        "status": "REVIEW",

        "issues": [

            f"{document_type} is present, but its output "

            f"could not be reliably extracted."

        ],

    }





def evaluate_test(

    document_type: str,

    test_results: dict,

) -> dict:



    # --------------------------------------------------

    # Normalize document type

    #

    # This allows both:

    #

    # tensile_test

    # tensile_test_report

    #

    # to work.

    # --------------------------------------------------



    type_aliases = {

        "tensile_test": "tensile_test_report",

        "bend_test": "bend_test_report",

        "impact_test": "impact_test_report",

        "hardness_test": "hardness_test_report",

        "macro_test": "macro_test_report",

        "microstructure_test": "microstructure_test_report",

        "chemical_test": "chemical_test_report",

        "proof_load_test": "proof_load_test_report",

        "ferrite_test": "ferrite_test_report",

        "corrosion_test": "corrosion_test_report",

    }



    document_type = type_aliases.get(

        document_type,

        document_type,

    )



    # --------------------------------------------------

    # Impact

    # --------------------------------------------------



    if document_type == "impact_test_report":



        # Support status produced by new extractor.

        if (

            test_results.get("status") == "PASS"

            and not test_results.get("readings")

        ):

            return {

                "status": "PASS",

                "issues": [],

            }



        return evaluate_impact_test(

            test_results

        )



    # --------------------------------------------------

    # Chemical

    # --------------------------------------------------



    if document_type == "chemical_test_report":

        return evaluate_chemical_test(

            test_results

        )



    if document_type == "tensile_test_report":

        return evaluate_tensile_test(test_results)



    if document_type == "hardness_test_report":

        return evaluate_hardness_test(test_results)



    if document_type == "proof_load_test_report":

        return evaluate_proof_load_test(test_results)



    if document_type == "bend_test_report":

        return evaluate_bend_test(test_results)



    if document_type in {

        "macro_test_report",

        "microstructure_test_report",

        "ferrite_test_report",

        "corrosion_test_report",

    }:

        return evaluate_reported_result(document_type, test_results)



    return {

        "status": "REVIEW",

        "issues": [

            f"No compliance rule created yet for "

            f"{document_type}."

        ],

    }





# ======================================================

# REQUIRED TEST vs COMPLETED TEST COMPARISON

# ======================================================



def normalize_required_test(test_name: str):

    """

    Convert requirement names and report names

    into the same internal format.

    """



    if not test_name:

        return None



    name = str(test_name).lower().strip()



    aliases = {

        "tensile": "tensile_test",

        "tensile test": "tensile_test",

        "tensile_test": "tensile_test",

        "tensile_test_report": "tensile_test",



        "bend": "bend_test",

        "bend test": "bend_test",

        "bending test": "bend_test",

        "bend_test": "bend_test",

        "bend_test_report": "bend_test",



        "impact": "impact_test",

        "impact test": "impact_test",

        "impact_test": "impact_test",

        "impact_test_report": "impact_test",



        "hardness": "hardness_test",

        "hardness test": "hardness_test",

        "hardness survey": "hardness_test",

        "vickers hardness": "hardness_test",

        "hardness_test": "hardness_test",

        "hardness_test_report": "hardness_test",



        "macro": "macro_test",

        "macro test": "macro_test",

        "macro examination": "macro_test",

        "macro_test": "macro_test",

        "macro_test_report": "macro_test",



        "microstructure": "microstructure_test",

        "microstructure examination": "microstructure_test",

        "microstructure_test": "microstructure_test",

        "microstructure_test_report": "microstructure_test",



        "chemical": "chemical_test",

        "chemical test": "chemical_test",

        "chemical analysis": "chemical_test",

        "chemical_test": "chemical_test",

        "chemical_test_report": "chemical_test",



        "proof load": "proof_load_test",

        "proof load test": "proof_load_test",

        "proof_load_test": "proof_load_test",

        "proof_load_test_report": "proof_load_test",

    }



    return aliases.get(name, name)





def compare_required_and_completed_tests(

    required_tests,

    completed_tests,

):

    """

    Compare tests requested by PO / Job Order

    against test reports that were uploaded.



    Returns a clean summary for frontend/API use.

    """



    required_tests = required_tests or []

    completed_tests = completed_tests or []



    normalized_required = []



    for test in required_tests:

        normalized = normalize_required_test(test)



        if (

            normalized

            and normalized not in normalized_required

        ):

            normalized_required.append(normalized)



    normalized_completed = []



    for test in completed_tests:



        # completed_tests can contain strings OR dictionaries

        if isinstance(test, dict):

            value = (

                test.get("normalized_test_name")

                or test.get("document_type")

                or test.get("test_name")

            )

        else:

            value = test



        normalized = normalize_required_test(value)



        if (

            normalized

            and normalized not in normalized_completed

        ):

            normalized_completed.append(normalized)



    missing_tests = [

        test

        for test in normalized_required

        if test not in normalized_completed

    ]



    completed_required_tests = [

        test

        for test in normalized_required

        if test in normalized_completed

    ]



    if not normalized_required:

        overall_status = "REVIEW"



    elif missing_tests:

        overall_status = "FAIL"



    else:

        overall_status = "PASS"



    return {

        "status": overall_status,



        "required_tests": normalized_required,



        "completed_tests": normalized_completed,



        "completed_required_tests":

            completed_required_tests,



        "missing_tests": missing_tests,



        "all_required_tests_completed":

            len(normalized_required) > 0

            and len(missing_tests) == 0,

    }