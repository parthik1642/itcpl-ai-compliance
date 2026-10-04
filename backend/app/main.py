from fastapi import (



    FastAPI,



    UploadFile,



    File,



    Depends,



    HTTPException



)







from fastapi.middleware.cors import CORSMiddleware



from sqlalchemy.orm import Session



from sqlalchemy import inspect, text



from pydantic import BaseModel







from datetime import datetime







import os

import re



import shutil



import json







from app.pdf_reader import extract_text_from_pdf



from app.document_classifier import classify_document, detect_test_report_types



from app.data_extractor import extract_common_fields



from app.extraction_pipeline import extract_with_fallback



from app.test_result_extractor import extract_test_results



from app.compliance_engine import evaluate_test



from app.iso17025_checker import check_iso17025_report



from app.nabl_scope_checker import check_nabl_scope



from app.job_order_extractor import extract_job_order



from app.final_decision import build_final_decisions



from app.job_comparator import compare_job_with_reports



from app.report_grouper import (



    group_reports_by_lab,



    calculate_lab_status



)



from app.purchase_order_extractor import extract_purchase_order



from app.po_job_comparator import compare_po_with_job_order



from app.llm_extractor import (



    extract_purchase_order_with_ai,



    extract_job_order_with_ai



)







from app.database import (



    engine,



    get_db



)







from app.models import (



    Base,



    Job,



    LabResult



)







from app.save_analysis import save_analysis











# =====================================================



# DATABASE



# =====================================================







Base.metadata.create_all(



    bind=engine



)











def ensure_optional_columns():



    """Add new JSON/text storage columns to an existing deployed database.







    create_all() creates missing tables but does not add columns to an existing



    table, so this keeps old Railway databases compatible with this update.



    """



    try:



        inspector = inspect(engine)



        columns = {column["name"] for column in inspector.get_columns("lab_results")}







        if "report_details" not in columns:



            with engine.begin() as connection:



                connection.execute(



                    text("ALTER TABLE lab_results ADD COLUMN report_details TEXT")



                )



    except Exception as exc:



        print("Database schema update warning:", exc)











ensure_optional_columns()











# =====================================================



# FASTAPI



# =====================================================







app = FastAPI(



    title="ITCPL AI Compliance System"



)











# =====================================================



# CORS



# =====================================================







app.add_middleware(



    CORSMiddleware,



    allow_origins=[



        "http://localhost:5173",



        "http://127.0.0.1:5173",



        "http://localhost:5174",



        "http://127.0.0.1:5174",



        "https://itcpl-ai-compliance.vercel.app",



    ],



    allow_credentials=True,



    allow_methods=["*"],



    allow_headers=["*"],



)











# =====================================================



# SETTINGS



# =====================================================







UPLOAD_FOLDER = "uploads"







os.makedirs(



    UPLOAD_FOLDER,



    exist_ok=True



)











AI_DISCLAIMER = (



    "AI assists with document extraction only. "



    "Final PASS/FAIL/MISSING/REVIEW decisions are produced by deterministic validation rules. "



    "REVIEW means human verification is required before final acceptance."



)











STATUS_GUIDE = {



    "PASS":



        "All automated compliance checks passed.",







    "REVIEW":



        "Human verification is required.",







    "FAIL":



        "One or more compliance checks failed.",







    "MISSING":



        "One or more required documents or test reports are missing.",







    "APPROVED":



        "A human reviewer manually approved the result.",







    "REJECTED":



        "A human reviewer manually rejected the result."



}



















METADATA_AI_FALLBACK_ENABLED = (



    os.getenv("AI_METADATA_FALLBACK_ENABLED", "false").lower() == "true"



)







# =====================================================



# MANUAL REVIEW REQUEST



# =====================================================







class ManualReviewRequest(BaseModel):



    decision: str



    note: str | None = None



    reviewed_by: str | None = None











# =====================================================



# VALIDATION HELPERS



# =====================================================







def validate_pdf_upload(



    file: UploadFile,



    label: str



):



    """



    Basic validation before saving an uploaded file.



    """







    filename = file.filename or ""







    if not filename:



        raise HTTPException(



            status_code=400,



            detail=f"{label} filename is missing."



        )







    if not filename.lower().endswith(".pdf"):



        raise HTTPException(



            status_code=400,



            detail=f"{label} must be a PDF file."



        )







    # Content type can sometimes be missing depending



    # on the browser/client, so only reject when a



    # clearly wrong content type is supplied.



    if (



        file.content_type



        and file.content_type



        not in [



            "application/pdf",



            "application/octet-stream"



        ]



    ):



        raise HTTPException(



            status_code=400,



            detail=f"{label} must be a PDF file."



        )











def validate_saved_file(



    file_path: str,



    label: str



):



    """



    Make sure the uploaded file was actually saved



    and is not empty.



    """







    if not os.path.exists(file_path):



        raise HTTPException(



            status_code=400,



            detail=f"{label} could not be saved."



        )







    if os.path.getsize(file_path) == 0:



        raise HTTPException(



            status_code=400,



            detail=f"{label} is empty."



        )











def validate_pdf_result(



    result: dict,



    label: str



):



    """



    Validate the extracted PDF result.



    """







    if not isinstance(result, dict):



        raise HTTPException(



            status_code=400,



            detail=f"{label} could not be processed."



        )







    pages = result.get(



        "pages",



        []



    )







    if not pages:



        raise HTTPException(



            status_code=400,



            detail=f"{label} contains no readable pages."



        )







    has_text = any(



        (page.get("text") or "").strip()



        for page in pages



    )







    if not has_text:



        raise HTTPException(



            status_code=400,



            detail=(



                f"{label} could not be read. "



                "The PDF may be empty, corrupted, "



                "or contain an unsupported scan."



            )



        )











def safe_extract_pdf(



    file_path: str,



    label: str



):



    """



    Run PDF extraction and return a clean 400 error



    instead of allowing a bad PDF to crash the API.



    """







    try:



        result = extract_text_from_pdf(



            file_path



        )







    except Exception as exc:







        print(



            f"{label} extraction error:",



            exc



        )







        raise HTTPException(



            status_code=400,



            detail=(



                f"{label} could not be processed. "



                "The PDF may be corrupted or unsupported."



            )



        )







    validate_pdf_result(



        result,



        label



    )







    return result











def save_uploaded_file(



    file: UploadFile,



    file_path: str,



    label: str



):



    """



    Safely save one uploaded file.



    """







    try:



        with open(



            file_path,



            "wb"



        ) as buffer:







            shutil.copyfileobj(



                file.file,



                buffer



            )







    except Exception as exc:







        print(



            f"{label} save error:",



            exc



        )







        raise HTTPException(



            status_code=400,



            detail=f"{label} could not be saved."



        )







    validate_saved_file(



        file_path,



        label



    )















# =====================================================



# RESULT SAFETY / CUSTOMER HELPERS



# =====================================================







