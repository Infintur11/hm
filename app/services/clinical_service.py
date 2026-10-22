from sqlalchemy.orm import Session
from app.models.clinical import VitalSigns, Encounter, TreatmentTemplate
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.pharmacy import Medicine, PrescriptionItem
from app.models.lab import LabTestTemplate, LabOrder
from app.models.billing import Invoice, InvoiceItem
from app.models.user import User
from app.schemas.clinical import VitalsCreate, EncounterCreate
from fastapi import HTTPException
from typing import List, Dict, Any, Optional
import datetime

def record_vitals(db: Session, data: VitalsCreate, recorded_by_id: int) -> VitalSigns:
    """Calculates BMI, evaluates clinical thresholds, flags abnormalities."""
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient ID #{data.patient_id} does not exist in hospital records.")

    bmi = None
    if data.weight_kg and data.height_cm and data.height_cm > 0:
        height_m = data.height_cm / 100.0
        bmi = round(data.weight_kg / (height_m * height_m), 1)

    # Evaluate clinical flags
    flags = []
    is_abnormal = False
    
    if data.blood_pressure_systolic:
        if data.blood_pressure_systolic >= 140 or (data.blood_pressure_diastolic and data.blood_pressure_diastolic >= 90):
            flags.append("Hypertension")
            is_abnormal = True
        elif data.blood_pressure_systolic <= 90:
            flags.append("Hypotension")
            is_abnormal = True

    if data.temperature_f and data.temperature_f >= 99.5:
        flags.append("Pyrexia (Fever)")
        is_abnormal = True

    if data.heart_rate_bpm:
        if data.heart_rate_bpm > 100:
            flags.append("Tachycardia")
            is_abnormal = True
        elif data.heart_rate_bpm < 60:
            flags.append("Bradycardia")
            is_abnormal = True

    if data.spo2_percent and data.spo2_percent < 94:
        flags.append("Hypoxemia (Low SpO2)")
        is_abnormal = True

    vitals = VitalSigns(
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        recorded_by_id=recorded_by_id,
        temperature_f=data.temperature_f,
        blood_pressure_systolic=data.blood_pressure_systolic,
        blood_pressure_diastolic=data.blood_pressure_diastolic,
        heart_rate_bpm=data.heart_rate_bpm,
        respiratory_rate=data.respiratory_rate,
        spo2_percent=data.spo2_percent,
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        bmi=bmi,
        is_abnormal=is_abnormal,
        clinical_flags=", ".join(flags) if flags else None,
        triage_notes=data.triage_notes
    )
    db.add(vitals)
    db.commit()
    db.refresh(vitals)
    return vitals

def get_latest_vitals(db: Session, patient_id: int) -> Dict[str, Any]:
    vitals = db.query(VitalSigns).filter(VitalSigns.patient_id == patient_id).order_by(VitalSigns.recorded_at.desc()).first()
    if not vitals:
        return {}
    return {
        "id": vitals.id,
        "temperature_f": vitals.temperature_f,
        "bp": f"{vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}" if vitals.blood_pressure_systolic else None,
        "heart_rate_bpm": vitals.heart_rate_bpm,
        "spo2_percent": vitals.spo2_percent,
        "bmi": vitals.bmi,
        "is_abnormal": vitals.is_abnormal,
        "clinical_flags": vitals.clinical_flags,
        "recorded_at": vitals.recorded_at.strftime("%d-%b %H:%M")
    }

