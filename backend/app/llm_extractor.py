import json

import os
import time

from typing import Any



import ollama





# ============================================================

# SETTINGS

# ============================================================



OLLAMA_MODEL = os.getenv(

    "OLLAMA_MODEL",

    "qwen2.5:3b-instruct"

)



AI_ENABLED = (

    os.getenv(

        "AI_ENABLED",

        "true"

    ).lower()

    == "true"

)



AI_MIN_CONFIDENCE = 0.75



MAX_PO_TEXT = 10000

MAX_JOB_TEXT = 14000

MAX_REPORT_TEXT = 9000

AI_TIMEOUT_SECONDS = float(
    os.getenv("OLLAMA_TIMEOUT_SECONDS", "15")
)

AI_COOLDOWN_SECONDS = float(
    os.getenv("OLLAMA_COOLDOWN_SECONDS", "60")
)

_OLLAMA_UNAVAILABLE_UNTIL = 0.0






# ============================================================

# HELPERS

# ============================================================



def _safe_json(

    value: str

) -> dict:



    if not value:

        return {}



    try:



        parsed = json.loads(

            value

        )



        if isinstance(

            parsed,

            dict

        ):

            return parsed



    except Exception as exc:



        print(

            "AI JSON parsing error:",

            exc

        )



    return {}





def _normalize_confidence(

    value: Any

) -> float:



    try:



        confidence = float(

            value

        )



    except (

        TypeError,

        ValueError

    ):



        return 0.0



    return max(

        0.0,

        min(

            confidence,

            1.0

        )

    )





def _normalize_list(

    value: Any

) -> list:



    if not isinstance(

        value,

        list

    ):

        return []



    result = []



    for item in value:



        if item is None:

            continue



        if isinstance(

            item,

            str

        ):



            item = item.strip()



            if not item:

                continue



        if item not in result:



            result.append(

                item

            )



    return result





# ============================================================

# OLLAMA CALL

# ============================================================



def _call_ollama(
    prompt: str
) -> dict:
    """
    Local AI extraction with a hard network timeout.

    AI is optional. If Ollama is slow/unavailable, deterministic analysis
    continues instead of leaving /analyze-job hanging.
    """
    global _OLLAMA_UNAVAILABLE_UNTIL

    if not AI_ENABLED:
        print("AI disabled. Skipping Ollama.")
        return {}

    now = time.monotonic()
    if now < _OLLAMA_UNAVAILABLE_UNTIL:
        remaining = int(_OLLAMA_UNAVAILABLE_UNTIL - now)
        print(f"AI skipped: Ollama cooldown active ({remaining}s remaining).")
        return {}

    try:
        print(
            f"AI fallback: using {OLLAMA_MODEL} "
            f"(timeout {AI_TIMEOUT_SECONDS:g}s)"
        )

        client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            timeout=AI_TIMEOUT_SECONDS,
        )

        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise industrial material testing "
                        "laboratory document extraction assistant. "
                        "Extract only information explicitly supported by "
                        "the supplied document. Never invent missing values. "
                        "Never determine PASS, FAIL, MISSING or REVIEW. "
                        "Return concise JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format="json",
            options={
                "temperature": 0,
                "num_ctx": 4096,
            },
            keep_alive="30m",
        )

        message = response.get("message", {})
        content = message.get("content", "")
        result = _safe_json(content)

        print("AI extraction completed.")
        return result

    except Exception as exc:
        _OLLAMA_UNAVAILABLE_UNTIL = (
            time.monotonic() + AI_COOLDOWN_SECONDS
        )
        print(
            "Ollama AI extraction failed or timed out. "
            "Continuing with deterministic extraction:",
            exc,
        )
        return {}


# ============================================================

# PURCHASE ORDER

# ============================================================



def extract_purchase_order_with_ai(

    text: str

) -> dict:



    text = (

        text or ""

    )[:MAX_PO_TEXT]



    if not text.strip():



        return {

            "po_numbers": [],

            "customer_name": None,

            "heat_numbers": [],

            "material_grade": None,

            "specifications": [],

            "required_tests": [],

            "confidence": 0.0,

            "uncertain_fields": []

        }



    prompt = f"""

Extract structured information from this Purchase Order,

Offer Letter or client requirement document.



IMPORTANT:



- Extract only visible/supported information.

- Never guess.

- There may be zero, one or multiple PO numbers.

- Return ALL confidently identified PO numbers.

- PO number is metadata only.

- Do not confuse PO numbers with Heat Numbers.

- Do not decide compliance.

- Separate specification from test method.

- If uncertain, use null or an empty list.



Required test names MUST use these identifiers only:



chemical_test_report

impact_test_report

tensile_test_report

hardness_test_report

proof_load_test_report

macro_test_report

microstructure_test_report

bend_test_report
ferrite_test_report
corrosion_test_report



Return JSON:



{{

    "po_numbers": [],

    "customer_name": null,

    "heat_numbers": [],

    "material_grade": null,

    "specifications": [],

    "required_tests": [],

    "confidence": 0.0,

    "uncertain_fields": []

}}



DOCUMENT:



{text}

"""



    data = _call_ollama(

        prompt

    )



    return {

        "po_numbers":

            _normalize_list(

                data.get(

                    "po_numbers"

                )

            ),



        "customer_name":

            data.get(

                "customer_name"

            ),



        "heat_numbers":

            _normalize_list(

                data.get(

                    "heat_numbers"

                )

            ),



        "material_grade":

            data.get(

                "material_grade"

            ),



        "specifications":

            _normalize_list(

                data.get(

                    "specifications"

                )

            ),



        "required_tests":

            _normalize_list(

                data.get(

                    "required_tests"

                )

            ),



        "confidence":

            _normalize_confidence(

                data.get(

                    "confidence"

                )

            ),



        "uncertain_fields":

            _normalize_list(

                data.get(

                    "uncertain_fields"

                )

            )

    }