def _valid_customer_name(value):



    if value is None:



        return False







    value = str(value).strip()







    if not value:



        return False







    generic_values = {



        "ADDRESS",



        "CUSTOMER",



        "CUSTOMER NAME",



        "CUSTOMER NAME & ADDRESS",



        "CUSTOMER NAME AND ADDRESS",



        "NAME",



        "CLIENT",



        "CLIENT NAME",



    }







    return value.upper() not in generic_values and len(value) >= 3











def _apply_extraction_review_safety(



    compliance: dict,



    test_results: dict



) -> dict:



    """



    Never allow an automated PASS when the extractor itself says



    critical result data still needs human review.







    A clear FAIL remains FAIL.



    """







    compliance = dict(compliance or {})



    test_results = test_results or {}







    if not test_results.get("needs_review"):



        return compliance







    current_status = str(



        compliance.get("status", "REVIEW")



    ).upper()







    # Never weaken a real FAIL.



    if current_status == "FAIL":



        return compliance







    # Do not override a verified PASS merely because an upstream extractor



    # left needs_review=True.  A PASS from the compliance engine means the



    # extracted result/conformity evidence was sufficient for that test.



    if current_status == "PASS":



        return compliance







    reason = (



        test_results.get("review_reason")



        or "Critical test-result values could not be verified automatically."



    )







    compliance["status"] = "REVIEW"







    issues = compliance.get("issues") or []



    if not isinstance(issues, list):



        issues = [str(issues)]







    if reason not in issues:



        issues.append(reason)







    compliance["issues"] = issues



    compliance["reason"] = reason







    return compliance











def _repair_missing_report_metadata(processed_reports: list, job_order_data: dict | None = None) -> None:

    """Repair OCR-dropped Lab No. conservatively.



    Recovery priority:

    1. Exact unique Heat No. match against the Job Order.

    2. Same Lab No. on both adjacent physical pages.

    3. One known adjacent Lab No.

    4. If adjacent pages belong to different labs, use required-test coverage:

       assign the orphan report only when its test is required by one neighbor,

       already present for the other neighbor, and missing for the candidate.



    Existing Lab Nos. are never overwritten.

    """

    job_order_data = job_order_data or {}

    by_page = {}

    for item in processed_reports:

        by_page.setdefault(item.get("page_number"), []).append(item)



    def norm(value):

        if value is None:

            return None

        value = str(value).upper().strip()

        value = value.replace("–", "-").replace("—", "-")

        value = re.sub(r"\s+", "", value)

        return value or None



    job_labs = {}

    heat_to_labs = {}

    for lab in job_order_data.get("labs", []):

        lab_no = lab.get("lab_no")

        if not lab_no:

            continue

        job_labs[lab_no] = lab

        heat = norm(lab.get("heat_no") or lab.get("heat_number"))

        if heat:

            heat_to_labs.setdefault(heat, []).append(lab_no)



    def page_lab(page_no):

        values = []

        for item in by_page.get(page_no, []):

            data = item.get("extracted_data") or {}

            value = data.get("lab_no")

            if value and value not in values:

                values.append(value)

        return values[0] if len(values) == 1 else None



    def present_types(lab_no):

        values = set()

        for item in processed_reports:

            data = item.get("extracted_data") or {}

            if data.get("lab_no") == lab_no and item.get("document_type"):

                values.add(item.get("document_type"))

        return values



    def required_types(lab_no):

        return set((job_labs.get(lab_no) or {}).get("required_tests") or [])



    for _ in range(4):

        changed = False



        for item in processed_reports:

            data = item.get("extracted_data")

            if not isinstance(data, dict):

                data = {}

                item["extracted_data"] = data



            if data.get("lab_no"):

                continue



            page_no = item.get("page_number")

            if not isinstance(page_no, int):

                continue



            inferred = None

            reason = None



            # First choice: a unique exact Heat No. match from the Job Order.

            heat = norm(

                data.get("heat_no")

                or (item.get("test_results") or {}).get("heat_no")

            )

            if heat and len(heat_to_labs.get(heat, [])) == 1:

                inferred = heat_to_labs[heat][0]

                reason = "heat match"



            prev_lab = page_lab(page_no - 1)

            next_lab = page_lab(page_no + 1)



            if not inferred and prev_lab and next_lab and prev_lab == next_lab:

                inferred = prev_lab

                reason = "matching adjacent pages"



            if not inferred and bool(prev_lab) != bool(next_lab):

                inferred = prev_lab or next_lab

                reason = "single adjacent page"



            # When the page sits between two different labs, don't guess by

            # direction. Use required-test coverage to resolve it.

            if not inferred and prev_lab and next_lab and prev_lab != next_lab:

                doc_type = item.get("document_type")

                if doc_type:

                    candidates = []

                    for lab_no in (prev_lab, next_lab):

                        required = required_types(lab_no)

                        present = present_types(lab_no)

                        if doc_type in required and doc_type not in present:

                            candidates.append(lab_no)



                    if len(candidates) == 1:

                        inferred = candidates[0]

                        reason = "required-test sequence"



            if not inferred:

                continue



            data["lab_no"] = inferred

            data["lab_no_inferred"] = True

            changed = True

            print(

                f"REPORT METADATA REPAIR: page {page_no} -> {inferred} "

                f"({reason})"

            )



        if not changed:

            break





# =====================================================



# AI MERGE HELPERS



# =====================================================







def _is_missing(value):



    return value is None or value == "" or value == [] or value == {}











def _normalize_po_numbers(purchase_order_data: dict) -> dict:



    """



    Keep old po_no compatibility while supporting zero, one, or many PO numbers.



    PO identification is metadata only and must never stop compliance analysis.



    """



    purchase_order_data = purchase_order_data or {}







    po_numbers = purchase_order_data.get("po_numbers") or []



    if isinstance(po_numbers, str):



        po_numbers = [po_numbers]







    legacy_po = purchase_order_data.get("po_no") or purchase_order_data.get("po_number")



    if legacy_po and legacy_po not in po_numbers:



        po_numbers.insert(0, legacy_po)







    cleaned = []



    for value in po_numbers:



        value = str(value).strip()



        if value and value not in cleaned:



            cleaned.append(value)







    purchase_order_data["po_numbers"] = cleaned



    purchase_order_data["po_no"] = cleaned[0] if cleaned else None



    purchase_order_data["po_number"] = purchase_order_data["po_no"]







    purchase_order_data.setdefault("warnings", [])



    if not cleaned:



        warning = "PO number could not be confidently extracted. Compliance analysis continued."



        if warning not in purchase_order_data["warnings"]:



            purchase_order_data["warnings"].append(warning)







    return purchase_order_data











