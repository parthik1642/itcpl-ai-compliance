import re





def safe_float(value):

    if value is None:

        return None



    value = str(value).replace(",", ".")

    value = re.sub(r"[^0-9.\-]", "", value)



    if value in ["", ".", "-", "-."]:

        return None



    try:

        return float(value)

    except ValueError:

        return None





def extract_reported_conformity(text: str):

    lower = (text or "").lower()



    fail_markers = [

        "does not meets the customer",

        "does not meet the customer",

        "does not meet customer",

        "not meets the customer",

        "not meet the customer",

        "does not conform",

        "not conform",

    ]



    if any(marker in lower for marker in fail_markers):

        return "FAIL"



    pass_markers = [

        "meets the customers requirement",

        "meets the customer requirement",

        "meets customer requirement",

        "meets the requirement",

        "result meets the customers requirement",

        "result meets the customer",

        "test results are accepted",

        "test result is accepted",

        "results are accepted as per",

    ]



    if any(marker in lower for marker in pass_markers):

        return "PASS"



    return None





def _extract_temperature(text: str):

    match = re.search(

        r"(?:Impact\s*Test[^\n]{0,80}?|"

        r"Testing\s*Temperature[^\n]{0,30}?)"

        r"(-?\s*\d+)\s*°?\s*C",

        text,

        re.IGNORECASE,

    )



    if not match:

        match = re.search(

            r"(-\s*29)\s*°?\s*C",

            text,

            re.IGNORECASE

        )



    return safe_float(

        match.group(1)

    ) if match else None





def extract_impact_test(text: str) -> dict:

    data = {

        "readings": [],

        "average": None,

        "single_minimum": None,

        "average_minimum": None,

        "temperature_c": _extract_temperature(text),

        "reported_conformity":

            extract_reported_conformity(text),

    }



    match = re.search(

        r"Energy\s*Absorbed\s*\(Joules\).*?"

        r"(-?\d+(?:[.,]\d+)?)\s+"

        r"(-?\d+(?:[.,]\d+)?)\s+"

        r"(-?\d+(?:[.,]\d+)?)\s+"

        r"(-?\d+(?:[.,]\d+)?)",

        text,

        re.IGNORECASE | re.DOTALL,

    )



    if match:

        data["readings"] = [

            safe_float(match.group(i))

            for i in range(1, 4)

        ]



        data["average"] = safe_float(

            match.group(4)

        )



    single = re.search(

        r"Single\s*Minimum\s*[:\-]?\s*"

        r"(\d+(?:[.,]\d+)?)",

        text,

        re.IGNORECASE,

    )



    if single:

        data["single_minimum"] = safe_float(

            single.group(1)

        )



    average = re.search(

        r"Average\s*Minimum\s*[:\-]?\s*"

        r"(\d+(?:[.,]\d+)?)",

        text,

        re.IGNORECASE,

    )



    if average:

        data["average_minimum"] = safe_float(

            average.group(1)

        )



    if (

        data["single_minimum"] is None

        or data["average_minimum"] is None

    ):

        note = re.search(

            r"Single\s*Minimum\D{0,12}"

            r"(\d+(?:[.,]\d+)?).*?"

            r"Average\s*Minimum\D{0,12}"

            r"(\d+(?:[.,]\d+)?)",

            text,

            re.IGNORECASE | re.DOTALL,

        )



        if note:

            data["single_minimum"] = (

                data["single_minimum"]

                or safe_float(note.group(1))

            )



            data["average_minimum"] = (

                data["average_minimum"]

                or safe_float(note.group(2))

            )



    # OCR sometimes joins the unit "J" to the requirement as a trailing 1

    # (for example 26 J -> 261, 34 J -> 341). Correct only when the signed

    # report says PASS and the uncorrected value contradicts all readings.

    if data.get("reported_conformity") == "PASS" and data.get("readings"):

        for key in ("single_minimum", "average_minimum"):

            value = data.get(key)

            if value is not None and value >= 150 and int(value) % 10 == 1:

                corrected = int(value) // 10

                if corrected <= max(v for v in data["readings"] if v is not None):

                    data[key] = float(corrected)



    return data





