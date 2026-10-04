from __future__ import annotations



import os

from typing import Any



from app.test_result_extractor import extract_test_results

from app.llm_extractor import extract_test_report_with_ai





# ============================================================

# SETTINGS

# ============================================================



# Keep AI available as a fallback, but do NOT call it just

# because an optional field is missing.

AI_REPORT_FALLBACK_ENABLED = (

    os.getenv("AI_REPORT_FALLBACK_ENABLED", "false").lower() == "true"

)



AI_MIN_CONFIDENCE = float(

    os.getenv("AI_REPORT_MIN_CONFIDENCE", "0.78")

)





# ============================================================

# GENERIC HELPERS

# ============================================================





def _has_value(value: Any) -> bool:

    """Return True when a value contains useful extracted data."""



    if value is None:

        return False



    if isinstance(value, str):

        return bool(value.strip())



    if isinstance(value, (list, tuple, set, dict)):

        return len(value) > 0



    return True





def _confidence(value: Any) -> float:

    try:

        number = float(value)

    except (TypeError, ValueError):

        return 0.0



    return max(0.0, min(number, 1.0))





def _append_unique(items: list, value: Any) -> None:

    if value is None:

        return



    if value not in items:

        items.append(value)





# ============================================================

# DETERMINE WHETHER AI IS REALLY NEEDED

# ============================================================





def _deterministic_result_is_usable(

    document_type: str,

    result: dict,

) -> bool:

    """

    Decide whether the normal rule-based extractor already found

    enough information to continue WITHOUT Ollama.



    This function intentionally uses a conservative speed policy:

    AI is NOT called merely because specification/test method or

    another optional field was not extracted here. Those fields can

    be checked elsewhere in the pipeline or marked for review.



    AI is reserved for cases where the actual test result extraction

    substantially failed.

    """



    if not isinstance(result, dict):

        return False



    conformity = result.get("reported_conformity")



    # --------------------------------------------------------

    # IMPACT

    # --------------------------------------------------------

    if document_type == "impact_test_report":

        readings = [

            value

            for value in result.get("readings", [])

            if value is not None

        ]



        # Three impact readings are the strongest deterministic signal.

        if len(readings) >= 3:

            return True



        # If the existing report parser extracted an average plus a

        # report conformity statement, do not spend another AI call.

        if (

            result.get("average") is not None

            and _has_value(conformity)

        ):

            return True



        return False



    # --------------------------------------------------------

    # CHEMICAL

    # --------------------------------------------------------

    if document_type == "chemical_test_report":

        elements = result.get("elements", {})



        if isinstance(elements, dict) and len(elements) > 0:

            return True



        if _has_value(conformity):

            return True



        return False



    # --------------------------------------------------------

    # TENSILE

    # --------------------------------------------------------

    if document_type == "tensile_test_report":

        parameters = result.get("parameters", [])



        # Do NOT treat a report conclusion alone as enough evidence.

        # We want the actual tensile values/parameters before allowing

        # the fast path to skip AI.

        if isinstance(parameters, list) and len(parameters) > 0:

            return True



        if _has_value(result.get("ai_tensile_values")):

            return True



        return False



    # --------------------------------------------------------

    # HARDNESS

    # --------------------------------------------------------

    if document_type == "hardness_test_report":

        readings = [

            value

            for value in result.get("readings", [])

            if value is not None

        ]



        # Hardness must have actual extracted readings or an average.

        # A statement such as "meets requirement" by itself is not

        # enough to skip extraction/verification.

        if readings:

            return True



        if result.get("average") is not None:

            return True



        return False



    # --------------------------------------------------------

    # PROOF LOAD

    # --------------------------------------------------------

    if document_type == "proof_load_test_report":

        if result.get("applied_load_kn") is not None:

            return True



        if result.get("required_load_kn") is not None:

            return True



        if _has_value(conformity):

            return True



        return False



    # --------------------------------------------------------

    # MACRO / MICRO

    # --------------------------------------------------------

    if document_type in {

        "macro_test_report",

        "microstructure_test_report",

    }:

        if _has_value(result.get("observation")):

            return True



        if _has_value(conformity):

            return True



        return False



    # Unknown report type: keep the rule result and avoid an expensive

    # AI call unless there is literally no extracted information.

    return bool(result)





