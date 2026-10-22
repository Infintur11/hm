from sqlalchemy.orm import Session
from app.models.inpatient import Bed, InpatientRecord, InpatientMedicationOrder
from app.models.patient import Patient
from app.models.user import User
from app.models.lab import LabOrder
from app.models.billing import Invoice, InvoiceItem
from app.schemas.inpatient import AdmissionCreate, DischargeOrder, IPMOAdminister, IPMOCreate
from fastapi import HTTPException
from typing import List, Dict, Any
import datetime

def get_bed_matrix(db: Session) -> Dict[str, List[Dict[str, Any]]]:
    """Returns visual bed floorplan grouped by ward with status chips."""
    beds = db.query(Bed).all()
    matrix = {}
    for bed in beds:
        patient_name = None
        if bed.current_patient_id:
            p = db.query(Patient).filter(Patient.id == bed.current_patient_id).first()
            patient_name = p.full_name if p else "Patient"

        if bed.ward_name not in matrix:
            matrix[bed.ward_name] = []
        matrix[bed.ward_name].append({
            "id": bed.id,
            "bed_number": bed.bed_number,
            "ward_name": bed.ward_name,
            "bed_type": bed.bed_type,
            "daily_rate": bed.daily_rate,
            "status": bed.status, # VACANT, OCCUPIED, CLEANING
            "current_patient_id": bed.current_patient_id,
            "patient_name": patient_name
        })
    return matrix