def extract_chemical_test(text: str) -> dict:

    elements = {}



    aliases = {

        "carbon": ("Carbon", "C"),

        "silicon": ("Silicon", "Si"),

        "manganese": ("Manganese", "Mn"),

        "phosphorus": ("Phosphorus", "P"),

        "sulphur": ("Sulphur", "S"),

        "chromium": ("Chromium", "Cr"),

        "molybdenum": ("Molybdenum", "Mo"),

        "nickel": ("Nickel", "Ni"),

    }



    for key, (name, symbol) in aliases.items():



        range_match = re.search(

            rf"%?\s*{name}\s*\({symbol}\).*?"

            rf"(-?\d+(?:[.,]\d+)?)\s+"

            rf"(-?\d+(?:[.,]\d+)?)\s*[-–]\s*"

            rf"(-?\d+(?:[.,]\d+)?)",

            text,

            re.IGNORECASE,

        )



        if range_match:

            elements[key] = {

                "result":

                    safe_float(

                        range_match.group(1)

                    ),



                "minimum":

                    safe_float(

                        range_match.group(2)

                    ),



                "maximum":

                    safe_float(

                        range_match.group(3)

                    ),

            }



            continue



        max_match = re.search(

            rf"%?\s*{name}\s*\({symbol}\).*?"

            rf"(-?\d+(?:[.,]\d+)?)\s+"

            rf"(-?\d+(?:[.,]\d+)?)\s*"

            rf"(?:max\.?|maximum)",

            text,

            re.IGNORECASE,

        )



        if max_match:

            elements[key] = {

                "result":

                    safe_float(

                        max_match.group(1)

                    ),



                "maximum":

                    safe_float(

                        max_match.group(2)

                    ),

            }



    reported = extract_reported_conformity(text)



    # Scanned reports occasionally lose a decimal point (0.509 -> 509).

    # Use the signed PASS statement only as an OCR disambiguator, then retain

    # the corrected numeric value for independent limit checking.

    if reported == "PASS":

        for values in elements.values():

            result = values.get("result")

            maximum = values.get("maximum")

            if result is None or maximum is None or maximum <= 0:

                continue

            corrected = result

            while corrected > maximum * 10 and corrected >= 10:

                corrected /= 10.0

            if corrected <= maximum and corrected != result:

                values["result"] = corrected

                values["ocr_decimal_corrected"] = True



    return {

        "elements": elements,

        "reported_conformity": reported,

    }





def _extract_parameter_rows(

    text: str,

    parameter_names: list[str]

) -> list[dict]:



    rows = []



    lines = [

        re.sub(

            r"\s+",

            " ",

            line

        ).strip()

        for line in (text or "").splitlines()

    ]



    for parameter in parameter_names:



        for line in lines:



            if parameter.lower() not in line.lower():

                continue



            numbers = [

                safe_float(v)

                for v in re.findall(

                    r"-?\d+(?:[.,]\d+)?",

                    line

                )

            ]



            numbers = [

                v

                for v in numbers

                if v is not None

            ]



            if numbers:

                rows.append({

                    "parameter":

                        parameter,



                    "values":

                        numbers,



                    "raw":

                        line,

                })



            break



    return rows





def _normalized_text(text: str) -> str:

    """

    Collapse PDF table line-breaks into spaces.



    This is important because PyMuPDF often returns a visual row like:

        Ultimate Tensile Load(kN) 783.600 678 min.

    as:

        Ultimate Tensile

        Load(kN)

        783.600

        678 min.

    """

    return re.sub(

        r"\s+",

        " ",

        text or ""

    ).strip()





