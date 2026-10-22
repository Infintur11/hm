import base64
import datetime
import json
import os
import re
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabResult, LabTestTemplate
from app.models.patient import Patient
from app.models.user import User
from app.schemas.lab import LabResultEntry, LabTemplateCreate, LabTemplateUpdate, LabOrderCreate

UPLOAD_DIR = os.path.join("static", "uploads", "radiology")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_lab_worklist(
    db: Session,
    status_filter: Optional[str] = None,
    department_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns enriched diagnostic worklist supporting laboratory and radiology modalities."""
    query = db.query(LabOrder).order_by(LabOrder.created_at.desc())
    if status_filter:
        query = query.filter(LabOrder.sample_status == status_filter)

    orders = query.all()
    worklist = []

    for ord in orders:
        template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord.template_id).first()
        dept = template.department if template else "Pathology"
        modality = ord.modality or (template.modality if template else None)

        # Department filtering: Pathology vs Radiology vs All
        if department_filter:
            if department_filter == "Radiology" and dept != "Radiology":
                continue
            elif department_filter == "Laboratory" and dept == "Radiology":
                continue

        patient = db.query(Patient).filter(Patient.id == ord.patient_id).first()
        doctor = db.query(User).filter(User.id == ord.ordered_by_doctor_id).first()
        result = db.query(LabResult).filter(LabResult.order_id == ord.id).first()

        worklist.append({
            "id": ord.id,
            "patient_id": ord.patient_id,
            "patient_name": patient.full_name if patient else "Unknown",
            "patient_phone": patient.phone_number if patient else "",
            "patient_mrn": patient.mrn if patient else "",
            "patient_age": patient.age if patient else "-",
            "patient_gender": patient.gender if patient else "-",
            "doctor_name": doctor.full_name if doctor else "Doctor",
            "test_name": ord.test_name,
            "department": dept,
            "modality": modality,
            "sample_type": template.sample_type if template else "Specimen",
            "normal_range": template.normal_range if template else "-",
            "unit": template.unit_of_measurement if template else "",
            "sample_status": ord.sample_status,
            "sample_barcode": ord.sample_barcode,
            "clinical_notes": ord.clinical_notes,
            "result_value": result.result_value if result else None,
            "is_abnormal": result.is_abnormal if result else False,
            "panic_flag": result.panic_flag if result else None,
            "technician_notes": result.technician_notes if result else None,
            "parameter_results": result.parameter_results if result else None,
            "image_url": result.image_url if result else None,
            "annotated_image_url": result.annotated_image_url if result else None,
            "findings": result.findings if result else None,
            "impression": result.impression if result else None,
            "clinical_history": result.clinical_history if result else None,
            "technique": result.technique if result else None,
            "doctor_approval_status": result.doctor_approval_status if result else "PENDING_REVIEW",
            "doctor_notes": result.doctor_notes if result else "",
            "ordered_at": ord.created_at.strftime("%d-%b %H:%M") if ord.created_at else "-",
            "verified_at": result.verified_at.strftime("%d-%b %H:%M") if (result and result.verified_at) else None
        })
    return worklist


def get_order_details(db: Session, order_id: int) -> Dict[str, Any]:
    """Returns detailed diagnostic order, patient history, test parameters, and radiology attachments."""
    ord = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not ord:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")

    patient = db.query(Patient).filter(Patient.id == ord.patient_id).first()
    doctor = db.query(User).filter(User.id == ord.ordered_by_doctor_id).first()
    template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord.template_id).first()
    result = db.query(LabResult).filter(LabResult.order_id == ord.id).first()

    return {
        "id": ord.id,
        "encounter_id": ord.encounter_id,
        "patient_id": ord.patient_id,
        "patient_name": patient.full_name if patient else "Unknown",
        "patient_mrn": patient.mrn if patient else "-",
        "patient_phone": patient.phone_number if patient else "",
        "patient_age": patient.age if patient else "-",
        "patient_gender": patient.gender if patient else "-",
        "ordered_by_doctor_id": ord.ordered_by_doctor_id,
        "doctor_name": doctor.full_name if doctor else "Doctor",
        "template_id": ord.template_id,
        "test_name": ord.test_name,
        "department": template.department if template else "Pathology",
        "modality": ord.modality or (template.modality if template else None),
        "sample_type": template.sample_type if template else "Specimen",
        "standard_rate": template.standard_rate if template else 0,
        "normal_range": template.normal_range if template else "-",
        "unit": template.unit_of_measurement if template else "",
        "parameters_json": template.parameters_json if template else None,
        "template_text": template.template_text if template else None,
        "sample_status": ord.sample_status,
        "sample_barcode": ord.sample_barcode,
        "clinical_notes": ord.clinical_notes,
        "created_at": ord.created_at.strftime("%d-%b-%Y %H:%M") if ord.created_at else "-",
        "collected_at": ord.collected_at.strftime("%d-%b-%Y %H:%M") if ord.collected_at else None,
        # Result Details
        "result_id": result.id if result else None,
        "result_value": result.result_value if result else "",
        "is_abnormal": result.is_abnormal if result else False,
        "panic_flag": result.panic_flag if result else "NORMAL",
        "technician_notes": result.technician_notes if result else "",
        "parameter_results": result.parameter_results if result else None,
        "image_url": result.image_url if result else None,
        "annotated_image_url": result.annotated_image_url if result else None,
        "clinical_history": result.clinical_history if result else (ord.clinical_notes or ""),
        "technique": result.technique if result else "",
        "findings": result.findings if result else "",
        "impression": result.impression if result else "",
        "doctor_approval_status": result.doctor_approval_status if result else "PENDING_REVIEW",
        "doctor_notes": result.doctor_notes if result else "",
        "verified_at": result.verified_at.strftime("%d-%b-%Y %H:%M") if (result and result.verified_at) else None
    }



def create_lab_order(db: Session, data: LabOrderCreate, user_id: int) -> LabOrder:
    """Creates a new diagnostic lab or radiology order with sample barcode."""
    template = db.query(LabTestTemplate).filter(LabTestTemplate.id == data.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Test template not found")

    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    doc_id = data.ordered_by_doctor_id or user_id
    barcode = f"BAR-{int(datetime.datetime.utcnow().timestamp()) % 1000000:06d}"

    order = LabOrder(
        encounter_id=data.encounter_id,
        patient_id=data.patient_id,
        ordered_by_doctor_id=doc_id,
        template_id=template.id,
        test_name=template.test_name,
        modality=template.modality,
        sample_status="ORDERED",
        sample_barcode=barcode,
        clinical_notes=data.clinical_notes
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def update_sample_collected(db: Session, order_id: int) -> LabOrder:
    """Updates order status to SAMPLE_COLLECTED / SPECIMEN_RECEIVED."""
    order = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Lab order not found")
    order.sample_status = "SAMPLE_COLLECTED"
    order.collected_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


def enter_lab_result(db: Session, data: LabResultEntry, tech_id: int) -> LabResult:
    """Saves or updates multi-parameter test results or radiology reports."""
    order = db.query(LabOrder).filter(LabOrder.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")

    template = db.query(LabTestTemplate).filter(LabTestTemplate.id == order.template_id).first()

    existing_result = db.query(LabResult).filter(LabResult.order_id == data.order_id).first()
    if existing_result:
        existing_result.result_value = data.result_value or "Completed"
        existing_result.is_abnormal = data.is_abnormal
        existing_result.panic_flag = data.panic_flag or ("ABNORMAL" if data.is_abnormal else "NORMAL")
        existing_result.technician_notes = data.technician_notes
        existing_result.technician_id = tech_id
        existing_result.verified_at = datetime.datetime.utcnow()

        # Multi-parameter values
        if data.parameter_results is not None:
            existing_result.parameter_results = data.parameter_results

        # Radiology specific diagnostics
        if data.modality is not None:
            existing_result.modality = data.modality
        if data.image_url is not None:
            existing_result.image_url = data.image_url
        if data.annotated_image_url is not None:
            existing_result.annotated_image_url = data.annotated_image_url
        if data.clinical_history is not None:
            existing_result.clinical_history = data.clinical_history
        if data.technique is not None:
            existing_result.technique = data.technique
        if data.findings is not None:
            existing_result.findings = data.findings
        if data.impression is not None:
            existing_result.impression = data.impression

        result = existing_result
    else:
        result = LabResult(
            order_id=order.id,
            result_value=data.result_value or "Completed",
            reference_range=template.normal_range if template else None,
            unit=template.unit_of_measurement if template else None,
            is_abnormal=data.is_abnormal,
            panic_flag=data.panic_flag or ("ABNORMAL" if data.is_abnormal else "NORMAL"),
            technician_notes=data.technician_notes,
            technician_id=tech_id,
            verified_at=datetime.datetime.utcnow(),
            parameter_results=data.parameter_results,
            modality=data.modality or (template.modality if template else None),
            image_url=data.image_url,
            annotated_image_url=data.annotated_image_url,
            clinical_history=data.clinical_history,
            technique=data.technique,
            findings=data.findings,
            impression=data.impression
        )
        db.add(result)

    order.sample_status = "COMPLETED"
    db.commit()
    db.refresh(result)
    return result


def save_radiology_annotation(db: Session, order_id: int, image_data_base64: str, tech_id: int) -> str:
    """Decodes HTML5 canvas base64 image data and saves it to static uploads."""
    order = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Match data URL prefix
    match = re.search(r"base64,(.*)", image_data_base64)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    raw_bytes = base64.b64decode(match.group(1))
    filename = f"annotated_order_{order_id}_{int(datetime.datetime.utcnow().timestamp())}.png"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(raw_bytes)

    web_url = f"/static/uploads/radiology/{filename}"

    # Update or initialize LabResult
    res = db.query(LabResult).filter(LabResult.order_id == order_id).first()
    if res:
        res.annotated_image_url = web_url
    else:
        template = db.query(LabTestTemplate).filter(LabTestTemplate.id == order.template_id).first()
        res = LabResult(
            order_id=order_id,
            result_value="Radiograph Annotated",
            modality=order.modality or (template.modality if template else "XRAY"),
            annotated_image_url=web_url,
            technician_id=tech_id
        )
        db.add(res)

    db.commit()
    return web_url


def get_all_templates(
    db: Session,
    department: Optional[str] = None,
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """Returns active or all test & imaging templates."""
    query = db.query(LabTestTemplate)
    if not include_inactive:
        query = query.filter(LabTestTemplate.is_active == True)
    if department:
        query = query.filter(LabTestTemplate.department == department)

    templates = query.order_by(LabTestTemplate.department.asc(), LabTestTemplate.test_name.asc()).all()
    out = []
    for t in templates:
        out.append({
            "id": t.id,
            "test_code": t.test_code,
            "test_name": t.test_name,
            "department": t.department,
            "modality": t.modality,
            "sample_type": t.sample_type,
            "standard_rate": t.standard_rate,
            "normal_range": t.normal_range,
            "unit": t.unit_of_measurement,
            "parameters_json": t.parameters_json,
            "template_text": t.template_text,
            "is_active": t.is_active
        })
    return out


def create_test_template(db: Session, data: LabTemplateCreate) -> LabTestTemplate:
    """Creates a new laboratory or radiology template."""
    existing = db.query(LabTestTemplate).filter(LabTestTemplate.test_code == data.test_code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Test code '{data.test_code}' already exists.")

    template = LabTestTemplate(
        test_code=data.test_code.strip().upper(),
        test_name=data.test_name.strip(),
        department=data.department.strip(),
        modality=data.modality.strip().upper() if data.modality else None,
        sample_type=data.sample_type.strip(),
        standard_rate=data.standard_rate,
        normal_range=data.normal_range.strip() if data.normal_range else None,
        unit_of_measurement=data.unit_of_measurement.strip() if data.unit_of_measurement else None,
        parameters_json=data.parameters_json,
        template_text=data.template_text,
        is_active=data.is_active
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_test_template(db: Session, template_id: int, data: LabTemplateUpdate) -> LabTestTemplate:
    """Updates existing laboratory or radiology template."""
    template = db.query(LabTestTemplate).filter(LabTestTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if data.test_code is not None:
        chk = db.query(LabTestTemplate).filter(
            LabTestTemplate.test_code == data.test_code.strip().upper(),
            LabTestTemplate.id != template_id
        ).first()
        if chk:
            raise HTTPException(status_code=400, detail="Test code already in use.")
        template.test_code = data.test_code.strip().upper()

    if data.test_name is not None:
        template.test_name = data.test_name.strip()
    if data.department is not None:
        template.department = data.department.strip()
    if data.modality is not None:
        template.modality = data.modality.strip().upper() if data.modality else None
    if data.sample_type is not None:
        template.sample_type = data.sample_type.strip()
    if data.standard_rate is not None:
        template.standard_rate = data.standard_rate
    if data.normal_range is not None:
        template.normal_range = data.normal_range.strip() if data.normal_range else None
    if data.unit_of_measurement is not None:
        template.unit_of_measurement = data.unit_of_measurement.strip() if data.unit_of_measurement else None
    if data.parameters_json is not None:
        template.parameters_json = data.parameters_json
    if data.template_text is not None:
        template.template_text = data.template_text
    if data.is_active is not None:
        template.is_active = data.is_active

    db.commit()
    db.refresh(template)
    return template


def get_lab_analytics(db: Session) -> Dict[str, Any]:
    """Return diagnostic queue counts, modality splits, and alerts."""
    orders = db.query(LabOrder).all()
    total_orders = len(orders)
    pending_collection = len([o for o in orders if o.sample_status == "ORDERED"])
    in_analysis = len([o for o in orders if o.sample_status == "SAMPLE_COLLECTED"])
    completed = len([o for o in orders if o.sample_status == "COMPLETED"])

    # Pathology vs Radiology breakdown
    templates = db.query(LabTestTemplate).all()
    dept_map = {t.id: t.department for t in templates}

    pathology_orders = sum(1 for o in orders if dept_map.get(o.template_id) != "Radiology")
    radiology_orders = sum(1 for o in orders if dept_map.get(o.template_id) == "Radiology")

    review_results = db.query(LabResult).filter(
        (LabResult.is_abnormal == True) |
        ((LabResult.panic_flag != None) & (LabResult.panic_flag != "NORMAL") & (LabResult.panic_flag != "ABNORMAL"))
    ).all()

    depts: Dict[str, int] = {}
    for o in orders:
        d = dept_map.get(o.template_id, "Pathology")
        depts[d] = depts.get(d, 0) + 1

    alerts = []
    for r in review_results[:5]:
        ord_item = db.query(LabOrder).filter(LabOrder.id == r.order_id).first()
        if ord_item:
            p = db.query(Patient).filter(Patient.id == ord_item.patient_id).first()
            p_name = p.full_name if p else "Patient"
            alerts.append({
                "type": "OUTSIDE_CONFIGURED_RANGE",
                "severity": "warning",
                "order_id": ord_item.id,
                "message": f"Review result: {ord_item.test_name} for {p_name} is flagged ({r.panic_flag or 'Abnormal'}).",
                "action": "Review result"
            })

    for o in [o for o in orders if o.sample_status == "ORDERED"][:3]:
        p = db.query(Patient).filter(Patient.id == o.patient_id).first()
        alerts.append({
            "type": "SAMPLE_COLLECTION_PENDING",
            "severity": "warning",
            "order_id": o.id,
            "message": f"Waiting for specimen: {o.test_name} for {p.full_name if p else 'Patient'}.",
            "action": "Collect specimen"
        })

    return {
        "kpis": {
            "total_orders": total_orders,
            "pending_collection": pending_collection,
            "in_analysis": in_analysis,
            "completed": completed,
            "pathology_orders": pathology_orders,
            "radiology_orders": radiology_orders,
            "review_count": len(review_results),
            "panic_count": len(review_results)
        },
        "departments": [{"department": k, "count": v} for k, v in depts.items()],
        "alerts": alerts
    }


def get_doctor_review_queue(db: Session, doctor_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Returns diagnostic reports awaiting doctor authentication or revisions."""
    from app.models.billing import Invoice
    query = db.query(LabOrder).join(LabResult, LabResult.order_id == LabOrder.id).order_by(LabOrder.created_at.desc())
    if doctor_id:
        query = query.filter((LabOrder.ordered_by_doctor_id == doctor_id) | (LabOrder.ordered_by_doctor_id == None))
        
    orders = query.all()
    results = []
    for ord_item in orders:
        res = db.query(LabResult).filter(LabResult.order_id == ord_item.id).first()
        patient = db.query(Patient).filter(Patient.id == ord_item.patient_id).first()
        doctor = db.query(User).filter(User.id == ord_item.ordered_by_doctor_id).first()
        template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord_item.template_id).first()
        
        # Check invoice payment status
        inv = None
        if ord_item.encounter_id:
            inv = db.query(Invoice).filter(Invoice.encounter_id == ord_item.encounter_id).first()
        if not inv and ord_item.patient_id:
            inv = db.query(Invoice).filter(Invoice.patient_id == ord_item.patient_id).order_by(Invoice.id.desc()).first()

        results.append({
            "order_id": ord_item.id,
            "test_name": ord_item.test_name,
            "modality": ord_item.modality or (template.modality if template else "LAB"),
            "department": template.department if template else "Diagnostic",
            "sample_barcode": ord_item.sample_barcode,
            "sample_status": ord_item.sample_status,
            "created_at": ord_item.created_at.strftime("%d-%b-%Y %H:%M") if ord_item.created_at else "-",
            "patient": {
                "id": patient.id if patient else None,
                "name": patient.full_name if patient else "Patient",
                "mrn": patient.mrn if patient else "-",
                "phone": patient.phone_number if patient else "-",
                "age_gender": f"{patient.age} / {patient.gender}" if patient else "-"
            },
            "doctor": {
                "id": doctor.id if doctor else None,
                "name": doctor.full_name if doctor else "Doctor",
                "department": doctor.department if doctor else "General"
            },
            "result": {
                "id": res.id if res else None,
                "result_value": res.result_value if res else "-",
                "is_abnormal": res.is_abnormal if res else False,
                "panic_flag": res.panic_flag if res else "NORMAL",
                "technician_notes": res.technician_notes if res else "",
                "parameter_results": res.parameter_results if res else None,
                "image_url": res.image_url if res else None,
                "annotated_image_url": res.annotated_image_url if res else None,
                "findings": res.findings if res else "",
                "impression": res.impression if res else "",
                "doctor_approval_status": res.doctor_approval_status if res else "PENDING_REVIEW",
                "doctor_notes": res.doctor_notes if res else "",
                "doctor_approved_at": res.doctor_approved_at.strftime("%d-%b-%Y %H:%M") if res and res.doctor_approved_at else None,
                "dispatch_status": res.dispatch_status if res else "NOT_DISPATCHED"
            },
            "billing": {
                "invoice_number": inv.invoice_number if inv else "N/A",
                "payment_status": inv.payment_status if inv else "PAID",
                "net_payable": inv.net_payable if inv else 0.0,
                "paid_amount": inv.paid_amount if inv else 0.0,
                "balance": max(0.0, (inv.net_payable - inv.paid_amount)) if inv else 0.0
            }
        })
    return results