# ============================================================

# JOB ORDER

# ============================================================



def extract_job_order_with_ai(

    text: str

) -> dict:



    text = (

        text or ""

    )[:MAX_JOB_TEXT]



    if not text.strip():



        return {

            "collection_no": None,

            "labs": [],

            "confidence": 0.0,

            "uncertain_fields": []

        }



    prompt = f"""

Extract structured information from this laboratory Job Order.



PRIMARY GOAL:



For every Lab Number identify:



1. Lab Number

2. Heat Number

3. Every required test

4. Specification if explicitly present

5. Test methods if explicitly present

6. Requirements if explicitly present



IMPORTANT:



- Never invent values.

- Never combine two Lab Numbers.

- Never decide PASS or FAIL.

- A specification is different from a test method.

- A requirement is different from an actual result.

- If uncertain, return null.

- Do not add a test merely because it is common for the material.



Required test identifiers:



chemical_test_report

impact_test_report

tensile_test_report

hardness_test_report

proof_load_test_report

macro_test_report

microstructure_test_report

bend_test_report
ferrite_test_report
corrosion_test_report



Return JSON:



{{

    "collection_no": null,



    "labs": [

        {{

            "lab_no": null,

            "heat_no": null,

            "required_tests": [],

            "specification": null,

            "test_methods": {{}},

            "requirements": {{}}

        }}

    ],



    "confidence": 0.0,

    "uncertain_fields": []

}}



JOB ORDER:



{text}

"""



    data = _call_ollama(

        prompt

    )



    labs = data.get(

        "labs",

        []

    )



    if not isinstance(

        labs,

        list

    ):



        labs = []



    clean_labs = []



    for lab in labs:



        if not isinstance(

            lab,

            dict

        ):

            continue



        clean_labs.append({

            "lab_no":

                lab.get(

                    "lab_no"

                ),



            "heat_no":

                lab.get(

                    "heat_no"

                ),



            "required_tests":

                _normalize_list(

                    lab.get(

                        "required_tests"

                    )

                ),



            "specification":

                lab.get(

                    "specification"

                ),



            "test_methods":

                lab.get(

                    "test_methods"

                )

                if isinstance(

                    lab.get(

                        "test_methods"

                    ),

                    dict

                )

                else {},



            "requirements":

                lab.get(

                    "requirements"

                )

                if isinstance(

                    lab.get(

                        "requirements"

                    ),

                    dict

                )

                else {}

        })



    return {

        "collection_no":

            data.get(

                "collection_no"

            ),



        "labs":

            clean_labs,



        "confidence":

            _normalize_confidence(

                data.get(

                    "confidence"

                )

            ),



        "uncertain_fields":

            _normalize_list(

                data.get(

                    "uncertain_fields"

                )

            )

    }





# ============================================================

# TEST REPORT

# ============================================================



def extract_test_report_with_ai(

    document_type: str,

    text: str

) -> dict:



    text = (

        text or ""

    )[:MAX_REPORT_TEXT]



    if not text.strip():



        return {

            "lab_no": None,

            "heat_no": None,

            "specification": None,

            "test_method": None,

            "requirements": {},

            "results": {},

            "reported_conformity": None,

            "confidence": 0.0,

            "uncertain_fields": []

        }



    prompt = f"""

Extract structured information from this industrial

material test report.



EXPECTED TEST TYPE:



{document_type}



Extract:



- Lab Number

- Heat Number

- Specification

- Test Method

- Requirements

- Actual Results

- Reported Statement of Conformity



IMPORTANT:



Do not decide PASS or FAIL.



Never invent a value.



Keep these concepts separate:



SPECIFICATION

Example:

ASTM A193/A193M:2026 Grade B7



TEST METHOD

Example:

ASTM E92:2023



REQUIREMENT

Example:

34 max



ACTUAL RESULT

Example:

28.18



For impact testing, extract when available:



- readings

- average

- temperature_c

- specimen_size

- single minimum requirement

- average minimum requirement



For hardness testing:



- readings

- average

- scale

- converted readings if shown

- minimum/maximum requirement



For tensile testing:



- yield strength

- tensile strength / UTS

- elongation

- reduction of area

- corresponding requirements



For proof load:



- applied load

- required load

- units



For chemical testing:



- elements

- actual percentages

- minimum/maximum limits



For macro/microstructure:



- observation

- requirement/acceptance criteria

- etchant if shown



If a value is unreadable or uncertain, return null.



Return JSON:



{{

    "lab_no": null,

    "heat_no": null,



    "specification": null,

    "test_method": null,



    "requirements": {{}},



    "results": {{}},



    "reported_conformity": null,



    "confidence": 0.0,

    "uncertain_fields": []

}}



REPORT:



{text}

"""



    data = _call_ollama(

        prompt

    )



    requirements = data.get(

        "requirements",

        {}

    )



    if not isinstance(

        requirements,

        dict

    ):



        requirements = {}



    results = data.get(

        "results",

        {}

    )



    if not isinstance(

        results,

        dict

    ):



        results = {}



    return {

        "lab_no":

            data.get(

                "lab_no"

            ),



        "heat_no":

            data.get(

                "heat_no"

            ),



        "specification":

            data.get(

                "specification"

            ),



        "test_method":

            data.get(

                "test_method"

            ),



        "requirements":

            requirements,



        "results":

            results,



        "reported_conformity":

            data.get(

                "reported_conformity"

            ),



        "confidence":

            _normalize_confidence(

                data.get(

                    "confidence"

                )

            ),



        "uncertain_fields":

            _normalize_list(

                data.get(

                    "uncertain_fields"

                )

            )

    }