def _extract_requirement_from_fragment(fragment: str) -> dict:

    fragment = fragment or ""



    range_match = re.search(

        r"(-?\d+(?:[.,]\d+)?)\s*[-–]\s*"

        r"(-?\d+(?:[.,]\d+)?)",

        fragment,

        re.IGNORECASE

    )



    if range_match:

        return {

            "minimum":

                safe_float(

                    range_match.group(1)

                ),

            "maximum":

                safe_float(

                    range_match.group(2)

                ),

            "requirement_type":

                "range",

            "requirement_text":

                range_match.group(0).strip(),

        }



    min_match = re.search(

        r"(-?\d+(?:[.,]\d+)?)\s*"

        r"(?:min\.?|minimum)",

        fragment,

        re.IGNORECASE

    )



    if min_match:

        return {

            "minimum":

                safe_float(

                    min_match.group(1)

                ),

            "maximum":

                None,

            "requirement_type":

                "minimum",

            "requirement_text":

                min_match.group(0).strip(),

        }



    max_match = re.search(

        r"(-?\d+(?:[.,]\d+)?)\s*"

        r"(?:max\.?|maximum)",

        fragment,

        re.IGNORECASE

    )



    if max_match:

        return {

            "minimum":

                None,

            "maximum":

                safe_float(

                    max_match.group(1)

                ),

            "requirement_type":

                "maximum",

            "requirement_text":

                max_match.group(0).strip(),

        }



    return {

        "minimum": None,

        "maximum": None,

        "requirement_type": None,

        "requirement_text": None,

    }





def _numbers_from_text(value: str) -> list[float]:

    numbers = []



    for token in re.findall(

        r"-?\d+(?:[.,]\d+)?",

        value or ""

    ):

        parsed = safe_float(

            token

        )



        if parsed is not None:

            numbers.append(

                parsed

            )



    return numbers





def _parameter_fragment(

    normalized_text: str,

    aliases: list[str],

    max_chars: int = 140

):

    """

    Return text immediately AFTER a parameter label.



    The search operates on whitespace-normalized text, therefore it

    works whether a PDF table row was returned on one line or split

    across many lines.

    """

    best = None



    for alias in aliases:

        pattern = re.compile(

            re.escape(alias),

            re.IGNORECASE

        )



        match = pattern.search(

            normalized_text

        )



        if not match:

            continue



        fragment = normalized_text[

            match.end():

            match.end() + max_chars

        ]



        candidate = {

            "alias":

                alias,

            "fragment":

                fragment,

            "start":

                match.start(),

        }



        if (

            best is None

            or candidate["start"] <

            best["start"]

        ):

            best = candidate



    return best