def admit_patient(db: Session, data: AdmissionCreate) -> InpatientRecord:
    """Allocates bed, checks vacancy, sets bed to OCCUPIED and creates InpatientRecord."""
    bed = db.query(Bed).filter(Bed.id == data.bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status != "VACANT":
        raise HTTPException(status_code=400, detail=f"Bed {bed.bed_number} is currently {bed.status}.")

    ip_count = db.query(InpatientRecord).count() + 1
    ip_number = f"IPD-2026-{ip_count:04d}"

    record = InpatientRecord(
        ip_number=ip_number,
        patient_id=data.patient_id,
        bed_id=data.bed_id,
        attending_doctor_id=data.attending_doctor_id,
        admission_date=datetime.datetime.utcnow(),
        expected_discharge_date=datetime.datetime.utcnow() + datetime.timedelta(days=data.expected_days),
        admission_reason=data.admission_reason,
        status="ADMITTED"
    )
    db.add(record)

    # Update bed
    bed.status = "OCCUPIED"
    bed.current_patient_id = data.patient_id

    db.commit()
    db.refresh(record)
    return record

def create_ipmo(db: Session, data: IPMOCreate) -> InpatientMedicationOrder:
    """Schedules a new medication dose on the inpatient nurse administration chart."""
    record = db.query(InpatientRecord).filter(InpatientRecord.id == data.inpatient_record_id).first()
    if not record or record.status != "ADMITTED":
        raise HTTPException(status_code=400, detail="Active inpatient admission record not found")

    order = InpatientMedicationOrder(
        inpatient_record_id=data.inpatient_record_id,
        patient_id=data.patient_id,
        medicine_name=data.medicine_name,
        dosage=data.dosage,
        frequency=data.frequency,
        route=data.route,
        scheduled_slot=data.scheduled_slot,
        status="PENDING",
        notes=data.notes
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def administer_ipmo(db: Session, data: IPMOAdminister, nurse_id: int) -> InpatientMedicationOrder:
    order = db.query(InpatientMedicationOrder).filter(InpatientMedicationOrder.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Medication order not found")
        
    order.status = "ADMINISTERED"
    order.administered_at = datetime.datetime.utcnow()
    order.administered_by_id = nurse_id
    if data.notes:
        order.notes = data.notes

    db.commit()
    db.refresh(order)
    return order

def check_discharge_clearance(db: Session, inpatient_record_id: int) -> Dict[str, Any]:
    """
    Evaluates the Discharge Billing Block Invariant:
    1. Open/unadministered Inpatient Medication Orders (IPMO) on the nurse chart
    2. Open/incomplete laboratory test investigations for this patient
    3. Unpaid or partially paid patient invoices
    """
    record = db.query(InpatientRecord).filter(InpatientRecord.id == inpatient_record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Inpatient record not found")

    patient = db.query(Patient).filter(Patient.id == record.patient_id).first()

    # 1. Check pending medication logs
    pending_ipmo = db.query(InpatientMedicationOrder).filter(
        InpatientMedicationOrder.inpatient_record_id == record.id,
        InpatientMedicationOrder.status == "PENDING"
    ).all()

    # 2. Check open / incomplete lab tests
    open_labs = db.query(LabOrder).filter(
        LabOrder.patient_id == record.patient_id,
        LabOrder.sample_status.in_(["ORDERED", "SAMPLE_COLLECTED", "ANALYZING"])
    ).all()

    # 3. Check unpaid prior invoices
    unpaid_invoices = db.query(Invoice).filter(
        Invoice.patient_id == record.patient_id,
        Invoice.payment_status.in_(["UNPAID", "PARTIAL"])
    ).all()

    blocking_reasons = []
    if pending_ipmo:
        med_names = ", ".join([o.medicine_name for o in pending_ipmo[:3]])
        suffix = "..." if len(pending_ipmo) > 3 else ""
        blocking_reasons.append(f"{len(pending_ipmo)} unadministered medication order(s) on nurse chart ({med_names}{suffix})")
    if open_labs:
        lab_names = ", ".join([l.test_name for l in open_labs[:3]])
        suffix = "..." if len(open_labs) > 3 else ""
        blocking_reasons.append(f"{len(open_labs)} open/uncompleted lab investigation(s) ({lab_names}{suffix})")
    if unpaid_invoices:
        inv_nums = ", ".join([inv.invoice_number for inv in unpaid_invoices[:3]])
        suffix = "..." if len(unpaid_invoices) > 3 else ""
        blocking_reasons.append(f"{len(unpaid_invoices)} unpaid bill(s) ({inv_nums}{suffix})")

    can_discharge = len(blocking_reasons) == 0

    return {
        "can_discharge": can_discharge,
        "record_id": record.id,
        "ip_number": record.ip_number,
        "patient_id": record.patient_id,
        "patient_name": patient.full_name if patient else "Patient",
        "pending_medications_count": len(pending_ipmo),
        "open_labs_count": len(open_labs),
        "unpaid_invoices_count": len(unpaid_invoices),
        "blocking_reasons": blocking_reasons,
        "pending_medications": [
            {
                "id": o.id,
                "medicine_name": o.medicine_name,
                "dosage": o.dosage,
                "frequency": o.frequency,
                "scheduled_slot": o.scheduled_slot
            } for o in pending_ipmo
        ],
        "open_labs": [
            {
                "id": l.id,
                "test_name": l.test_name,
                "sample_status": l.sample_status,
                "sample_barcode": l.sample_barcode
            } for l in open_labs
        ],
        "unpaid_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "net_payable": inv.net_payable,
                "paid_amount": inv.paid_amount,
                "payment_status": inv.payment_status
            } for inv in unpaid_invoices
        ]
    }

def discharge_patient(db: Session, data: DischargeOrder) -> Dict[str, Any]:
    """
    Enforces Discharge Billing Block Invariant:
    Blocks discharge while there are open, unbilled tests or medication logs,
    unless an explicit emergency clinical override reason is recorded.
    When cleared, calculates bed stay charges, generates inpatient invoice,
    and transitions bed status to CLEANING.
    """
    record = db.query(InpatientRecord).filter(InpatientRecord.id == data.inpatient_record_id).first()
    if not record or record.status != "ADMITTED":
        raise HTTPException(status_code=400, detail="Active inpatient record not found")

    # Invariant Check: Discharge Billing & Clinical Block
    clearance = check_discharge_clearance(db, data.inpatient_record_id)
    if not clearance["can_discharge"]:
        if not data.allow_override or not (data.override_reason and data.override_reason.strip()):
            reasons_summary = "; ".join(clearance["blocking_reasons"])
            raise HTTPException(
                status_code=403,
                detail=f"Discharge Billing Block Invariant: Discharge blocked for {record.ip_number}. Outstanding items: {reasons_summary}. Complete all diagnostic tests, administer/omit scheduled medication logs, and settle unpaid bills before discharge clearance."
            )
        else:
            # Audit trail: Log manual emergency override pathway
            record.discharge_summary = f"[EMERGENCY OVERRIDE: {data.override_reason.strip()}] " + (data.discharge_summary or "")
    else:
        record.discharge_summary = data.discharge_summary

    discharge_time = datetime.datetime.utcnow()
    record.discharge_date = discharge_time
    record.status = "DISCHARGED"
    record.discharge_condition = data.discharge_condition

    bed = db.query(Bed).filter(Bed.id == record.bed_id).first()
    days_stayed = max(1, (discharge_time - record.admission_date).days)
    bed_charges = days_stayed * bed.daily_rate if bed else 1500

    if bed:
        bed.status = "CLEANING"
        bed.current_patient_id = None

    # Generate Inpatient Invoice
    inv_count = db.query(Invoice).count() + 1
    invoice = Invoice(
        invoice_number=f"INV-2026-{inv_count:04d}",
        patient_id=record.patient_id,
        inpatient_record_id=record.id,
        total_amount=bed_charges,
        net_payable=bed_charges,
        paid_amount=0.0,
        payment_status="UNPAID"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    inv_item = InvoiceItem(
        invoice_id=invoice.id,
        item_type="BED_CHARGE",
        description=f"Inpatient Stay: {bed.ward_name if bed else 'Ward'} ({bed.bed_number if bed else 'Bed'}) - {days_stayed} Day(s)",
        quantity=days_stayed,
        unit_price=bed.daily_rate if bed else 1500,
        total_price=bed_charges
    )
    db.add(inv_item)
    db.commit()

    return {
        "status": "DISCHARGED",
        "ip_number": record.ip_number,
        "days_stayed": days_stayed,
        "total_bed_charges": bed_charges,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "override_applied": bool(data.allow_override and data.override_reason)
    }

def get_nurse_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes real-time bed occupancy, IPMO shift medication administration stats,
    ward breakdown, and actionable nursing alerts.
    """
    beds = db.query(Bed).all()
    total_beds = len(beds)
    occupied_beds = len([b for b in beds if b.status == "OCCUPIED"])
    vacant_beds = len([b for b in beds if b.status == "VACANT"])
    cleaning_beds = len([b for b in beds if b.status == "CLEANING"])
    occupancy_pct = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

    # Ward breakdown
    wards: Dict[str, Dict[str, Any]] = {}
    for b in beds:
        w = b.ward_name
        if w not in wards:
            wards[w] = {"ward": w, "total": 0, "occupied": 0, "vacant": 0, "cleaning": 0}
        wards[w]["total"] += 1
        if b.status == "OCCUPIED":
            wards[w]["occupied"] += 1
        elif b.status == "VACANT":
            wards[w]["vacant"] += 1
        elif b.status == "CLEANING":
            wards[w]["cleaning"] += 1

    # IPMO stats
    pending_ipmo = db.query(InpatientMedicationOrder).filter(InpatientMedicationOrder.status == "PENDING").all()
    admin_ipmo_count = db.query(InpatientMedicationOrder).filter(InpatientMedicationOrder.status == "ADMINISTERED").count()
    admitted_count = db.query(InpatientRecord).filter(InpatientRecord.status == "ADMITTED").count()

    alerts = []

    # 1. Cleaning bed turnaround alerts
    for b in beds:
        if b.status == "CLEANING":
            alerts.append({
                "type": "BED_CLEANING_REQUIRED",
                "severity": "warning",
                "bed_id": b.id,
                "message": f"Bed Turnaround: Bed {b.bed_number} ({b.ward_name}) requires sanitization. Click to sanitize and mark VACANT.",
                "action": "Sanitize Bed"
            })

    # 2. Overdue / Pending IPMO medication dose alerts
    for o in pending_ipmo[:5]:
        p = db.query(Patient).filter(Patient.id == o.patient_id).first()
        p_name = p.full_name if p else "Patient"
        alerts.append({
            "type": "IPMO_DOSE_DUE",
            "severity": "danger",
            "order_id": o.id,
            "message": f"Medication Due: {p_name} is scheduled for {o.medicine_name} ({o.dosage}) - {o.scheduled_slot} slot.",
            "action": "Administer"
        })

    return {
        "kpis": {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "vacant_beds": vacant_beds,
            "cleaning_beds": cleaning_beds,
            "occupancy_rate_pct": occupancy_pct,
            "pending_ipmo_doses": len(pending_ipmo),
            "administered_ipmo_doses": admin_ipmo_count,
            "admitted_inpatients": admitted_count
        },
        "wards": list(wards.values()),
        "alerts": alerts
    }

