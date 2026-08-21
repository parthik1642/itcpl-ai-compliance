from app.database import SessionLocal
from app.models import Job, LabResult
import json


def save_analysis(
    purchase_order: dict,
    job_order: dict,
    report_comparison: dict,
    final_decisions: dict,
    customer_name: str = None
):

    db = SessionLocal()

    try:
        statuses = [
            result.get("final_status")
            for result in final_decisions.values()
        ]

        if "FAIL" in statuses:
            overall_status = "FAIL"

        elif "MISSING" in statuses:
            overall_status = "MISSING"

        elif "REVIEW" in statuses:
            overall_status = "REVIEW"

        elif statuses and all(
            status == "PASS"
            for status in statuses
        ):
            overall_status = "PASS"

        else:
            overall_status = "REVIEW"

        job = Job(
    po_no=purchase_order.get("po_no"),
    collection_no=job_order.get("collection_no"),
    customer=customer_name,
    overall_status=overall_status
)

        db.add(job)
        db.flush()

        # Map heat numbers from Job Order
        heat_map = {
            lab.get("lab_no"): lab.get("heat_no")
            for lab in job_order.get("labs", [])
        }

        for lab_no, result in final_decisions.items():
            report_data = report_comparison.get(
                        lab_no,
                        {}
                    )

            lab = LabResult(
                job_id=job.id,
                lab_no=lab_no,
                heat_no=heat_map.get(lab_no),
                final_status=result.get("final_status"),
                reason=result.get("reason"),

                required_tests=json.dumps(
                    report_data.get(
                        "required_tests",
                        []
                    )
                ),

                uploaded_tests=json.dumps(
                    report_data.get(
                        "uploaded_tests",
                        []
                    )
                ),

                missing_tests=json.dumps(
                    report_data.get(
                        "missing_tests",
                        []
                    )
                ),

                issues=json.dumps(
                    result.get(
                        "issues",
                        []
                    )
                )
            )

            db.add(lab)

        db.commit()

        return {
            "job_id": job.id,
            "overall_status": overall_status
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()