def extract_tensile_test(text: str) -> dict:

    """

    Extract tensile result values from ITCPL-style PDF tables.



    Handles both normal rows and rows broken across PDF text lines.



    Examples:

        Ultimate Tensile Load(kN) 783.600 678 min.

        U.T.S (MPa) 959.119

        Yield Strength (MPa) 650 600 min.

        Elongation (%) 18 12 min.

    """



    normalized = _normalized_text(

        text

    )



    parameter_specs = [

        {

            "parameter":

                "Ultimate Tensile Load",

            "aliases": [

                "Ultimate Tensile Load",

                "Ultimate Load",

                "Tensile Load",

            ],

            "default_unit":

                "kN",

        },

        {

            "parameter":

                "U.T.S",

            "aliases": [

                "U.T.S",

                "UTS",

                "Ultimate Tensile Strength",

                "Tensile Strength",

            ],

            "default_unit":

                "MPa",

        },

        {

            "parameter":

                "Yield Load",

            "aliases": [

                "Yield Load",

            ],

            "default_unit":

                "kN",

        },

        {

            "parameter":

                "Yield Strength",

            "aliases": [

                "Yield Strength",

                "0.2% Proof Stress",

                "0.2 Proof Stress",

                "Proof Stress",

            ],

            "default_unit":

                "MPa",

        },

        {

            "parameter":

                "Elongation",

            "aliases": [

                "Elongation",

            ],

            "default_unit":

                "%",

        },

        {

            "parameter":

                "Reduction of Area",

            "aliases": [

                "Reduction of Area",

                "Reduction",

            ],

            "default_unit":

                "%",

        },

    ]



    parameters = []



    stop_markers = [

        "Statement of conformity",

        "Test Witnessed By",

        "Test Name",

        "Equipment",

        "END OF REPORT",

    ]



    for spec in parameter_specs:



        found = _parameter_fragment(

            normalized,

            spec["aliases"],

            max_chars=160

        )



        if not found:

            continue



        fragment = found[

            "fragment"

        ]



        # Stop before another report section starts.

        lower_fragment = (

            fragment.lower()

        )



        stop_positions = []



        for marker in stop_markers:

            pos = lower_fragment.find(

                marker.lower()

            )



            if pos >= 0:

                stop_positions.append(

                    pos

                )



        if stop_positions:

            fragment = fragment[

                :min(stop_positions)

            ]



        # Do not let the next known tensile parameter become part

        # of this parameter's result fragment.

        for other_spec in parameter_specs:

            for alias in other_spec[

                "aliases"

            ]:

                if (

                    alias.lower()

                    in [

                        item.lower()

                        for item in spec[

                            "aliases"

                        ]

                    ]

                ):

                    continue



                pos = fragment.lower().find(

                    alias.lower()

                )



                if pos > 0:

                    fragment = (

                        fragment[:pos]

                    )



        numbers = _numbers_from_text(

            fragment

        )



        if not numbers:

            continue



        # Unit can appear directly after the label.

        unit = spec[

            "default_unit"

        ]



        unit_match = re.search(

            r"^\s*\(?\s*"

            r"(kN|MPa|N/mm(?:2|²)|%)"

            r"\s*\)?",

            fragment,

            re.IGNORECASE

        )



        if unit_match:

            unit = unit_match.group(

                1

            )



            if unit.lower() in {

                "n/mm2",

                "n/mm²",

            }:

                unit = "MPa"



        requirement = (

            _extract_requirement_from_fragment(

                fragment

            )

        )



        # Requirement values normally appear at the end of the row.

        # Use the last non-requirement number as the actual result. This

        # avoids treating the "0.2" in "0.2% Proof Stress" as the result.

        req_count = 2 if requirement.get("requirement_type") == "range" else (

            1 if requirement.get("requirement_type") in {"minimum", "maximum"} else 0

        )

        result_candidates = numbers[:-req_count] if req_count and len(numbers) > req_count else list(numbers)

        result_value = result_candidates[-1] if result_candidates else numbers[0]



        parameters.append({

            "parameter":

                spec["parameter"],



            "result":

                result_value,



            # Keep values as well for backward compatibility with

            # existing frontend/pipeline code.

            "values":

                [result_value],



            "unit":

                unit,



            "minimum":

                requirement.get(

                    "minimum"

                ),



            "maximum":

                requirement.get(

                    "maximum"

                ),



            "requirement_type":

                requirement.get(

                    "requirement_type"

                ),



            "requirement_text":

                requirement.get(

                    "requirement_text"

                ),



            "raw":

                fragment.strip(),

        })



    return {

        "parameters":

            parameters,



        "reported_conformity":

            extract_reported_conformity(

                text

            ),

    }



def extract_bend_test(text: str) -> dict:



    data = {

        "bend_angle": None,

        "sample_results": [],

        "reported_conformity":

            extract_reported_conformity(text),

    }



    angle = re.search(

        r"(?:SIDE\s*BEND|BEND)"

        r"[^\n]{0,50}?(\d{2,3})\s*°",

        text,

        re.IGNORECASE

    )



    if angle:

        data["bend_angle"] = safe_float(

            angle.group(1)

        )



    satisfactory_count = len(

        re.findall(

            r"\bSATISFACTORY\b",

            text,

            re.IGNORECASE

        )

    )



    no_opening_count = len(

        re.findall(

            r"NO\s+OPENING\s+OBSERVED",

            text,

            re.IGNORECASE

        )

    )



    if satisfactory_count:

        data["sample_results"] = (

            ["Satisfactory"]

            * satisfactory_count

        )



    if no_opening_count:

        data[

            "no_opening_observed_count"

        ] = no_opening_count



    return data