def get_recent_vitals(db: Session, limit: int = 30) -> List[Dict[str, Any]]:
    """Fetches recent triage vitals records with clinical parameters, timestamps, and patient metadata."""
    records = db.query(VitalSigns).order_by(VitalSigns.recorded_at.desc()).limit(limit).all()
    results = []
    for v in records:
        p = db.query(Patient).filter(Patient.id == v.patient_id).first()
        u = db.query(User).filter(User.id == v.recorded_by_id).first() if v.recorded_by_id else None
        
        # Calculate human-readable relative time
        now = datetime.datetime.utcnow()
        diff = (now - v.recorded_at).total_seconds() if v.recorded_at else 0
        if diff < 60:
            rel_time = "Just now"
        elif diff < 3600:
            rel_time = f"{int(diff // 60)} min ago"
        elif diff < 86400:
            rel_time = f"{int(diff // 3600)} hr ago"
        else:
            rel_time = f"{int(diff // 86400)} days ago"

        results.append({
            "id": v.id,
            "patient_id": v.patient_id,
            "patient_name": p.full_name if p else f"Patient #{v.patient_id}",
            "patient_mrn": p.mrn if p else "N/A",
            "patient_meta": f"{p.age}y/{p.gender} • Blood: {p.blood_group or '-'}" if p else "",
            "temperature_f": v.temperature_f,
            "bp_systolic": v.blood_pressure_systolic,
            "bp_diastolic": v.blood_pressure_diastolic,
            "bp_display": f"{v.blood_pressure_systolic}/{v.blood_pressure_diastolic} mmHg" if (v.blood_pressure_systolic and v.blood_pressure_diastolic) else "-",
            "heart_rate_bpm": v.heart_rate_bpm,
            "respiratory_rate": v.respiratory_rate,
            "spo2_percent": v.spo2_percent,
            "weight_kg": v.weight_kg,
            "height_cm": v.height_cm,
            "bmi": v.bmi,
            "is_abnormal": v.is_abnormal,
            "clinical_flags": v.clinical_flags,
            "triage_notes": v.triage_notes,
            "recorded_by_name": u.full_name if u else "Triage Nurse",
            "recorded_at_iso": v.recorded_at.isoformat() if v.recorded_at else "",
            "recorded_at_display": v.recorded_at.strftime("%d-%b-%Y %H:%M:%S") if v.recorded_at else "",
            "relative_time": rel_time
        })
    return results

def finalize_encounter(db: Session, data: EncounterCreate) -> Dict[str, Any]:
    """
    Submits doctor SOAP encounter.
    1. Saves encounter record.
    2. Generates prescription items.
    3. Orders selected lab investigations.
    4. Auto-generates consolidated pending invoice for cashier.
    5. Marks appointment completed.
    """
    encounter = Encounter(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        appointment_id=data.appointment_id,
        chief_complaint=data.chief_complaint,
        clinical_notes=data.clinical_notes,
        diagnosis=data.diagnosis,
        icd10_code=data.icd10_code,
        admission_recommended=data.admission_recommended,
        admission_ward_preference=data.admission_ward_preference,
        admission_instructions=data.admission_instructions,
        status="FINALIZED"
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)

    # 1. Invoicing & Prescriptions
    invoice_items = []
    doctor = db.query(User).filter(User.id == data.doctor_id).first()
    doctor_fee = doctor.consultation_fee if doctor else 500
    doc_title = doctor.full_name if (doctor and doctor.full_name.startswith("Dr.")) else f"Dr. {doctor.full_name}" if doctor else "Specialist"

    # Avoid duplicate consultation fee if already billed at reception appointment booking
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    already_billed = db.query(InvoiceItem).join(Invoice).filter(
        Invoice.patient_id == data.patient_id,
        InvoiceItem.item_type == "CONSULTATION",
        Invoice.created_at >= today_start
    ).first()

    if not already_billed:
        invoice_items.append({
            "type": "CONSULTATION",
            "description": f"OPD Consultation - {doc_title}",
            "qty": 1,
            "rate": doctor_fee
        })

    for rx in data.prescriptions:
        med = None
        if rx.medicine_id:
            med = db.query(Medicine).filter(Medicine.id == rx.medicine_id).first()
            
        unit_price = med.unit_price if med else 15.0
        presc_item = PrescriptionItem(
            encounter_id=encounter.id,
            patient_id=data.patient_id,
            medicine_id=rx.medicine_id,
            medicine_name=rx.medicine_name,
            dosage=rx.dosage,
            frequency=rx.frequency,
            duration_days=rx.duration_days,
            instructions=rx.instructions,
            quantity_prescribed=rx.quantity,
            is_dispensed=False
        )
        db.add(presc_item)
        invoice_items.append({
            "type": "PHARMACY",
            "description": f"Rx: {rx.medicine_name} ({rx.dosage} x {rx.quantity})",
            "qty": rx.quantity,
            "rate": unit_price
        })

    # 2. Create Lab Orders
    for template_id in data.lab_test_template_ids:
        template = db.query(LabTestTemplate).filter(LabTestTemplate.id == template_id).first()
        if template:
            lab_order = LabOrder(
                encounter_id=encounter.id,
                patient_id=data.patient_id,
                ordered_by_doctor_id=data.doctor_id,
                template_id=template.id,
                test_name=template.test_name,
                sample_status="ORDERED",
                sample_barcode=f"SMP-{int(datetime.datetime.utcnow().timestamp()) % 100000:05d}"
            )
            db.add(lab_order)
            invoice_items.append({
                "type": "LAB_TEST",
                "description": f"Lab Investigation: {template.test_name}",
                "qty": 1,
                "rate": template.standard_rate
            })

    # 3. Mark appointment completed
    if data.appointment_id:
        appt = db.query(Appointment).filter(Appointment.id == data.appointment_id).first()
        if appt:
            appt.status = "COMPLETED"

    # 4. Generate Consolidated Cashier Invoice if items exist
    inv_id = None
    inv_num = None
    total_amount = 0.0
    if invoice_items:
        total_amount = sum(item["qty"] * item["rate"] for item in invoice_items)
        inv_count = db.query(Invoice).count() + 1
        invoice = Invoice(
            invoice_number=f"INV-2026-{inv_count:04d}",
            patient_id=data.patient_id,
            encounter_id=encounter.id,
            total_amount=total_amount,
            net_payable=total_amount,
            paid_amount=0.0,
            payment_status="UNPAID",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        for itm in invoice_items:
            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                item_type=itm["type"],
                description=itm["description"],
                quantity=itm["qty"],
                unit_price=itm["rate"],
                total_price=itm["qty"] * itm["rate"]
            )
            db.add(inv_item)

        db.commit()
        inv_id = invoice.id
        inv_num = invoice.invoice_number

    return {
        "encounter_id": encounter.id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "total_payable": total_amount,
        "admission_recommended": data.admission_recommended
    }