def _merge_purchase_order_ai(purchase_order_data: dict, ai_data: dict) -> dict:



    """



    Conservative no-degradation merge:



    AI may fill missing PO metadata only. It never overwrites a reliable rule value.



    Conflicts are preserved as warnings for human visibility.



    """



    purchase_order_data = _normalize_po_numbers(purchase_order_data)



    ai_data = ai_data or {}







    purchase_order_data.setdefault("ai_conflicts", [])



    purchase_order_data.setdefault("ai_used_fields", [])







    try:



        confidence = float(ai_data.get("confidence", 0) or 0)



    except Exception:



        confidence = 0.0







    purchase_order_data["ai_confidence"] = confidence



    purchase_order_data["ai_uncertain_fields"] = ai_data.get("uncertain_fields", []) or []







    # Use AI only when reasonably confident.



    if confidence < 0.75:



        return purchase_order_data







    rule_pos = purchase_order_data.get("po_numbers") or []



    ai_pos = ai_data.get("po_numbers") or []







    if not rule_pos and ai_pos:



        unique = []



        for value in ai_pos:



            value = str(value).strip()



            if value and value not in unique:



                unique.append(value)



        if unique:



            purchase_order_data["po_numbers"] = unique



            purchase_order_data["po_no"] = unique[0]



            purchase_order_data["po_number"] = unique[0]



            purchase_order_data["ai_used_fields"].append("po_numbers")



    elif rule_pos and ai_pos:



        normalized_rule = {str(v).strip() for v in rule_pos if str(v).strip()}



        normalized_ai = {str(v).strip() for v in ai_pos if str(v).strip()}



        if normalized_rule != normalized_ai:



            purchase_order_data["ai_conflicts"].append({



                "field": "po_numbers",



                "rule_value": rule_pos,



                "ai_value": ai_pos



            })







    for field in ["customer_name", "material_grade"]:



        rule_value = purchase_order_data.get(field)



        ai_value = ai_data.get(field)



        if _is_missing(rule_value) and not _is_missing(ai_value):



            purchase_order_data[field] = ai_value



            purchase_order_data["ai_used_fields"].append(field)



        elif not _is_missing(rule_value) and not _is_missing(ai_value) and rule_value != ai_value:



            purchase_order_data["ai_conflicts"].append({



                "field": field,



                "rule_value": rule_value,



                "ai_value": ai_value



            })







    rule_heats = purchase_order_data.get("heat_numbers") or []



    ai_heats = ai_data.get("heat_numbers") or []



    if not rule_heats and ai_heats:



        purchase_order_data["heat_numbers"] = list(dict.fromkeys(ai_heats))



        if purchase_order_data["heat_numbers"]:



            purchase_order_data["heat_number"] = purchase_order_data["heat_numbers"][0]



        purchase_order_data["ai_used_fields"].append("heat_numbers")







    rule_specs = purchase_order_data.get("specifications") or []



    ai_specs = ai_data.get("specifications") or []



    if not rule_specs and ai_specs:



        purchase_order_data["specifications"] = list(dict.fromkeys(ai_specs))



        if not purchase_order_data.get("specification") and purchase_order_data["specifications"]:



            purchase_order_data["specification"] = purchase_order_data["specifications"][0]



        purchase_order_data["ai_used_fields"].append("specifications")







    purchase_order_data = _normalize_po_numbers(purchase_order_data)



    purchase_order_data["ai_used"] = bool(purchase_order_data.get("ai_used_fields"))



    return purchase_order_data











def _merge_job_order_ai(job_order_data: dict, ai_data: dict) -> dict:



    """



    AI supplements missing Job Order fields only.



    If rules and AI disagree on required tests, preserve rule output and record a conflict.



    This avoids AI hallucinations creating false MISSING tests.



    """



    job_order_data = job_order_data or {}



    ai_data = ai_data or {}







    job_order_data.setdefault("ai_conflicts", [])



    job_order_data.setdefault("ai_used_fields", [])







    try:



        confidence = float(ai_data.get("confidence", 0) or 0)



    except Exception:



        confidence = 0.0







    job_order_data["ai_confidence"] = confidence



    job_order_data["ai_uncertain_fields"] = ai_data.get("uncertain_fields", []) or []







    if confidence < 0.75:



        return job_order_data







    if not job_order_data.get("collection_no") and ai_data.get("collection_no"):



        job_order_data["collection_no"] = ai_data.get("collection_no")



        job_order_data["ai_used_fields"].append("collection_no")







    ai_labs = {



        lab.get("lab_no"): lab



        for lab in ai_data.get("labs", [])



        if isinstance(lab, dict) and lab.get("lab_no")



    }







    for lab in job_order_data.get("labs", []):



        if not isinstance(lab, dict):



            continue







        lab_no = lab.get("lab_no")



        ai_lab = ai_labs.get(lab_no)



        if not ai_lab:



            continue







        rule_heat = lab.get("heat_no")



        ai_heat = ai_lab.get("heat_no")



        if not rule_heat and ai_heat:



            lab["heat_no"] = ai_heat



            job_order_data["ai_used_fields"].append(f"{lab_no}.heat_no")



        elif rule_heat and ai_heat and rule_heat != ai_heat:



            job_order_data["ai_conflicts"].append({



                "lab_no": lab_no,



                "field": "heat_no",



                "rule_value": rule_heat,



                "ai_value": ai_heat



            })







        rule_tests = list(dict.fromkeys(lab.get("required_tests", []) or []))



        ai_tests = list(dict.fromkeys(ai_lab.get("required_tests", []) or []))







        # AI may fill tests only when deterministic parsing found none.



        # If both found tests but disagree, keep rules and flag the difference.



        if not rule_tests and ai_tests and confidence >= 0.80:



            lab["required_tests"] = ai_tests



            job_order_data["ai_used_fields"].append(f"{lab_no}.required_tests")



        elif rule_tests and ai_tests and set(rule_tests) != set(ai_tests):



            job_order_data["ai_conflicts"].append({



                "lab_no": lab_no,



                "field": "required_tests",



                "rule_value": rule_tests,



                "ai_value": ai_tests



            })







        if not lab.get("specification") and ai_lab.get("specification"):



            lab["specification"] = ai_lab.get("specification")



            job_order_data["ai_used_fields"].append(f"{lab_no}.specification")







        lab.setdefault("test_methods", {})



        for test_name, method in (ai_lab.get("test_methods") or {}).items():



            if test_name not in lab["test_methods"] and method:



                lab["test_methods"][test_name] = method



                job_order_data["ai_used_fields"].append(



                    f"{lab_no}.test_methods.{test_name}"



                )







        lab.setdefault("requirements", {})



        for test_name, requirement in (ai_lab.get("requirements") or {}).items():



            if test_name not in lab["requirements"] and requirement:



                lab["requirements"][test_name] = requirement



                job_order_data["ai_used_fields"].append(



                    f"{lab_no}.requirements.{test_name}"



                )







    job_order_data["ai_used"] = bool(job_order_data.get("ai_used_fields"))



    return job_order_data











# =====================================================



# HOME



# =====================================================







@app.get("/")



def home():







    return {



        "message":



            "ITCPL AI Compliance System is running",







        "disclaimer":



            AI_DISCLAIMER,







        "status_guide":



            STATUS_GUIDE



    }











# =====================================================



# SINGLE DOCUMENT UPLOAD



# =====================================================







@app.post("/upload")



