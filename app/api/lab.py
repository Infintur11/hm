import os
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.schemas.lab import (
    LabResultEntry,
    LabTemplateCreate,
    LabTemplateUpdate,
    LabOrderCreate,
    RadiologyAnnotationSave
)
from app.services.lab_service import (
    get_lab_worklist,
    get_order_details,
    create_lab_order,
    update_sample_collected,
    enter_lab_result,
    save_radiology_annotation,
    get_all_templates,
    create_test_template,
    update_test_template,
    get_lab_analytics
)
from app.services.pdf_service import generate_diagnostic_report_pdf
from app.models.lab import LabTestTemplate, LabOrder, LabResult
from app.models.patient import Patient
from app.models.user import User
from app.api.deps import get_current_user, require_permissions

router = APIRouter(prefix="/api/lab", tags=["Laboratory & Radiology"])

UPLOAD_DIR = os.path.join("static", "uploads", "radiology")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/analytics")
def api_get_lab_analytics(
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:view_worklist"))
):
    """Real-time diagnostic workload KPIs, modality breakdown, and review alerts."""
    return get_lab_analytics(db)


@router.get("/templates")
def api_get_lab_templates(
    department: Optional[str] = Query(None, description="Filter by Hematology, Biochemistry, Radiology, etc."),
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    """Returns active lab & radiology test templates for ordering."""
    return get_all_templates(db, department=department, include_inactive=False)


@router.get("/templates/all")
def api_get_all_templates(
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:templates_manage"))
):
    """Returns all templates including inactive ones for the template management studio."""
    return get_all_templates(db, department=department, include_inactive=True)


@router.post("/templates")
def api_create_template(
    data: LabTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:templates_manage"))
):
    """Creates a new laboratory or radiology investigation template."""
    tmpl = create_test_template(db, data)
    return {"status": "SUCCESS", "id": tmpl.id, "test_code": tmpl.test_code, "test_name": tmpl.test_name}


@router.put("/templates/{template_id}")
def api_update_template(
    template_id: int,
    data: LabTemplateUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:templates_manage"))
):
    """Updates an existing test or imaging template."""
    tmpl = update_test_template(db, template_id, data)
    return {"status": "SUCCESS", "id": tmpl.id, "test_code": tmpl.test_code, "test_name": tmpl.test_name}


@router.get("/worklist")
def api_get_lab_worklist(
    status: Optional[str] = Query(None, description="Filter by ORDERED, SAMPLE_COLLECTED, or COMPLETED"),
    department: Optional[str] = Query(None, description="Filter by Laboratory, Radiology, or specific department"),
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:view_worklist"))
):
    """Returns diagnostic orders with patient demographics, modality, and results."""
    return get_lab_worklist(db, status_filter=status, department_filter=department)


@router.get("/orders/{order_id}")
def api_get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:view_worklist"))
):
    """Returns complete diagnostic order details, test parameters, scan attachments, and reports."""
    return get_order_details(db, order_id)


@router.post("/orders")
def api_create_lab_order(
    data: LabOrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:order"))
):
    """Orders a new diagnostic laboratory investigation or radiology exam."""
    ord = create_lab_order(db, data, user.id)
    return {
        "status": "SUCCESS",
        "order_id": ord.id,
        "test_name": ord.test_name,
        "barcode": ord.sample_barcode
    }


@router.patch("/orders/{order_id}/sample-collected")
def api_sample_collected(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:write_result"))
):
    """Marks specimen sample collected / patient received in imaging room with barcode."""
    ord = update_sample_collected(db, order_id)
    return {"status": "SAMPLE_COLLECTED", "barcode": ord.sample_barcode}


@router.post("/results")
def api_enter_lab_result(
    data: LabResultEntry,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:write_result"))
):
    """Saves or updates technician/radiologist results, multi-parameters, and findings."""
    res = enter_lab_result(db, data, user.id)
    return {
        "status": "SUCCESS",
        "order_id": res.order_id,
        "is_abnormal": res.is_abnormal,
        "panic_flag": res.panic_flag,
        "verified_at": res.verified_at.isoformat() if res.verified_at else None
    }


@router.post("/radiology/upload")
async def api_upload_radiology_image(
    file: UploadFile = File(...),
    order_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:write_result"))
):
    """Uploads a radiographic scan image (DICOM / PNG / JPG / WEBP) to the PACS storage."""
    file_bytes = await file.read()
    clean_name = file.filename.replace(" ", "_")
    timestamp = int(datetime.datetime.utcnow().timestamp())
    target_filename = f"scan_{order_id or 'temp'}_{timestamp}_{clean_name}"
    target_path = os.path.join(UPLOAD_DIR, target_filename)

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    web_url = f"/static/uploads/radiology/{target_filename}"

    # If linked to an order, update result or create draft
    if order_id:
        res = db.query(LabResult).filter(LabResult.order_id == order_id).first()
        if res:
            res.image_url = web_url
        else:
            ord = db.query(LabOrder).filter(LabOrder.id == order_id).first()
            template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord.template_id).first() if ord else None
            res = LabResult(
                order_id=order_id,
                result_value="Scan Uploaded",
                modality=ord.modality if ord else (template.modality if template else "XRAY"),
                image_url=web_url,
                technician_id=user.id
            )
            db.add(res)
        db.commit()

    return {"status": "SUCCESS", "image_url": web_url, "filename": target_filename}


@router.post("/radiology/annotate")
def api_save_radiology_annotation(
    data: RadiologyAnnotationSave,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:write_result"))
):
    """Saves annotated canvas radiograph with radiologist drawn ROI callouts and arrows."""
    annotated_url = save_radiology_annotation(db, data.order_id, data.image_data, user.id)
    return {"status": "SUCCESS", "annotated_image_url": annotated_url}