def get_doctor_analytics(db: Session, doctor_id: int = None) -> Dict[str, Any]:
    """
    Computes doctor clinical KPIs, queue progress, and patient risk alerts
    (abnormal triage vitals, critical allergies, pending lab diagnostics).
    """
    today_str = datetime.date.today().isoformat()
    from app.models.patient import Patient
    from app.models.lab import LabOrder, LabResult

    query = db.query(Appointment).filter(Appointment.appointment_date == today_str, Appointment.status != "CANCELLED")
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)

    appts = query.order_by(Appointment.token_number.asc()).all()
    queue_total = len(appts)
    completed = len([a for a in appts if a.status == "COMPLETED"])
    waiting = len([a for a in appts if a.status in ["CHECKED_IN", "SCHEDULED"]])

    alerts = []
    abnormal_vitals_count = 0
    allergy_count = 0

    for a in appts:
        patient = db.query(Patient).filter(Patient.id == a.patient_id).first()
        if not patient:
            continue

        # Check known allergies
        if patient.allergies and "none" not in patient.allergies.lower():
            allergy_count += 1
            if a.status != "COMPLETED":
                alerts.append({
                    "type": "CRITICAL_ALLERGY",
                    "severity": "danger",
                    "patient_id": patient.id,
                    "patient_name": patient.full_name,
                    "message": f"Critical Drug Allergy Warning: {patient.full_name} has documented allergy to {patient.allergies}. Review Rx carefully.",
                    "action": "Review Allergy"
                })

        # Check latest vitals for waiting patients
        vitals = db.query(VitalSigns).filter(VitalSigns.patient_id == patient.id).order_by(VitalSigns.recorded_at.desc()).first()
        if vitals and vitals.is_abnormal:
            abnormal_vitals_count += 1
            if a.status != "COMPLETED":
                alerts.append({
                    "type": "ABNORMAL_VITALS",
                    "severity": "danger",
                    "patient_id": patient.id,
                    "patient_name": patient.full_name,
                    "message": f"Physiological Anomaly Alert: {patient.full_name} triage flagged with {vitals.clinical_flags or 'abnormal vitals'} (BP: {vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}, SpO2: {vitals.spo2_percent}%).",
                    "action": "Triage Review"
                })

    # Check panic lab results for this doctor's patients
    lab_query = db.query(LabOrder).join(LabResult, LabResult.order_id == LabOrder.id).filter(
        LabResult.is_abnormal == True
    )
    if doctor_id:
        lab_query = lab_query.filter(LabOrder.ordered_by_doctor_id == doctor_id)
    abnormal_labs = lab_query.limit(5).all()

    for l in abnormal_labs:
        p = db.query(Patient).filter(Patient.id == l.patient_id).first()
        alerts.append({
            "type": "LAB_PANIC_RESULT",
            "severity": "warning",
            "patient_id": l.patient_id,
            "patient_name": p.full_name if p else "Patient",
            "message": f"Diagnostic Anomaly: {l.test_name} for {p.full_name if p else 'Patient'} returned out-of-range value.",
            "action": "Inspect Lab"
        })

    return {
        "kpis": {
            "queue_total": queue_total,
            "completed": completed,
            "waiting": waiting,
            "abnormal_vitals_count": abnormal_vitals_count,
            "allergy_count": allergy_count
        },
        "alerts": alerts
    }