def upload_document(



    file: UploadFile = File(...)



):







    validate_pdf_upload(



        file,



        "Uploaded document"



    )







    file_path = os.path.join(



        UPLOAD_FOLDER,



        file.filename



    )







    save_uploaded_file(



        file,



        file_path,



        "Uploaded document"



    )







    result = safe_extract_pdf(



        file_path,



        "Uploaded document"



    )







    classified_pages = []











    for page in result["pages"]:







        document_type = classify_document(



            page["text"]



        )







        job_order_data = None







        if document_type == "job_order":







            job_order_data = extract_job_order(



                page["text"]



            )











        extracted_data = extract_common_fields(



            page["text"]



        )











        test_results = extract_with_fallback(



            document_type,



            page["text"]



        )











        compliance = evaluate_test(



            document_type,



            test_results



        )







        compliance = _apply_extraction_review_safety(



            compliance,



            test_results



        )







        iso17025_report_check = check_iso17025_report(



            page["text"],



            extracted_data=extracted_data,



            test_results=test_results,



            document_type=document_type



        )











        classified_pages.append({







            "page_number":



                page["page_number"],







            "extraction_method":



                page["method"],







            "document_type":



                document_type,







            "extracted_data":



                extracted_data,







            "test_results":



                test_results,







            "compliance":



                compliance,







            "iso17025_report_check":



                iso17025_report_check,







            "job_order_data":



                job_order_data



        })











    labs = group_reports_by_lab(



        classified_pages



    )











    for lab_no, lab in labs.items():







        lab["overall_compliance"] = (



            calculate_lab_status(



                lab



            )



        )











    return {







        "disclaimer":



            AI_DISCLAIMER,







        "status_guide":



            STATUS_GUIDE,







        "filename":



            file.filename,







        "total_pages":



            result["total_pages"],







        "pages":



            classified_pages,







        "labs":



            labs



    }















# =====================================================



# ISO / NABL REPORT COMPLIANCE



# =====================================================