def extract_hardness_test(text: str) -> dict:

    """

    Extract hardness values from ITCPL-style tables even when a PDF

    splits the visual table row across multiple text lines.



    Examples:

        HRC 30.4 30.8 31.2 30.80 23-34

        HRC 34.5 34.8 35.1 34.80 26 min.

        HV10 281 288 271 281.3 340 max.

    """



    data = {

        "scale":

            None,



        "readings":

            [],



        "average":

            None,



        "minimum":

            None,



        "maximum":

            None,



        "requirement_type":

            None,



        "requirement_text":

            None,



        "reported_conformity":

            extract_reported_conformity(

                text

            ),

    }



    normalized = _normalized_text(

        text

    )



    # First preference:

    # locate the result row after the familiar table heading.

    search_regions = []



    heading_match = re.search(

        r"(?:Parameter\s+)?"

        r"Reading\s*1.*?"

        r"Reading\s*2.*?"

        r"Reading\s*3.*?"

        r"Average"

        r"(?:\s+Requirement)?",

        normalized,

        re.IGNORECASE

    )



    if heading_match:

        search_regions.append(

            normalized[

                heading_match.end():

                heading_match.end() + 180

            ]

        )



    # Do not numerically parse arbitrary occurrences such as equipment

    # names ("Vickers Hardness Machine") because dates/calibration values

    # can look like hardness readings. If the standard reading table is not

    # present, keep the report for conformity/manual review instead.

    if not heading_match:

        search_regions = []



    candidate = None



    scale_pattern = (

        r"\b("

        r"HRC|HRB|HBW|"

        r"HV\s*\d*(?:\.\d+)?|"

        r"VICKERS"

        r")\b"

    )



    for region in search_regions:



        for match in re.finditer(

            scale_pattern,

            region,

            re.IGNORECASE

        ):



            scale = (

                match.group(1)

                .upper()

                .strip()

            )



            fragment = region[

                match.end():

                match.end() + 120

            ]



            if scale.startswith("HBW"):

                fragment = re.sub(

                    r"^\s*\(?\s*\d+(?:\.\d+)?\s*(?:mm)?\s*/\s*\d+(?:\.\d+)?\s*(?:kgf)?\s*\)?",

                    " ",

                    fragment,

                    flags=re.IGNORECASE,

                )



            # End before unrelated report sections.

            stops = []



            for marker in [

                "Statement of conformity",

                "Test Witnessed By",

                "Test Name",

                "Equipment",

                "END OF REPORT",

            ]:

                pos = (

                    fragment

                    .lower()

                    .find(

                        marker.lower()

                    )

                )



                if pos >= 0:

                    stops.append(

                        pos

                    )



            if stops:

                fragment = fragment[

                    :min(stops)

                ]



            numbers = (

                _numbers_from_text(

                    fragment

                )

            )



            requirement = (

                _extract_requirement_from_fragment(

                    fragment

                )

            )



            req_count = 0



            if (

                requirement.get(

                    "requirement_type"

                )

                == "range"

            ):

                req_count = 2



            elif requirement.get(

                "requirement_type"

            ) in {

                "minimum",

                "maximum",

            }:

                req_count = 1



            result_numbers = list(

                numbers

            )



            if (

                req_count

                and len(

                    result_numbers

                ) > req_count

            ):

                result_numbers = (

                    result_numbers[

                        :-req_count

                    ]

                )



            # A strong hardness candidate normally has at least

            # three readings. Prefer the candidate with most result

            # numbers and a recognizable requirement.

            score = len(

                result_numbers

            )



            if requirement.get(

                "requirement_type"

            ):

                score += 3



            if len(

                result_numbers

            ) >= 3:

                score += 5



            current = {

                "scale":

                    scale,

                "fragment":

                    fragment,

                "result_numbers":

                    result_numbers,

                "requirement":

                    requirement,

                "score":

                    score,

            }



            if (

                candidate is None

                or current["score"]

                > candidate["score"]

            ):

                candidate = (

                    current

                )



        if (

            candidate

            and candidate[

                "score"

            ] >= 8

        ):

            break



    if candidate:

        data["scale"] = (

            candidate["scale"]

        )



        result_numbers = (

            candidate[

                "result_numbers"

            ]

        )



        # Typical ITCPL layout:

        # 3 readings + average.

        if len(result_numbers) >= 4:

            data["readings"] = (

                result_numbers[:3]

            )



            data["average"] = (

                result_numbers[3]

            )



        elif len(result_numbers) == 3:

            data["readings"] = (

                result_numbers

            )



            data["average"] = round(

                sum(

                    result_numbers

                ) / 3,

                3

            )



        elif result_numbers:

            data["readings"] = (

                result_numbers

            )



        requirement = (

            candidate[

                "requirement"

            ]

        )



        data["minimum"] = (

            requirement.get(

                "minimum"

            )

        )



        data["maximum"] = (

            requirement.get(

                "maximum"

            )

        )



        data[

            "requirement_type"

        ] = requirement.get(

            "requirement_type"

        )



        data[

            "requirement_text"

        ] = requirement.get(

            "requirement_text"

        )



    else:

        # Metadata-only scale fallback.

        scale_match = re.search(

            r"\b("

            r"HRC|HRB|HBW|"

            r"HV\s*\d+(?:\.\d+)?|"

            r"VICKERS|ROCKWELL"

            r")\b",

            normalized,

            re.IGNORECASE

        )



        if scale_match:

            data["scale"] = (

                scale_match.group(

                    1

                )

                .upper()

                .strip()

            )



    return data