@router.get("/reports/{order_id}/pdf")
def api_download_diagnostic_pdf(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("lab:view_worklist"))
):
    """Exports an executive-grade clinical diagnostic report PDF for laboratory or radiology."""
    ord = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not ord:
        raise HTTPException(status_code=404, detail="Order not found")

    template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord.template_id).first()
    patient = db.query(Patient).filter(Patient.id == ord.patient_id).first()
    doctor = db.query(User).filter(User.id == ord.ordered_by_doctor_id).first()
    result = db.query(LabResult).filter(LabResult.order_id == ord.id).first()

    order_data = {
        "id": ord.id,
        "test_name": ord.test_name,
        "modality": ord.modality or (template.modality if template else None),
        "sample_barcode": ord.sample_barcode,
        "clinical_notes": ord.clinical_notes,
        "created_at": ord.created_at.strftime("%d-%b-%Y %H:%M") if ord.created_at else "-",
        "collected_at": ord.collected_at.strftime("%d-%b-%Y %H:%M") if ord.collected_at else "-"
    }

    patient_data = {
        "full_name": patient.full_name if patient else "Unknown",
        "mrn": patient.mrn if patient else "-",
        "age": patient.age if patient else "-",
        "gender": patient.gender if patient else "-",
        "phone_number": patient.phone_number if patient else "-"
    }

    doctor_data = {
        "full_name": doctor.full_name if doctor else "Doctor"
    }

    template_data = {
        "test_name": template.test_name if template else ord.test_name,
        "department": template.department if template else "Pathology",
        "modality": template.modality if template else ord.modality,
        "sample_type": template.sample_type if template else "Specimen",
        "normal_range": template.normal_range if template else "-",
        "unit_of_measurement": template.unit_of_measurement if template else ""
    }

    result_data = {
        "result_value": result.result_value if result else "Pending",
        "reference_range": result.reference_range if result else (template.normal_range if template else "-"),
        "unit": result.unit if result else (template.unit_of_measurement if template else ""),
        "is_abnormal": result.is_abnormal if result else False,
        "panic_flag": result.panic_flag if result else "NORMAL",
        "technician_notes": result.technician_notes if result else "",
        "parameter_results": result.parameter_results if result else None,
        "modality": result.modality if (result and result.modality) else template_data.get("modality"),
        "image_url": result.image_url if result else None,
        "annotated_image_url": result.annotated_image_url if result else None,
        "clinical_history": result.clinical_history if result else (ord.clinical_notes or ""),
        "technique": result.technique if result else "",
        "findings": result.findings if result else "",
        "impression": result.impression if result else "",
        "verified_at": result.verified_at.strftime("%d-%b-%Y %H:%M") if (result and result.verified_at) else datetime.datetime.utcnow().strftime("%d-%b-%Y %H:%M")
    }

    pdf_bytes = generate_diagnostic_report_pdf(
        order_data=order_data,
        result_data=result_data,
        patient_data=patient_data,
        doctor_data=doctor_data,
        template_data=template_data
    )

    clean_filename = f"diagnostic-report-order-{order_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={clean_filename}",
            "Cache-Control": "no-cache"
        }
    )


@router.get("/doctor-review-queue")
def api_get_doctor_review_queue(
    db: Session = Depends(get_db),
    user=Depends(require_permissions("consultation:write"))
):
    """Returns diagnostic reports awaiting consulting doctor verification and clinical sign-off."""
    from app.services.lab_service import get_doctor_review_queue
    doc_id = user.id if user.role == "DOCTOR" else None
    return get_doctor_review_queue(db, doctor_id=doc_id)


@router.post("/orders/{order_id}/doctor-review")
async def api_review_order_by_doctor(
    order_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(require_permissions("consultation:write"))
):
    """Doctor approves & signs off report, or requests changes sending it back to lab tech."""
    from app.services.lab_service import review_lab_result_by_doctor
    action = payload.get("action", "APPROVE")
    doctor_notes = payload.get("doctor_notes", "")
    return review_lab_result_by_doctor(db, order_id=order_id, doctor_id=user.id, action=action, doctor_notes=doctor_notes)


@router.get("/dispatch-queue")
def api_get_reception_dispatch_queue(
    db: Session = Depends(get_db),
    user=Depends(require_permissions("appointment:create"))
):
    """Returns patient diagnostic delivery queue with billing status and doctor sign-off verification."""
    from app.services.lab_service import get_reception_dispatch_queue
    return get_reception_dispatch_queue(db)


@router.post("/orders/{order_id}/dispatch")
async def api_dispatch_report(
    order_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user=Depends(require_permissions("appointment:create"))
):
    """Dispatches doctor-approved diagnostic report via Email, WhatsApp, and SMS once bill is cleared."""
    from app.services.lab_service import dispatch_report_to_patient
    channels = payload.get("channels", ["WHATSAPP", "EMAIL", "SMS"])
    recipient_phone = payload.get("recipient_phone")
    recipient_email = payload.get("recipient_email")
    return dispatch_report_to_patient(
        db,
        order_id=order_id,
        channels=channels,
        user_id=user.id,
        recipient_phone=recipient_phone,
        recipient_email=recipient_email
    )


@router.post("/orders/{order_id}/notify-billing")
async def api_notify_billing_reminder(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("appointment:create"))
):
    """Triggers instant SMS & WhatsApp notification to patient to settle cashier bill so report can be dispatched."""
    from app.services.lab_service import send_billing_clearance_reminder
    return send_billing_clearance_reminder(db, order_id=order_id, user_id=user.id)