@app.post("/analyze-report-compliance")
def analyze_report_compliance(
    reports_file: UploadFile = File(...)
):
    """
    Separate ISO/IEC 17025:2017 + NABL report-level check.

    IMPORTANT:
    This endpoint is intentionally independent from the normal
    job/test compliance workflow. Results from this endpoint do
    NOT change technical PASS / FAIL / MISSING / REVIEW statuses.

    Multi-page reports are grouped by Report No. before ISO/NABL
    evaluation so one physical report produces one result row.
    """

    validate_pdf_upload(
        reports_file,
        "Test Reports"
    )

    reports_path = os.path.join(
        UPLOAD_FOLDER,
        f"compliance_{reports_file.filename}"
    )

    save_uploaded_file(
        reports_file,
        reports_path,
        "Test Reports"
    )

    reports_pdf = safe_extract_pdf(
        reports_path,
        "Test Reports"
    )

    def normalize_report_no(value):
        if value is None:
            return None

        raw = str(value).upper().strip()
        raw = raw.replace("–", "-").replace("—", "-")
        raw = re.sub(r"\s+", "", raw)

        if not raw:
            return None

        # A bare 26-XXXXXX value is the ITCPL Lab No. format, not a
        # complete Report No.  Do not let it become a grouping key.
        if re.fullmatch(r"\d{2}-\d{6}", raw):
            return None

        # OCR sometimes corrupts only the ITCPL prefix (for example TTCPL or
        # TTICPL) while preserving the numeric report identity.  Canonicalize
        # only when the complete three-part numeric Report No. is present.
        # This is intentionally local to the ISO/NABL endpoint.
        canonical_match = re.fullmatch(
            r"[A-Z0-9]{1,6}CPL[-/]?(\d{2})[-/]?(\d{6})[-/]?(\d+)",
            raw,
        )
        if canonical_match:
            report_suffix = canonical_match.group(3)

            # Report suffix 0 is valid in real ITCPL reports (for example
            # ITCPL-26-020656-0 in the verified Petro scan). Reject only
            # non-numeric suffixes; do not reinterpret a valid -0 as OCR noise.
            if not report_suffix.isdigit():
                return None

            return (
                f"ITCPL-{canonical_match.group(1)}-"
                f"{canonical_match.group(2)}-{report_suffix}"
            )

        # Preserve other legitimate report-number formats rather than
        # rewriting identifiers that do not match the known ITCPL pattern.
        return raw

    def report_no_from_text(text_value):
        text_value = str(text_value or "")

        # First prefer a complete ITCPL-style report identity.  The prefix is
        # allowed to contain OCR noise, but the numeric structure must be
        # complete before we canonicalize it.
        strong_patterns = [
            r"\b([A-Z0-9]{1,6}CPL(?:\s*[-/]\s*|\s+)\d{2}(?:\s*[-/]\s*|\s+)\d{6}(?:\s*[-/]\s*|\s+)\d+)\b",
            r"\b(ITCPL\s*[-/]\s*\d{2}\s*[-/]\s*\d{6}\s*[-/]\s*\d+)\b",
        ]
        for pattern in strong_patterns:
            match = re.search(pattern, text_value, flags=re.I)
            if match:
                normalized = normalize_report_no(match.group(1))
                if normalized:
                    return normalized

        # Then inspect an explicitly labelled Report No.  Reject a bare Lab
        # No. such as 26-020657 so it cannot be displayed/grouped as a report.
        labelled = re.search(
            r"\bREPORT\s*(?:NO\.?|NUMBER)\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/._\-]{5,})",
            text_value,
            flags=re.I,
        )
        if labelled:
            return normalize_report_no(labelled.group(1))

        return None

    def normalize_lab_no(value):
        if value is None:
            return None

        raw = str(value).upper().strip()
        raw = raw.replace("–", "-").replace("—", "-")
        raw = re.sub(r"\s+", "", raw)

        match = re.fullmatch(r"(\d{2})[-/]?(\d{6})", raw)
        if not match:
            return None

        return f"{match.group(1)}-{match.group(2)}"

    def lab_no_from_text(text_value):
        text_value = str(text_value or "")

        labelled_patterns = [
            r"\bLAB\s*(?:NO\.?|NUMBER)\s*[:\-]?\s*(\d{2}\s*[-/]\s*\d{6})\b",
            r"\bLAB\s*(?:NO\.?|NUMBER)\s*[:\-]?\s*(\d{2}\s+\d{6})\b",
        ]

        for pattern in labelled_patterns:
            match = re.search(pattern, text_value, flags=re.I)
            if match:
                normalized = normalize_lab_no(match.group(1))
                if normalized:
                    return normalized

        return None

    def page_position(text_value):
        text_value = str(text_value or "")
        match = re.search(
            r"\bPAGE\s*(?:NO\.?\s*)?(\d+)\s*(?:OF|/)\s*(\d+)\b",
            text_value,
            flags=re.I,
        )
        if not match:
            return None, None
        try:
            return int(match.group(1)), int(match.group(2))
        except Exception:
            return None, None

    # -------------------------------------------------
    # 1. Read every physical page and identify Report No.
    # -------------------------------------------------
    prepared_pages = []

    for page in reports_pdf.get("pages", []):
        page_text = page.get("text", "") or ""
        extracted_data = extract_common_fields(page_text) or {}

        report_no = normalize_report_no(
            extracted_data.get("report_no")
        ) or report_no_from_text(page_text)

        if report_no:
            extracted_data["report_no"] = report_no
        else:
            # Never preserve a malformed/bare Lab No. as Report No.
            extracted_data.pop("report_no", None)

        lab_no = normalize_lab_no(
            extracted_data.get("lab_no")
        ) or lab_no_from_text(page_text)

        if lab_no:
            extracted_data["lab_no"] = lab_no

        current_page, total_report_pages = page_position(page_text)

        prepared_pages.append({
            "page_number": page.get("page_number"),
            "text": page_text,
            "method": page.get("method"),
            "extracted_data": extracted_data,
            "report_no": report_no,
            "report_page_number": current_page,
            "report_total_pages": total_report_pages,
        })

        print(
            "ISO PAGE DEBUG: "
            f"page={page.get('page_number')} | "
            f"report={report_no or '-'} | "
            f"lab={lab_no or '-'} | "
            f"position={current_page or '-'} of {total_report_pages or '-'} | "
            f"method={page.get('method') or '-'}"
        )

    # -------------------------------------------------
    # 2. Conservative continuation-page repair.
    #    Only attach a missing Report No. when Page X of Y
    #    clearly continues the immediately preceding report.
    # -------------------------------------------------
    for index, item in enumerate(prepared_pages):
        if item.get("report_no"):
            continue

        current_page = item.get("report_page_number")
        total_pages = item.get("report_total_pages")

        if not current_page or not total_pages or current_page <= 1:
            continue

        if index == 0:
            continue

        previous = prepared_pages[index - 1]
        previous_report_no = previous.get("report_no")
        previous_current = previous.get("report_page_number")
        previous_total = previous.get("report_total_pages")

        if not previous_report_no:
            continue

        if (
            previous_current
            and previous_total
            and previous_total == total_pages
            and previous_current + 1 == current_page
        ):
            item["report_no"] = previous_report_no
            item["extracted_data"]["report_no"] = previous_report_no
            item["report_no_inferred"] = True

    # A first page can also lose its Report No. while a following continuation
    # page keeps it. Repair backwards only when Page 1 of Y is immediately
    # followed by Page 2 of the same Y and that next page has a reliable Report
    # No. This is the mirror image of the forward repair above and does not
    # invent a report suffix.
    for index in range(len(prepared_pages) - 1):
        item = prepared_pages[index]

        if item.get("report_no"):
            continue

        current_page = item.get("report_page_number")
        total_pages = item.get("report_total_pages")

        if current_page != 1 or not total_pages or total_pages <= 1:
            continue

        following = prepared_pages[index + 1]
        following_report_no = following.get("report_no")
        following_current = following.get("report_page_number")
        following_total = following.get("report_total_pages")

        if (
            following_report_no
            and following_current == 2
            and following_total == total_pages
        ):
            item["report_no"] = following_report_no
            item["extracted_data"]["report_no"] = following_report_no
            item["report_no_inferred"] = True

    # -------------------------------------------------
    # 3. Group physical pages by exact normalized Report No.
    #    Pages without a reliable Report No. stay separate.
    # -------------------------------------------------
    grouped_reports = []
    group_index = {}

    for item in prepared_pages:
        report_no = item.get("report_no")

        if report_no:
            group_key = f"REPORT::{report_no}"
        else:
            group_key = f"PAGE::{item.get('page_number')}"

        if group_key not in group_index:
            group_index[group_key] = len(grouped_reports)
            grouped_reports.append({
                "report_no": report_no,
                "pages": [],
            })

        grouped_reports[group_index[group_key]]["pages"].append(item)

    print(f"ISO GROUP DEBUG: prepared_pages={len(prepared_pages)} | groups={len(grouped_reports)}")
    for group_number, report_group in enumerate(grouped_reports, start=1):
        debug_pages = [
            page_item.get("page_number")
            for page_item in report_group.get("pages", [])
        ]
        print(
            "ISO GROUP DEBUG: "
            f"group={group_number} | "
            f"report={report_group.get('report_no') or '-'} | "
            f"pages={debug_pages}"
        )

    report_checks = []

    # -------------------------------------------------
    # 4. Evaluate each complete grouped report ONCE.
    # -------------------------------------------------
    for report_group in grouped_reports:
        group_pages = sorted(
            report_group.get("pages", []),
            key=lambda item: item.get("page_number") or 0,
        )

        combined_text = "\n\n".join(
            item.get("text", "") or ""
            for item in group_pages
        ).strip()

        if not combined_text:
            continue

        # Re-extract metadata from the complete report first.
        extracted_data = extract_common_fields(combined_text) or {}

        report_no = report_group.get("report_no")
        if report_no:
            extracted_data["report_no"] = report_no

        # Fill metadata conservatively from individual pages when the
        # combined extractor did not find it.
        for field in ("lab_no", "heat_no", "customer"):
            if extracted_data.get(field):
                continue
            for item in group_pages:
                value = (item.get("extracted_data") or {}).get(field)
                if value:
                    extracted_data[field] = value
                    break

        # Keep Report No. and Lab No. identities strict. A bare Lab No. must
        # never be promoted to Report No. If Report No. is unavailable, Lab No.
        # is retained only as a safe display fallback for this ISO/NABL result.
        combined_report_no = normalize_report_no(extracted_data.get("report_no"))
        if report_no:
            combined_report_no = report_no

        if combined_report_no:
            extracted_data["report_no"] = combined_report_no
        else:
            extracted_data.pop("report_no", None)

        lab_no = normalize_lab_no(extracted_data.get("lab_no"))
        if not lab_no:
            lab_no = lab_no_from_text(combined_text)
        if lab_no:
            extracted_data["lab_no"] = lab_no

        document_types = detect_test_report_types(combined_text) or []

        if not document_types:
            fallback_type = classify_document(combined_text)
            if fallback_type not in [
                "unknown",
                "test_report",
                "purchase_order",
                "job_order",
            ]:
                document_types = [fallback_type]

        if not document_types and "TEST REPORT" in combined_text.upper():
            document_types = ["test_report"]

        if not document_types:
            # Do not silently drop a report-looking grouped document.
            document_types = ["test_report"]

        # A single report can contain wording that triggers more than one
        # detector. Evaluate candidate types, but still return ONE report row.
        type_evaluations = []

        for document_type in list(dict.fromkeys(document_types)):
            try:
                test_results = extract_test_results(
                    document_type,
                    combined_text,
                )
                if not isinstance(test_results, dict):
                    test_results = {}
            except Exception as exc:
                print(
                    "Report compliance result extraction warning:",
                    exc,
                )
                test_results = {}

            check = check_iso17025_report(
                combined_text,
                extracted_data=extracted_data,
                test_results=test_results,
                document_type=document_type,
            )

            all_checks = check.get("checks", []) or []
            iso_checks = [
                item
                for item in all_checks
                if item.get("code") != "nabl_accreditation_reference"
            ]

            iso_issue_count = sum(
                1 for item in iso_checks
                if item.get("status") == "ISSUE"
            )
            iso_review_count = sum(
                1 for item in iso_checks
                if item.get("status") == "REVIEW"
            )
            iso_pass_count = sum(
                1 for item in iso_checks
                if item.get("status") == "PASS"
            )

            if iso_issue_count:
                iso_status = "ISSUE"
            elif iso_review_count:
                iso_status = "REVIEW"
            else:
                iso_status = "PASS"

            nabl_scope = check_nabl_scope(
                combined_text,
                extracted_data=extracted_data,
                test_results=test_results,
                document_type=document_type,
            )

            type_evaluations.append({
                "document_type": document_type,
                "test_results": test_results,
                "check": check,
                "iso_checks": iso_checks,
                "iso_status": iso_status,
                "iso_pass_count": iso_pass_count,
                "iso_review_count": iso_review_count,
                "iso_issue_count": iso_issue_count,
                "nabl_scope": nabl_scope,
                "nabl_status": nabl_scope.get(
                    "status",
                    "NOT VERIFIED",
                ),
            })

        # Choose the ISO evaluation with the least severe result when multiple
        # detector labels describe the same physical report. This avoids a
        # secondary keyword detector creating a duplicate false ISSUE.
        iso_rank = {
            "PASS": 0,
            "REVIEW": 1,
            "ISSUE": 2,
        }
        primary = min(
            type_evaluations,
            key=lambda item: (
                iso_rank.get(item.get("iso_status"), 9),
                -item.get("iso_pass_count", 0),
            ),
        )

        # NABL is COVERED only when at least one reliably detected test type
        # matches scope. If none match, preserve NOT VERIFIED rather than
        # claiming OUT OF SCOPE.
        covered_evaluations = [
            item
            for item in type_evaluations
            if item.get("nabl_status") == "COVERED"
        ]

        if covered_evaluations:
            best_nabl_eval = max(
                covered_evaluations,
                key=lambda item: (
                    (item.get("nabl_scope") or {})
                    .get("best_match", {})
                    .get("confidence", 0)
                ),
            )
        else:
            best_nabl_eval = primary

        nabl_scope = best_nabl_eval.get("nabl_scope") or {}
        nabl_status = best_nabl_eval.get(
            "nabl_status",
            "NOT VERIFIED",
        )

        nabl_checks = [{
            "code": "nabl_scope_verification",
            "label": "NABL Scope Verification",
            "status": nabl_status,
            "detail": nabl_scope.get("reason"),
            "evidence": (
                (
                    f"TC-11952 | "
                    f"{nabl_scope.get('best_match', {}).get('material')} | "
                    f"{nabl_scope.get('best_match', {}).get('test')} | "
                    f"{nabl_scope.get('best_match', {}).get('method')} | "
                    f"Scope page {nabl_scope.get('best_match', {}).get('scope_page')}"
                )
                if nabl_scope.get("best_match")
                else (
                    f"TC-11952 valid "
                    f"{nabl_scope.get('valid_from')} to "
                    f"{nabl_scope.get('valid_until')}"
                )
            ),
        }]

        page_numbers = [
            item.get("page_number")
            for item in group_pages
            if item.get("page_number") is not None
        ]

        # Display fallback only. It never changes grouping or invents a Report No.
        # If OCR misses the Report No., keep this physical report distinct by
        # showing its reliable Lab No. plus detected test type. If Lab No. is also
        # unreadable, show the physical PDF page plus test type instead of an em dash.
        display_type = str(primary.get("document_type") or "test_report")
        display_type = display_type.replace("_test_report", "").replace("_", " ").strip().title()
        if combined_report_no:
            display_report_no = combined_report_no
        elif lab_no:
            display_report_no = f"Lab {lab_no} — {display_type}"
        else:
            first_page = page_numbers[0] if page_numbers else None
            display_report_no = (
                f"PDF Page {first_page} — {display_type}"
                if first_page is not None
                else f"Unresolved — {display_type}"
            )

        report_checks.append({
            "page_number": page_numbers[0] if page_numbers else None,
            "page_numbers": page_numbers,
            "page_count": len(group_pages),
            "document_type": primary.get("document_type"),
            "detected_document_types": list(dict.fromkeys(document_types)),
            "report_no": display_report_no,
            "lab_no": extracted_data.get("lab_no"),
            "report_no_fallback": bool(not combined_report_no and lab_no),
            "heat_no": extracted_data.get("heat_no"),
            "customer": extracted_data.get("customer"),
            "iso_status": primary.get("iso_status"),
            "nabl_status": nabl_status,
            "iso_pass_count": primary.get("iso_pass_count", 0),
            "iso_review_count": primary.get("iso_review_count", 0),
            "iso_issue_count": primary.get("iso_issue_count", 0),
            "iso_checks": primary.get("iso_checks", []),
            "nabl_checks": nabl_checks,
            "nabl_scope": nabl_scope,
            "limitations": (primary.get("check") or {}).get(
                "limitations",
                [],
            ),
        })

    if not report_checks:
        raise HTTPException(
            status_code=400,
            detail=(
                "No test reports could be identified "
                "for ISO/NABL report compliance checking."
            ),
        )

    iso_issue_reports = sum(
        1
        for report in report_checks
        if report.get("iso_status") == "ISSUE"
    )

    iso_review_reports = sum(
        1
        for report in report_checks
        if report.get("iso_status") == "REVIEW"
    )

    iso_pass_reports = sum(
        1
        for report in report_checks
        if report.get("iso_status") == "PASS"
    )

    if iso_issue_reports:
        iso_overall_status = "ISSUE"
    elif iso_review_reports:
        iso_overall_status = "REVIEW"
    else:
        iso_overall_status = "PASS"

    nabl_covered_reports = sum(
        1
        for report in report_checks
        if report.get("nabl_status") == "COVERED"
    )

    nabl_not_verified_reports = sum(
        1
        for report in report_checks
        if report.get("nabl_status") == "NOT VERIFIED"
    )

    nabl_issue_reports = sum(
        1
        for report in report_checks
        if report.get("nabl_status") == "ISSUE"
    )

    if nabl_issue_reports:
        nabl_overall_status = "ISSUE"
    elif nabl_not_verified_reports:
        nabl_overall_status = "NOT VERIFIED"
    else:
        nabl_overall_status = "COVERED"

    return {
        "standard": "ISO/IEC 17025:2017",
        "title": "ISO / NABL Report Compliance",
        "iso_overall_status": iso_overall_status,
        "nabl_overall_status": nabl_overall_status,
        "report_count": len(report_checks),
        "iso_passed_reports": iso_pass_reports,
        "iso_reports_for_review": iso_review_reports,
        "iso_reports_with_issues": iso_issue_reports,
        "nabl_covered_reports": nabl_covered_reports,
        "nabl_not_verified_reports": nabl_not_verified_reports,
        "nabl_issue_reports": nabl_issue_reports,
        "reports": report_checks,
        "nabl_note": (
            "NABL scope verification is separate from ISO report "
            "compliance. NOT VERIFIED does not mean the report failed. "
            "It means the current NABL certificate/scope has not yet "
            "been independently matched to this test/method."
        ),
        "disclaimer": (
            "This automated page checks ISO/IEC 17025:2017 report "
            "content and NABL indicators separately. It does not "
            "certify the laboratory or independently prove current "
            "NABL accreditation scope."
        ),
    }


