from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Depends,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from datetime import datetime

import os
import shutil
import json

from app.pdf_reader import extract_text_from_pdf
from app.document_classifier import classify_document
from app.data_extractor import extract_common_fields
from app.extraction_pipeline import extract_with_fallback
from app.compliance_engine import evaluate_test
from app.job_order_extractor import extract_job_order
from app.final_decision import build_final_decisions
from app.job_comparator import compare_job_with_reports
from app.report_grouper import (
    group_reports_by_lab,
    calculate_lab_status
)
from app.purchase_order_extractor import extract_purchase_order
from app.po_job_comparator import compare_po_with_job_order

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
        "http://127.0.0.1:5173"
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
    "AI-generated compliance results are advisory. "
    "PASS means all automated checks passed. "
    "REVIEW means human verification is required before final acceptance. "
    "A qualified reviewer should verify results before certification or release."
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
async def upload_document(
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
# COMPLETE JOB ANALYSIS
# =====================================================

@app.post("/analyze-job")
async def analyze_complete_job(

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


    for page in job_pdf["pages"]:

        document_type = classify_document(
            page["text"]
        )

        if document_type == "job_order":

            job_order_data = extract_job_order(
                page["text"]
            )

            break


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

        document_type = classify_document(
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


        processed_reports.append({

            "page_number":
                page["page_number"],

            "document_type":
                document_type,

            "extracted_data":
                extracted_data,

            "test_results":
                test_results,

            "compliance":
                compliance
        })


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

        if customer:

            customer_name = (
                customer.strip()
            )

            break


    print(
        "Detected customer:",
        customer_name
    )


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
    )


    if not purchase_order_data:

        raise HTTPException(
            status_code=400,
            detail=(
                "Purchase Order data "
                "could not be extracted."
            )
        )


    if not purchase_order_data.get(
        "po_no"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Purchase Order number "
                "could not be identified."
            )
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