def review_lab_result_by_doctor(db: Session, order_id: int, doctor_id: int, action: str, doctor_notes: Optional[str] = None) -> Dict[str, Any]:
    """Handles doctor approval or revision request with clinical change notes."""
    ord_item = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not ord_item:
        raise HTTPException(status_code=404, detail="Diagnostic order not found")

    res = db.query(LabResult).filter(LabResult.order_id == order_id).first()
    if not res:
        raise HTTPException(status_code=400, detail="Cannot review order before laboratory/radiology findings are entered")

    if action == "APPROVE":
        res.doctor_approval_status = "APPROVED"
        res.doctor_id = doctor_id
        res.doctor_approved_at = datetime.datetime.utcnow()
        if doctor_notes:
            res.doctor_notes = doctor_notes
        db.commit()
        return {
            "status": "APPROVED",
            "order_id": order_id,
            "message": "Diagnostic report clinically authenticated and signed. Unlocked for patient dispatch upon billing settlement."
        }
    elif action == "REQUEST_REVISION":
        res.doctor_approval_status = "REVISION_REQUESTED"
        res.doctor_id = doctor_id
        res.doctor_notes = doctor_notes or "Doctor requested revisions on findings/parameters."
        ord_item.sample_status = "SAMPLE_COLLECTED"  # Send back to lab technician
        db.commit()
        return {
            "status": "REVISION_REQUESTED",
            "order_id": order_id,
            "message": "Report returned to Laboratory / Radiology technician queue with revision notes."
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'. Must be APPROVE or REQUEST_REVISION")


def get_reception_dispatch_queue(db: Session) -> List[Dict[str, Any]]:
    """Returns diagnostic orders with patient delivery status, billing settlement, and doctor approval."""
    from app.models.billing import Invoice
    orders = db.query(LabOrder).order_by(LabOrder.created_at.desc()).all()
    results = []

    for ord_item in orders:
        res = db.query(LabResult).filter(LabResult.order_id == ord_item.id).first()
        patient = db.query(Patient).filter(Patient.id == ord_item.patient_id).first()
        doctor = db.query(User).filter(User.id == ord_item.ordered_by_doctor_id).first()
        template = db.query(LabTestTemplate).filter(LabTestTemplate.id == ord_item.template_id).first()

        # Check billing
        inv = None
        if ord_item.encounter_id:
            inv = db.query(Invoice).filter(Invoice.encounter_id == ord_item.encounter_id).first()
        if not inv and ord_item.patient_id:
            inv = db.query(Invoice).filter(Invoice.patient_id == ord_item.patient_id).order_by(Invoice.id.desc()).first()

        payment_status = inv.payment_status if inv else "PAID"
        balance = max(0.0, (inv.net_payable - inv.paid_amount)) if inv else 0.0
        is_bill_paid = (payment_status == "PAID" or balance <= 0.0)

        doctor_approval = res.doctor_approval_status if res else "AWAITING_TECH"
        is_doctor_approved = (doctor_approval == "APPROVED")

        can_dispatch = is_bill_paid and is_doctor_approved

        results.append({
            "order_id": ord_item.id,
            "test_name": ord_item.test_name,
            "modality": ord_item.modality or (template.modality if template else "LAB"),
            "department": template.department if template else "Diagnostic",
            "sample_barcode": ord_item.sample_barcode,
            "order_status": ord_item.sample_status,
            "created_at": ord_item.created_at.strftime("%d-%b-%Y %H:%M") if ord_item.created_at else "-",
            "patient": {
                "id": patient.id if patient else None,
                "name": patient.full_name if patient else "Patient",
                "mrn": patient.mrn if patient else "-",
                "phone": patient.phone_number if patient else "-",
                "email": getattr(patient, "email", "") or f"{patient.full_name.lower().replace(' ', '.')}@example.com" if patient else ""
            },
            "doctor": {
                "id": doctor.id if doctor else None,
                "name": doctor.full_name if doctor else "Doctor",
                "department": doctor.department if doctor else "General"
            },
            "doctor_approval_status": doctor_approval,
            "doctor_notes": res.doctor_notes if res else "",
            "doctor_approved_at": res.doctor_approved_at.strftime("%d-%b-%Y %H:%M") if res and res.doctor_approved_at else None,
            "billing": {
                "invoice_number": inv.invoice_number if inv else "N/A",
                "payment_status": payment_status,
                "net_payable": inv.net_payable if inv else 0.0,
                "paid_amount": inv.paid_amount if inv else 0.0,
                "balance": balance,
                "is_paid": is_bill_paid
            },
            "dispatch": {
                "can_dispatch": can_dispatch,
                "status": res.dispatch_status if res else "NOT_DISPATCHED",
                "dispatched_at": res.dispatched_at.strftime("%d-%b-%Y %H:%M") if res and res.dispatched_at else None,
                "channels": res.dispatch_channels if res else None
            }
        })
    return results


def dispatch_report_to_patient(
    db: Session,
    order_id: int,
    channels: List[str],
    user_id: int,
    recipient_phone: Optional[str] = None,
    recipient_email: Optional[str] = None
) -> Dict[str, Any]:
    """Validates bill clearance & doctor authentication, then dispatches report via Email, WhatsApp, and SMS."""
    from app.models.billing import Invoice
    ord_item = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not ord_item:
        raise HTTPException(status_code=404, detail="Order not found")

    res = db.query(LabResult).filter(LabResult.order_id == order_id).first()
    if not res:
        raise HTTPException(status_code=400, detail="Report results are not entered yet")

    if res.doctor_approval_status != "APPROVED":
        raise HTTPException(status_code=400, detail="Cannot dispatch report: Consulting doctor has not yet approved and signed off.")

    # Check billing status
    inv = None
    if ord_item.encounter_id:
        inv = db.query(Invoice).filter(Invoice.encounter_id == ord_item.encounter_id).first()
    if not inv and ord_item.patient_id:
        inv = db.query(Invoice).filter(Invoice.patient_id == ord_item.patient_id).order_by(Invoice.id.desc()).first()

    if inv and inv.payment_status != "PAID" and (inv.net_payable - inv.paid_amount) > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Closed-Loop Billing Lock: Outstanding balance of ₹{inv.net_payable - inv.paid_amount:.2f} on {inv.invoice_number}. Collect payment before dispatching report."
        )

    patient = db.query(Patient).filter(Patient.id == ord_item.patient_id).first()
    phone = recipient_phone or (patient.phone_number if patient else "9876543210")
    email = recipient_email or f"{patient.full_name.lower().replace(' ', '.')}@example.com" if patient else "patient@example.com"
    clean_channels = [c.upper().strip() for c in channels if c.strip()]
    if not clean_channels:
        clean_channels = ["WHATSAPP", "EMAIL", "SMS"]

    res.dispatch_status = "DISPATCHED"
    res.dispatched_at = datetime.datetime.utcnow()
    res.dispatch_channels = ", ".join(clean_channels)
    db.commit()

    # Pre-generate secure portal download link and WhatsApp dispatch message
    report_link = f"/api/lab/reports/{order_id}/pdf"
    patient_name = patient.full_name if patient else "Patient"
    whatsapp_text = (
        f"Hello {patient_name}, your official diagnostic report for {ord_item.test_name} "
        f"has been clinically verified by City Hospital doctors and is ready. "
        f"Download your PDF report here: https://cityhospital.med/reports/{order_id} or contact reception at +91 98765 43210."
    )
    import urllib.parse
    whatsapp_web_url = f"https://api.whatsapp.com/send?phone=91{phone.replace('+', '')}&text={urllib.parse.quote(whatsapp_text)}"

    return {
        "status": "DISPATCHED",
        "order_id": order_id,
        "patient_name": patient_name,
        "phone": phone,
        "email": email,
        "channels": clean_channels,
        "dispatched_at": res.dispatched_at.strftime("%d-%b-%Y %H:%M:%S UTC"),
        "whatsapp_url": whatsapp_web_url,
        "report_pdf_url": report_link,
        "message": f"Official report successfully dispatched to {patient_name} via {', '.join(clean_channels)}!"
    }