# =====================================================
# =====================================================



# COMPLETE JOB ANALYSIS



# =====================================================







@app.post("/analyze-job")



def analyze_complete_job(







    purchase_order_file:



        UploadFile = File(...),







    job_order_file:



        UploadFile = File(...),







    reports_file:



        UploadFile = File(...)



):







    # =================================================



    # VALIDATE UPLOADS



    # =================================================







    validate_pdf_upload(



        purchase_order_file,



        "Purchase Order"



    )







    validate_pdf_upload(



        job_order_file,



        "Job Order"



    )







    validate_pdf_upload(



        reports_file,



        "Test Reports"



    )











    # =================================================



    # FILE PATHS



    # =================================================







    po_path = os.path.join(



        UPLOAD_FOLDER,



        purchase_order_file.filename



    )







    job_path = os.path.join(



        UPLOAD_FOLDER,



        job_order_file.filename



    )







    reports_path = os.path.join(



        UPLOAD_FOLDER,



        reports_file.filename



    )











    # =================================================



    # SAVE FILES



    # =================================================







    save_uploaded_file(



        purchase_order_file,



        po_path,



        "Purchase Order"



    )







    save_uploaded_file(



        job_order_file,



        job_path,



        "Job Order"



    )







    save_uploaded_file(



        reports_file,



        reports_path,



        "Test Reports"



    )











    # =================================================



    # PROCESS JOB ORDER



    # =================================================







    job_pdf = safe_extract_pdf(



        job_path,



        "Job Order"



    )







    job_order_data = None







    # Job Orders can span multiple pages.  Parse the complete document so



    # labs that continue on page 2+ are not silently omitted.



    complete_job_text = "\n".join(



        page.get("text", "")



        for page in job_pdf.get("pages", [])



    )







    if complete_job_text.strip() and (



        classify_document(complete_job_text) == "job_order"



        or "JOB ORDER" in complete_job_text.upper()



    ):



        job_order_data = extract_job_order(



            complete_job_text



        )







        # AI supplements only missing/uncertain Job Order fields.



        # It does not overwrite deterministic values or decide compliance.



        if METADATA_AI_FALLBACK_ENABLED and not job_order_data.get("labs"):



            job_ai_data = extract_job_order_with_ai(complete_job_text)



            job_order_data = _merge_job_order_ai(job_order_data, job_ai_data)



        else:



            print("AI skipped: deterministic Job Order extraction sufficient.")











    if job_order_data is None:







        raise HTTPException(



            status_code=400,



            detail=(



                "The uploaded Job Order could not "



                "be identified as a Job Order."



            )



        )











    if not job_order_data.get(



        "labs"



    ):







        raise HTTPException(



            status_code=400,



            detail=(



                "No Lab Numbers could be identified "



                "from the Job Order."



            )



        )











    # =================================================



    # PROCESS TEST REPORTS



    # =================================================







    reports_pdf = safe_extract_pdf(



        reports_path,



        "Test Reports"



    )







    processed_reports = []











    for page in reports_pdf["pages"]:







        extracted_data = extract_common_fields(



            page["text"]



        )







        # One ITCPL report page may contain multiple tests (for example



        # Hardness + Nut Proof Load). Process every detected test type so



        # completed tests are not incorrectly marked as missing.



        document_types = detect_test_report_types(



            page["text"]



        )



        # Conservative recovery for scanned ITCPL chemical reports.

        # Only use an explicit chemical test-name marker from the report.

        page_text_upper = (page.get("text") or "").upper()

        strong_chemical_marker = (

            "SPECTRO CHEMICAL ANALYSIS" in page_text_upper

            or "TEST NAME : CHEMICAL" in page_text_upper

            or "TEST NAME: CHEMICAL" in page_text_upper

        )

        if strong_chemical_marker and "chemical_test_report" not in document_types:

            document_types = list(document_types or []) + ["chemical_test_report"]

            print(

                "REPORT TYPE RECOVERY: "

                f"page {page.get('page_number')} -> chemical_test_report "

                "(explicit chemical test-name marker)"

            )







        if not document_types:



            fallback_type = classify_document(



                page["text"]



            )







            if fallback_type not in [



                "unknown",



                "test_report",



                "purchase_order",



                "job_order"



            ]:



                document_types = [fallback_type]







        for document_type in document_types:







            test_results = extract_with_fallback(



                document_type,



                page["text"]



            )







            compliance = evaluate_test(



                document_type,



                test_results



            )







            compliance = _apply_extraction_review_safety(



                compliance,



                test_results



            )







            processed_reports.append({



                "page_number": page["page_number"],



                "document_type": document_type,



                "extracted_data": extracted_data,



                "test_results": test_results,



                "compliance": compliance



            })











    _repair_missing_report_metadata(processed_reports, job_order_data)











    if not processed_reports:







        raise HTTPException(



            status_code=400,



            detail=(



                "No test reports could be processed."



            )



        )











    # =================================================



    # CUSTOMER



    # =================================================







    customer_name = None











    for report in processed_reports:







        extracted_data = report.get(



            "extracted_data",



            {}



        )







        customer = extracted_data.get(



            "customer"



        )







        if _valid_customer_name(customer):







            customer_name = (



                customer.strip()



            )







            break











    if not _valid_customer_name(customer_name):



        customer_pattern = re.compile(



            r"Customer\s*Name\s*(?:&\s*Address)?\s*[:\\-]?\s*(?:\r?\n\s*)?([^\n\r]+)",



            re.IGNORECASE,



        )



        for page in reports_pdf.get("pages", []):



            match = customer_pattern.search(page.get("text", ""))



            if match and _valid_customer_name(match.group(1)):



                customer_name = match.group(1).strip()



                break







    print("Detected customer:", customer_name)











    # =================================================



    # PROCESS PURCHASE ORDER



    # =================================================







    po_pdf = safe_extract_pdf(



        po_path,



        "Purchase Order"



    )











    po_text = "\n".join(



        page["text"]



        for page in po_pdf["pages"]



    )











    purchase_order_data = (



        extract_purchase_order(



            po_text



        )



        or {}



    )







    # -------------------------------------------------



    # AI PURCHASE ORDER FALLBACK



    # -------------------------------------------------



    # PO number is metadata. Zero, one, or multiple PO numbers



    # are accepted. AI may fill missing metadata only.



    if METADATA_AI_FALLBACK_ENABLED and (



        not purchase_order_data.get("customer_name")



        and not purchase_order_data.get("po_numbers")



        and not purchase_order_data.get("required_tests")



    ):



        po_ai_data = extract_purchase_order_with_ai(po_text)



        purchase_order_data = _merge_purchase_order_ai(purchase_order_data, po_ai_data)



    else:



        print("AI skipped: deterministic client-requirement extraction sufficient.")







    # If report metadata produced a generic value such as "Address",



    # use the properly extracted PO/customer name instead.



    if not _valid_customer_name(customer_name):



        po_customer = purchase_order_data.get("customer_name")







        if _valid_customer_name(po_customer):



            customer_name = str(po_customer).strip()







    if not purchase_order_data.get("po_numbers"):



        print(



            "WARNING: No PO number could be confidently identified. "



            "Continuing compliance analysis."



        )











    # =================================================



    # GROUP REPORTS



    # =================================================







    report_labs = group_reports_by_lab(



        processed_reports



    )











    if not report_labs:







        raise HTTPException(



            status_code=400,



            detail=(



                "No valid Lab Numbers could be matched "



                "from the Test Reports."



            )



        )











    # =================================================



    # PO VS JOB ORDER



    # =================================================







    po_job_comparison = (



        compare_po_with_job_order(



            purchase_order_data,



            job_order_data



        )



    )











    # =================================================



    # JOB ORDER VS TEST REPORTS



    # =================================================







    comparison = (



        compare_job_with_reports(



            job_order_data,



            report_labs



        )



    )











    # =================================================



    # FINAL DECISIONS



    # =================================================







    final_decisions = (



        build_final_decisions(



            po_job_comparison,



            comparison



        )



    )











    if not final_decisions:







        raise HTTPException(



            status_code=400,



            detail=(



                "No final compliance decisions "



                "could be generated."



            )



        )











    # =================================================



    # SAVE DATABASE RESULT



    # =================================================







    saved_job = save_analysis(



        purchase_order_data,



        job_order_data,



        comparison,



        final_decisions,



        customer_name



    )











    # =================================================



    # RETURN



    # =================================================







    return {







        "disclaimer":



            AI_DISCLAIMER,







        "status_guide":



            STATUS_GUIDE,







        "customer":



            customer_name,







        "purchase_order":



            purchase_order_data,







        "job_order":



            job_order_data,







        "po_job_comparison":



            po_job_comparison,







        "report_comparison":



            comparison,







        "final_decisions":



            final_decisions,







        "saved_job":



            saved_job



    }