# ============================================================

# AI NORMALIZATION / SAFE MERGE

# ============================================================





def _merge_if_missing(

    result: dict,

    key: str,

    ai_value: Any,

    filled_fields: list,

) -> None:

    """AI may fill an empty field, but never overwrite rule data."""



    if not _has_value(ai_value):

        return



    if _has_value(result.get(key)):

        return



    result[key] = ai_value

    _append_unique(filled_fields, key)







def _merge_impact_ai(

    result: dict,

    ai_results: dict,

    ai_requirements: dict,

    filled_fields: list,

) -> None:

    _merge_if_missing(

        result,

        "readings",

        ai_results.get("readings"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "average",

        ai_results.get("average"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "temperature_c",

        ai_results.get("temperature_c"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "specimen_size",

        ai_results.get("specimen_size"),

        filled_fields,

    )



    single_minimum = (

        ai_requirements.get("single_minimum")

        or ai_requirements.get("single_minimum_j")

    )

    average_minimum = (

        ai_requirements.get("average_minimum")

        or ai_requirements.get("average_minimum_j")

    )



    _merge_if_missing(

        result,

        "single_minimum",

        single_minimum,

        filled_fields,

    )

    _merge_if_missing(

        result,

        "average_minimum",

        average_minimum,

        filled_fields,

    )







def _merge_chemical_ai(

    result: dict,

    ai_results: dict,

    ai_requirements: dict,

    filled_fields: list,

) -> None:

    existing_elements = result.get("elements")



    if not isinstance(existing_elements, dict):

        existing_elements = {}

        result["elements"] = existing_elements



    # AI may return chemical data under several reasonable keys.

    ai_elements = (

        ai_results.get("elements")

        or ai_results.get("chemical_elements")

        or {}

    )



    if not isinstance(ai_elements, dict):

        return



    requirement_elements = ai_requirements.get("elements", {})

    if not isinstance(requirement_elements, dict):

        requirement_elements = {}



    for element_name, ai_element in ai_elements.items():

        if element_name in existing_elements:

            continue



        if isinstance(ai_element, dict):

            merged_element = dict(ai_element)

        else:

            merged_element = {

                "result": ai_element,

            }



        req = requirement_elements.get(element_name)

        if isinstance(req, dict):

            if "minimum" not in merged_element and req.get("minimum") is not None:

                merged_element["minimum"] = req.get("minimum")

            if "maximum" not in merged_element and req.get("maximum") is not None:

                merged_element["maximum"] = req.get("maximum")



        existing_elements[element_name] = merged_element

        _append_unique(filled_fields, f"elements.{element_name}")







def _merge_tensile_ai(

    result: dict,

    ai_results: dict,

    filled_fields: list,

) -> None:

    parameters = result.get("parameters")



    if not isinstance(parameters, list):

        parameters = []

        result["parameters"] = parameters



    if parameters:

        return



    ai_parameters = ai_results.get("parameters")



    if isinstance(ai_parameters, list) and ai_parameters:

        result["parameters"] = ai_parameters

        _append_unique(filled_fields, "parameters")

        return



    # If the model returned named tensile fields instead of a list,

    # preserve them in a structured fallback object without guessing.

    named_fields = {

        key: ai_results.get(key)

        for key in (

            "yield_strength",

            "yield_strength_mpa",

            "tensile_strength",

            "tensile_strength_mpa",

            "uts",

            "elongation",

            "elongation_percent",

            "reduction_of_area",

            "reduction_of_area_percent",

        )

        if _has_value(ai_results.get(key))

    }



    if named_fields:

        result["ai_tensile_values"] = named_fields

        _append_unique(filled_fields, "ai_tensile_values")







def _merge_hardness_ai(

    result: dict,

    ai_results: dict,

    ai_requirements: dict,

    filled_fields: list,

) -> None:

    _merge_if_missing(

        result,

        "readings",

        ai_results.get("readings"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "average",

        ai_results.get("average"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "scale",

        ai_results.get("scale"),

        filled_fields,

    )



    requirement_text = (

        ai_requirements.get("requirement_text")

        or ai_requirements.get("hardness_requirement")

        or ai_requirements.get("maximum")

        or ai_requirements.get("minimum")

    )



    if requirement_text is not None:

        _merge_if_missing(

            result,

            "requirement_text",

            str(requirement_text),

            filled_fields,

        )







def _merge_proof_load_ai(

    result: dict,

    ai_results: dict,

    ai_requirements: dict,

    filled_fields: list,

) -> None:

    applied = (

        ai_results.get("applied_load_kn")

        or ai_results.get("applied_load")

    )



    required = (

        ai_requirements.get("required_load_kn")

        or ai_requirements.get("required_load")

        or ai_results.get("required_load_kn")

        or ai_results.get("required_load")

    )



    _merge_if_missing(

        result,

        "applied_load_kn",

        applied,

        filled_fields,

    )

    _merge_if_missing(

        result,

        "required_load_kn",

        required,

        filled_fields,

    )







def _merge_metallography_ai(

    result: dict,

    ai_results: dict,

    ai_requirements: dict,

    filled_fields: list,

) -> None:

    _merge_if_missing(

        result,

        "specimen_orientation",

        ai_results.get("specimen_orientation"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "observation",

        ai_results.get("observation"),

        filled_fields,

    )

    _merge_if_missing(

        result,

        "etchant",

        ai_results.get("etchant"),

        filled_fields,

    )



    acceptance = (

        ai_requirements.get("acceptance_criteria")

        or ai_requirements.get("requirement")

    )



    _merge_if_missing(

        result,

        "acceptance_criteria",

        acceptance,

        filled_fields,

    )







def _merge_ai_result(

    document_type: str,

    rule_result: dict,

    ai_data: dict,

) -> dict:

    """

    Merge only missing values from high-confidence AI output.

    Existing deterministic values always win.

    """



    result = dict(rule_result or {})

    filled_fields: list[str] = []



    ai_results = ai_data.get("results", {})

    if not isinstance(ai_results, dict):

        ai_results = {}



    ai_requirements = ai_data.get("requirements", {})

    if not isinstance(ai_requirements, dict):

        ai_requirements = {}



    if document_type == "impact_test_report":

        _merge_impact_ai(

            result,

            ai_results,

            ai_requirements,

            filled_fields,

        )



    elif document_type == "chemical_test_report":

        _merge_chemical_ai(

            result,

            ai_results,

            ai_requirements,

            filled_fields,

        )



    elif document_type == "tensile_test_report":

        _merge_tensile_ai(

            result,

            ai_results,

            filled_fields,

        )



    elif document_type == "hardness_test_report":

        _merge_hardness_ai(

            result,

            ai_results,

            ai_requirements,

            filled_fields,

        )



    elif document_type == "proof_load_test_report":

        _merge_proof_load_ai(

            result,

            ai_results,

            ai_requirements,

            filled_fields,

        )



    elif document_type in {

        "macro_test_report",

        "microstructure_test_report",

    }:

        _merge_metallography_ai(

            result,

            ai_results,

            ai_requirements,

            filled_fields,

        )



    # These are useful metadata. They are added only when the existing

    # rule extractor has not already provided a value with the same key.

    for key in (

        "lab_no",

        "heat_no",

        "specification",

        "test_method",

    ):

        _merge_if_missing(

            result,

            key,

            ai_data.get(key),

            filled_fields,

        )



    _merge_if_missing(

        result,

        "reported_conformity",

        ai_data.get("reported_conformity"),

        filled_fields,

    )



    result["ai_filled_fields"] = filled_fields

    result["ai_confidence"] = _confidence(ai_data.get("confidence"))



    return result





# ============================================================

# REVIEW FLAGS

# ============================================================





def _set_review_flags(

    document_type: str,

    result: dict,

) -> None:

    """Mark incomplete result extraction for human review."""



    reasons: list[str] = []



    if document_type == "impact_test_report":

        readings = [

            value

            for value in result.get("readings", [])

            if value is not None

        ]



        if len(readings) < 3:

            reasons.append(

                "Could not reliably extract all impact readings."

            )



    elif document_type == "chemical_test_report":

        if not result.get("elements"):

            reasons.append(

                "Could not reliably extract chemical element results."

            )



    elif document_type == "tensile_test_report":

        if (

            not result.get("parameters")

            and not result.get("ai_tensile_values")

        ):

            reasons.append(

                "Could not reliably extract tensile result parameters."

            )



    elif document_type == "hardness_test_report":

        if (

            not result.get("readings")

            and result.get("average") is None

        ):

            reasons.append(

                "Could not reliably extract hardness results."

            )



    elif document_type == "proof_load_test_report":

        if result.get("applied_load_kn") is None:

            reasons.append(

                "Could not reliably extract applied proof load."

            )



    elif document_type in {

        "macro_test_report",

        "microstructure_test_report",

    }:

        if not _has_value(result.get("observation")):

            reasons.append(

                "Could not reliably extract metallography observation."

            )



    if reasons:

        result["needs_review"] = True

        result["review_reason"] = " ".join(reasons)

    else:

        result["needs_review"] = False

        result.pop("review_reason", None)





# ============================================================

# MAIN EXTRACTION ENTRY POINT

# ============================================================





def extract_with_fallback(

    document_type: str,

    text: str,

) -> dict:

    """

    Fast extraction flow:



        1. Existing deterministic parser first.

        2. If it extracted usable test-result data -> SKIP AI.

        3. If actual result extraction substantially failed -> one AI call.

        4. AI can fill missing fields only.

        5. Existing deterministic values are never overwritten.



    This prevents Ollama from being called on every normal report page.

    """



    text = text or ""



    # --------------------------------------------------------

    # 1. RULE-BASED EXTRACTION FIRST

    # --------------------------------------------------------

    rule_result = extract_test_results(

        document_type,

        text,

    )



    if not isinstance(rule_result, dict):

        rule_result = {}



    result = dict(rule_result)

    result["extraction_source"] = "rules"

    result["ai_used"] = False



    # --------------------------------------------------------

    # 2. FAST PATH — DO NOT CALL OLLAMA

    # --------------------------------------------------------

    if _deterministic_result_is_usable(

        document_type,

        result,

    ):

        print(

            f"AI skipped: deterministic extraction sufficient "

            f"for {document_type}."

        )



        _set_review_flags(

            document_type,

            result,

        )



        return result



    # --------------------------------------------------------

    # 3. AI DISABLED — RETURN RULE RESULT

    # --------------------------------------------------------

    if not AI_REPORT_FALLBACK_ENABLED:

        print(

            f"AI skipped: report fallback disabled for "

            f"{document_type}."

        )



        _set_review_flags(

            document_type,

            result,

        )



        return result



    # Avoid wasting an LLM call on nearly empty or obviously useless text.

    if len(text.strip()) < 80:

        print(

            f"AI skipped: not enough report text for {document_type}."

        )



        _set_review_flags(

            document_type,

            result,

        )



        return result



    # --------------------------------------------------------

    # 4. TRUE AI FALLBACK — ONE CALL FOR THIS REPORT TEXT

    # --------------------------------------------------------

    print(

        f"AI needed: deterministic extraction incomplete for "

        f"{document_type}."

    )



    ai_data = extract_test_report_with_ai(

        document_type,

        text,

    )



    if not isinstance(ai_data, dict) or not ai_data:

        print(

            f"AI fallback returned no usable data for {document_type}."

        )



        _set_review_flags(

            document_type,

            result,

        )



        return result



    ai_confidence = _confidence(

        ai_data.get("confidence")

    )



    if ai_confidence < AI_MIN_CONFIDENCE:

        print(

            f"AI ignored: confidence {ai_confidence:.2f} is below "

            f"{AI_MIN_CONFIDENCE:.2f} for {document_type}."

        )



        result["ai_used"] = True

        result["ai_confidence"] = ai_confidence

        result["ai_accepted"] = False



        _set_review_flags(

            document_type,

            result,

        )



        return result



    # --------------------------------------------------------

    # 5. HIGH-CONFIDENCE, MISSING-ONLY MERGE

    # --------------------------------------------------------

    result = _merge_ai_result(

        document_type,

        result,

        ai_data,

    )



    result["ai_used"] = True

    result["ai_accepted"] = True



    if result.get("ai_filled_fields"):

        result["extraction_source"] = "rules+ai"

    else:

        result["extraction_source"] = "rules"



    _set_review_flags(

        document_type,

        result,

    )



    return result