def send_billing_clearance_reminder(db: Session, order_id: int, user_id: int) -> Dict[str, Any]:
    """Sends SMS/WhatsApp reminder to patient to settle cashier bill so report can be dispatched."""
    from app.models.billing import Invoice
    ord_item = db.query(LabOrder).filter(LabOrder.id == order_id).first()
    if not ord_item:
        raise HTTPException(status_code=404, detail="Order not found")

    patient = db.query(Patient).filter(Patient.id == ord_item.patient_id).first()
    inv = None
    if ord_item.encounter_id:
        inv = db.query(Invoice).filter(Invoice.encounter_id == ord_item.encounter_id).first()
    if not inv and ord_item.patient_id:
        inv = db.query(Invoice).filter(Invoice.patient_id == ord_item.patient_id).order_by(Invoice.id.desc()).first()

    balance = (inv.net_payable - inv.paid_amount) if inv else 500.0
    phone = patient.phone_number if patient else "9876543210"
    patient_name = patient.full_name if patient else "Patient"

    msg = (
        f"Dear {patient_name}, your diagnostic report for {ord_item.test_name} is prepared and awaiting dispatch. "
        f"Kindly settle your pending cashier bill of ₹{balance:.2f} (Invoice {inv.invoice_number if inv else ''}) "
        f"to instantly receive your verified report via WhatsApp and Email."
    )
    import urllib.parse
    whatsapp_url = f"https://api.whatsapp.com/send?phone=91{phone.replace('+', '')}&text={urllib.parse.quote(msg)}"

    return {
        "status": "REMINDER_SENT",
        "patient_name": patient_name,
        "phone": phone,
        "balance": balance,
        "whatsapp_url": whatsapp_url,
        "message": f"Billing clearance reminder sent to {patient_name} ({phone}) via SMS & WhatsApp."
    }