# =====================================================



# GET ALL JOBS



# =====================================================







@app.get("/jobs")



def get_jobs(



    db: Session = Depends(



        get_db



    )



):







    jobs = (



        db.query(Job)



        .order_by(



            Job.id.desc()



        )



        .all()



    )











    return [



        {



            "id":



                job.id,







            "po_no":



                job.po_no,







            "collection_no":



                job.collection_no,







            "customer":



                job.customer,







            "overall_status":



                job.overall_status,







            "created_at":



                job.created_at,







            "lab_count":



                len(job.labs)



        }







        for job in jobs



    ]











# =====================================================



# GET ONE JOB



# =====================================================







@app.get("/jobs/{job_id}")



def get_job(







    job_id: int,







    db: Session = Depends(



        get_db



    )



):







    job = (



        db.query(Job)



        .filter(



            Job.id == job_id



        )



        .first()



    )











    if not job:







        raise HTTPException(



            status_code=404,



            detail="Job not found."



        )











    return {







        "disclaimer":



            AI_DISCLAIMER,







        "status_guide":



            STATUS_GUIDE,







        "id":



            job.id,







        "po_no":



            job.po_no,







        "collection_no":



            job.collection_no,







        "customer":



            job.customer,







        "overall_status":



            job.overall_status,







        "created_at":



            job.created_at,











        "labs": [







            {



                "id":



                    lab.id,











                "lab_no":



                    lab.lab_no,











                "heat_no":



                    lab.heat_no,











                "required_tests":



                    json.loads(



                        lab.required_tests



                        or "[]"



                    ),











                "uploaded_tests":



                    json.loads(



                        lab.uploaded_tests



                        or "[]"



                    ),











                "missing_tests":



                    json.loads(



                        lab.missing_tests



                        or "[]"



                    ),











                "final_status":



                    lab.final_status,











                "reason":



                    lab.reason,











                "issues":



                    json.loads(



                        lab.issues



                        or "[]"



                    ),











                "report_details":



                    json.loads(



                        lab.report_details



                        or "[]"



                    ),











                "review_status":



                    lab.review_status,











                "review_note":



                    lab.review_note,











                "reviewed_by":



                    lab.reviewed_by,











                "reviewed_at":



                    lab.reviewed_at



            }







            for lab in job.labs



        ]



    }