def extract_proof_load_test(

    text: str

) -> dict:



    data = {

        "applied_load_kn": None,

        "required_load_kn": None,

        "reported_conformity":

            extract_reported_conformity(text),

    }



    applied = re.search(

        r"Applied\s*Load\s*(?:\(\s*kN\s*\))?"

        r"\s*[:\-]?\s*"

        r"(\d+(?:[.,]\d+)?)",

        _normalized_text(text),

        re.IGNORECASE

    )



    required = re.search(

        r"Required\s*Load\s*(?:\(\s*kN\s*\))?"

        r"\s*[:\-]?\s*"

        r"(\d+(?:[.,]\d+)?)",

        _normalized_text(text),

        re.IGNORECASE

    )



    if applied:

        data["applied_load_kn"] = (

            safe_float(

                applied.group(1)

            )

        )



    if required:

        data["required_load_kn"] = (

            safe_float(

                required.group(1)

            )

        )



    return data





def extract_metallography_test(

    text: str

) -> dict:



    data = {

        "specimen_orientation": None,

        "observation": None,

        "etchant": None,

        "reported_conformity":

            extract_reported_conformity(text),

    }



    orientation = re.search(

        r"Specimen\s*Orientation"

        r"\s*[:\-]?\s*([^\n]+)",

        text,

        re.IGNORECASE

    )



    observation = re.search(

        r"Observation\s*[:\-]?\s*"

        r"([^\n]+"

        r"(?:\n"

        r"(?!Etchant|Test Witnessed|"

        r"END OF REPORT)"

        r"[^\n]+)?)",

        text,

        re.IGNORECASE

    )



    etchant = re.search(

        r"Etchant\s*[:\-]?\s*"

        r"([^\n]+)",

        text,

        re.IGNORECASE

    )



    if orientation:

        data["specimen_orientation"] = (

            orientation.group(1).strip()

        )



    if observation:

        data["observation"] = re.sub(

            r"\s+",

            " ",

            observation.group(1)

        ).strip()



    if etchant:

        data["etchant"] = (

            etchant.group(1).strip()

        )



    return data





def extract_special_report(text: str) -> dict:

    """Extract conservative evidence for ferrite/corrosion and other signed reports."""

    normalized = _normalized_text(text)

    observation = None

    observation_match = re.search(

        r"(?:Observation|Result)\s*[:\-]?\s*(.{1,220}?)(?=Statement of conformity|Test Witnessed By|END OF REPORT|$)",

        normalized,

        re.IGNORECASE,

    )

    if observation_match:

        observation = observation_match.group(1).strip()



    return {

        "observation": observation,

        "reported_conformity": extract_reported_conformity(text),

    }





# ======================================================

# MAIN TEST RESULT EXTRACTOR

# ======================================================



def extract_test_results(

    document_type: str,

    text: str

) -> dict:



    if document_type == "impact_test_report":



        return extract_impact_test(

            text

        )



    if document_type == "chemical_test_report":



        return extract_chemical_test(

            text

        )



    if document_type == "tensile_test_report":



        return extract_tensile_test(

            text

        )



    if document_type == "bend_test_report":



        return extract_bend_test(

            text

        )



    if document_type == "hardness_test_report":



        return extract_hardness_test(

            text

        )



    if document_type == "proof_load_test_report":



        return extract_proof_load_test(

            text

        )



    if document_type in {

        "macro_test_report",

        "microstructure_test_report"

    }:



        return extract_metallography_test(

            text

        )



    if document_type in {

        "ferrite_test_report",

        "corrosion_test_report",

    }:

        return extract_special_report(text)



    return {}