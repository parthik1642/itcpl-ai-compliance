import json
import re
from datetime import date
from pathlib import Path
from difflib import SequenceMatcher


SCOPE_FILE = Path(__file__).with_name("nabl_scope_tc11952.json")


def _norm(value):
    value = str(value or "").upper()
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"\bEDITION\b|\bED\.?\b", " ", value)
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return " ".join(value.split())


def _method_key(value):
    text = _norm(value)

    # Ignore publication/revision years.
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)

    # Normalize common wording variations.
    text = re.sub(r"\bSECTION\b", "SEC", text)
    text = re.sub(r"\bPART\b", "PT", text)
    text = re.sub(r"\bISSUE\s+NO\b", "ISSUE", text)
    text = re.sub(r"\bISSUE\s+DATE\b.*$", " ", text)

    return " ".join(text.split())


def _words(value):
    return set(_norm(value).split())


def _similar(a, b):
    a = _norm(a)
    b = _norm(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    aw = _words(a)
    bw = _words(b)

    overlap = len(aw & bw) / max(1, len(aw | bw))
    seq = SequenceMatcher(None, a, b).ratio()

    return max(overlap, seq)


def _load_scope():
    with SCOPE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_methods(text):
    text = str(text or "")

    patterns = [
        r"\bASTM\s+[A-Z]\s*\d+(?:\.\d+)?(?:[/-]\d+)?(?:M)?(?:\s*[:\-]\s*\d{4})?\b",

        r"\bBS\s+EN\s+ISO\s+\d+(?:-\d+)*(?:\s*[:\-]\s*\d{4})?\b",

        r"\bEN\s+ISO\s+\d+(?:-\d+)*(?:\s*[:\-]\s*\d{4})?\b",

        r"\bISO\s+\d+(?:-\d+)*(?:\s*[:\-]\s*\d{4})?\b",

        r"\bIS\s+\d+(?:\s*,?\s*(?:PART|PT)\s*[.\-]?\s*\d+)?(?:\s*[:\-]\s*\d{4})?\b",

        r"\bAPI\s+[A-Z0-9]+(?:\.\d+)?(?:\s+(?:ED|EDITION)\.?\s*\d+)?\b",

        r"\bASME\s+(?:BPVC\s+)?(?:SEC(?:TION)?\.?\s*)?[A-Z0-9.\-()]+\b",

        r"\bAWS\s+[A-Z]\s*\d+(?:\.\d+)?\b",

        r"\bSOP\s*/\s*[A-Z0-9]+\s*/\s*\d+\b",

        r"\bIBR\s+1950\b",

        r"\bASM\s+HANDBOOK(?:\s+VOLUME|\s+VOL\.?)?\s+[A-Z0-9]+\b",
    ]

    found = []

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            value = match if isinstance(match, str) else match[0]
            value = " ".join(value.split())

            if value and value not in found:
                found.append(value)

    return found


TEST_HINTS = {
    "impact": [
        "IMPACT",
        "IMPACT TEST",
        "CHARPY",
        "CHARPY IMPACT",
    ],

    "tensile": [
        "TENSILE",
        "TENSILE TEST",
        "ULTIMATE TENSILE",
        "YIELD STRENGTH",
        "ELONGATION",
        "REDUCTION OF AREA",
    ],

    "hardness": [
        "HARDNESS",
        "HARDNESS TEST",
        "ROCKWELL",
        "VICKERS",
        "BRINELL",
        "HRC",
        "HRB",
        "HRA",
    ],

    "bend": [
        "BEND",
        "BEND TEST",
        "BENDING",
    ],

    "proof_load": [
        "PROOF LOAD",
        "PROOF LOAD TEST",
    ],

    "macro": [
        "MACRO",
        "MACRO EXAMINATION",
        "MACROSTRUCTURE",
    ],

    "microstructure": [
        "MICROSTRUCTURE",
        "MICROSTRUCTURE EXAMINATION",
        "MICRO EXAMINATION",
        "METALLOGRAPHIC",
    ],

    "chemical": [
        "CHEMICAL",
        "CHEMICAL ANALYSIS",
        "SPECTRO CHEMICAL ANALYSIS",
    ],
}


CHEMICAL_ELEMENTS = [
    "ALUMINIUM",
    "ALUMINUM",
    "ANTIMONY",
    "ARSENIC",
    "BISMUTH",
    "BORON",
    "CADMIUM",
    "CALCIUM",
    "CARBON",
    "CERIUM",
    "CHROMIUM",
    "COBALT",
    "COPPER",
    "IRON",
    "LEAD",
    "LITHIUM",
    "MAGNESIUM",
    "MANGANESE",
    "MOLYBDENUM",
    "NICKEL",
    "NIOBIUM",
    "NITROGEN",
    "PHOSPHOROUS",
    "PHOSPHORUS",
    "SILICON",
    "SULFUR",
    "SULPHUR",
    "TIN",
    "TITANIUM",
    "TUNGSTEN",
    "VANADIUM",
    "ZINC",
    "ZIRCONIUM",
]


def _document_type_key(document_type):
    value = _norm(document_type).lower().replace(" ", "_")

    for key in TEST_HINTS:
        if key in value:
            return key

    return None


def _test_terms(document_type, text):
    dtype = _document_type_key(document_type)

    if dtype:
        return list(TEST_HINTS.get(dtype, []))

    upper = _norm(text)

    detected = []

    for key, hints in TEST_HINTS.items():
        if any(_norm(hint) in upper for hint in hints):
            detected.extend(hints)

    return list(dict.fromkeys(detected))


def _chemical_elements_in_report(text):
    text_norm = _norm(text)
    words = set(text_norm.split())

    found = []

    for element in CHEMICAL_ELEMENTS:
        normalized = _norm(element)

        if normalized in words:
            found.append(normalized)

    # Normalize spelling variants.
    normalized_found = []

    aliases = {
        "ALUMINUM": "ALUMINIUM",
        "PHOSPHOROUS": "PHOSPHORUS",
        "SULPHUR": "SULFUR",
    }

    for element in found:
        element = aliases.get(element, element)

        if element not in normalized_found:
            normalized_found.append(element)

    return normalized_found


def _normalize_element(value):
    value = _norm(value)

    aliases = {
        "ALUMINUM": "ALUMINIUM",
        "PHOSPHOROUS": "PHOSPHORUS",
        "SULPHUR": "SULFUR",
    }

    return aliases.get(value, value)


def _test_score(scope_test, document_type, report_text):
    scope_test_norm = _norm(scope_test)
    dtype = _document_type_key(document_type)

    if not scope_test_norm:
        return 0.0

    # Chemical scope is commonly stored element-by-element.
    if dtype == "chemical":
        report_elements = _chemical_elements_in_report(report_text)
        scope_element = _normalize_element(scope_test_norm)

        if scope_element in report_elements:
            return 1.0

        # Some scope entries may use a generic chemical-analysis name.
        if "CHEMICAL" in scope_test_norm:
            return 0.90

        return 0.0

    hints = _test_terms(document_type, report_text)

    if not hints:
        return 0.0

    best = 0.0

    for hint in hints:
        hint_norm = _norm(hint)

        if hint_norm == scope_test_norm:
            score = 1.0

        elif hint_norm in scope_test_norm or scope_test_norm in hint_norm:
            score = 0.90

        else:
            score = _similar(hint_norm, scope_test_norm)

        best = max(best, score)

    return best


def _material_score(scope_material, report_text):
    material = _norm(scope_material)
    text = _norm(report_text)

    if not material:
        return 0.0

    if material in text:
        return 1.0

    aliases = {
        "STEEL PRODUCTS": [
            "STEEL",
            "CARBON STEEL",
            "ALLOY STEEL",
            "LOW ALLOY STEEL",
            "STAINLESS STEEL",
        ],

        "WELDED PRODUCTS": [
            "WELD",
            "WELDED",
            "WELDING",
            "WELD METAL",
        ],

        "METALLIC FASTENERS": [
            "BOLT",
            "NUT",
            "FASTENER",
            "STUD",
            "WASHER",
        ],

        "METALLIC MATERIALS FERROUS PRODUCTS": [
            "STEEL",
            "FERROUS",
            "IRON",
        ],

        "LOW ALLOY STEEL": [
            "LOW ALLOY STEEL",
            "ALLOY STEEL",
        ],

        "STAINLESS STEEL": [
            "STAINLESS STEEL",
        ],

        "CAST IRON": [
            "CAST IRON",
        ],

        "COPPER AND COPPER ALLOYS": [
            "COPPER",
            "COPPER ALLOY",
        ],

        "COPPER ITS ALLOYS": [
            "COPPER",
            "COPPER ALLOY",
        ],

        "NICKEL ITS ALLOYS": [
            "NICKEL ALLOY",
            "NICKEL BASE",
        ],
    }

    for key, values in aliases.items():
        if key in material:
            for value in values:
                if _norm(value) in text:
                    return 0.90

    important = [
        word
        for word in _words(material)
        if len(word) >= 5
        and word not in {"PRODUCTS", "MATERIALS", "METALLIC"}
    ]

    report_words = _words(text)

    if important:
        overlap = len(set(important) & report_words)

        if overlap >= 2:
            return 0.75

        if overlap == 1:
            return 0.55

    return 0.0


def _method_score(report_method, scope_method):
    report_key = _method_key(report_method)
    scope_key = _method_key(scope_method)

    if not report_key or not scope_key:
        return 0.0

    # Exact normalized standard identity.
    if report_key == scope_key:
        return 1.0

    report_words = report_key.split()
    scope_words = scope_key.split()

    # Allow extra revision/detail text only when the shorter identity is
    # sufficiently specific. This avoids tiny substrings producing COVERED.
    if len(report_words) >= 2 and len(scope_words) >= 2:
        if report_key in scope_key or scope_key in report_key:
            return 0.96

    similarity = _similar(report_key, scope_key)

    # Fuzzy similarity is supporting evidence only.
    if similarity >= 0.94:
        return 0.90

    if similarity >= 0.88:
        return 0.82

    return similarity


def check_nabl_scope(
    report_text,
    extracted_data=None,
    test_results=None,
    document_type=None,
):
    data = _load_scope()

    entries = data.get("scope_entries", [])

    extracted_data = extracted_data or {}
    test_results = test_results or {}

    certificate = data.get("certificate_number")
    valid_from = data.get("valid_from")
    valid_until = data.get("valid_until")

    today = date.today().isoformat()

    certificate_current = bool(
        valid_from
        and valid_until
        and valid_from <= today <= valid_until
    )

    methods = _find_methods(report_text)

    # Include structured extraction fields.
    for source in (extracted_data, test_results):
        if not isinstance(source, dict):
            continue

        for key in (
            "method",
            "test_method",
            "standard",
            "specification",
        ):
            value = source.get(key)

            if not value:
                continue

            for method in _find_methods(str(value)):
                if method not in methods:
                    methods.append(method)

    if not certificate_current:
        return {
            "status": "NOT VERIFIED",
            "certificate_number": certificate,
            "certificate_current": False,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "reason": (
                "The stored NABL certificate is not currently "
                "within its validity period."
            ),
            "report_methods": methods,
            "matches": [],
        }

    if not methods:
        return {
            "status": "NOT VERIFIED",
            "certificate_number": certificate,
            "certificate_current": True,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "reason": (
                "The report method/standard could not be extracted "
                "reliably enough for scope matching."
            ),
            "report_methods": [],
            "matches": [],
        }

    candidates = []

    report_norm = _norm(report_text)

    for entry in entries:
        scope_method = entry.get("method", "")

        best_method_score = 0.0
        matched_report_method = None

        for report_method in methods:
            score = _method_score(
                report_method,
                scope_method,
            )

            if score > best_method_score:
                best_method_score = score
                matched_report_method = report_method

        # Method identity is mandatory.
        if best_method_score < 0.90:
            continue

        test_score = _test_score(
            entry.get("test", ""),
            document_type,
            report_text,
        )

        # Test identity is mandatory.
        if test_score < 0.75:
            continue

        material_score = _material_score(
            entry.get("material", ""),
            report_norm,
        )

        # Material is supporting evidence. Missing material does not mean
        # OUT OF SCOPE, but weak evidence should reduce confidence.
        confidence = (
            (0.55 * best_method_score)
            + (0.30 * test_score)
            + (0.15 * material_score)
        )

        candidates.append(
            {
                "confidence": round(confidence, 3),
                "method_score": round(best_method_score, 3),
                "test_score": round(test_score, 3),
                "material_score": round(material_score, 3),
                "report_method": matched_report_method,
                "discipline": entry.get("discipline"),
                "material": entry.get("material"),
                "test": entry.get("test"),
                "method": entry.get("method"),
                "scope_page": entry.get("page"),
                "s_no": entry.get("s_no"),
            }
        )

    candidates.sort(
        key=lambda item: (
            item["confidence"],
            item["method_score"],
            item["test_score"],
            item["material_score"],
        ),
        reverse=True,
    )

    if candidates:
        best = candidates[0]

        # Do not declare COVERED from a weak fuzzy candidate.
        if (
            best["method_score"] >= 0.90
            and best["test_score"] >= 0.75
            and best["confidence"] >= 0.76
        ):
            return {
                "status": "COVERED",
                "certificate_number": certificate,
                "certificate_current": True,
                "valid_from": valid_from,
                "valid_until": valid_until,
                "reason": (
                    "The report test and test method match an entry "
                    "in the current TC-11952 Scope of Accreditation."
                ),
                "report_methods": methods,
                "best_match": best,
                "matches": candidates[:5],
            }

    return {
        "status": "NOT VERIFIED",
        "certificate_number": certificate,
        "certificate_current": True,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "reason": (
            "No sufficiently reliable combination of test, method "
            "and available material evidence was found in the stored "
            "TC-11952 scope. This is not automatically treated as "
            "OUT OF SCOPE."
        ),
        "report_methods": methods,
        "matches": candidates[:5],
    }