# =====================================================



# RECALCULATE JOB STATUS



# =====================================================







def recalculate_job_status(



    job_id: int,



    db: Session



):







    job = (



        db.query(Job)



        .filter(



            Job.id == job_id



        )



        .first()



    )











    if not job:



        return











    labs = job.labs







    has_rejected = False



    has_unresolved_review = False











    for lab in labs:







        # Human rejection always fails the job.



        if lab.review_status == "REJECTED":







            has_rejected = True



            break











        # Automated FAIL always fails the job.



        if lab.final_status == "FAIL":







            has_rejected = True



            break











        # REVIEW remains unresolved until



        # explicitly approved by a human.



        if (



            lab.final_status == "REVIEW"



            and lab.review_status != "APPROVED"



        ):







            has_unresolved_review = True











        # Missing required documents also



        # prevent automatic PASS.



        if lab.final_status == "MISSING":







            has_unresolved_review = True











    if has_rejected:







        job.overall_status = "FAIL"











    elif has_unresolved_review:







        job.overall_status = "REVIEW"











    else:







        job.overall_status = "PASS"











    db.commit()











# =====================================================



# MANUAL LAB REVIEW



# =====================================================







@app.patch("/labs/{lab_id}/review")



def review_lab(







    lab_id: int,







    review: ManualReviewRequest,







    db: Session = Depends(



        get_db



    )



):







    lab = (



        db.query(LabResult)



        .filter(



            LabResult.id == lab_id



        )



        .first()



    )











    if not lab:







        raise HTTPException(



            status_code=404,



            detail="Lab result not found."



        )











    decision = (



        review.decision



        .strip()



        .upper()



    )











    if decision not in [



        "APPROVED",



        "REJECTED"



    ]:







        raise HTTPException(



            status_code=400,



            detail=(



                "Decision must be "



                "APPROVED or REJECTED."



            )



        )











    # Optional safety rule:



    # PASS results normally do not require manual review.



    if (



        lab.final_status == "PASS"



        and decision == "APPROVED"



    ):







        raise HTTPException(



            status_code=400,



            detail=(



                "This Lab already passed automated validation "



                "and does not require manual approval."



            )



        )











    lab.review_status = decision







    lab.review_note = (



        review.note



    )







    lab.reviewed_by = (



        review.reviewed_by



    )







    lab.reviewed_at = (



        datetime.utcnow()



    )











    db.commit()







    db.refresh(



        lab



    )











    recalculate_job_status(



        lab.job_id,



        db



    )











    db.refresh(



        lab



    )











    job = (



        db.query(Job)



        .filter(



            Job.id == lab.job_id



        )



        .first()



    )











    return {







        "message":



            "Manual review saved.",







        "disclaimer":



            AI_DISCLAIMER,







        "id":



            lab.id,







        "lab_id":



            lab.id,







        "lab_no":



            lab.lab_no,







        "review_status":



            lab.review_status,







        "review_note":



            lab.review_note,







        "reviewed_by":



            lab.reviewed_by,







        "reviewed_at":



            lab.reviewed_at,







        "job_id":



            lab.job_id,







        "job_overall_status":



            job.overall_status



    }