from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.models.user import User
from app.models.patient import Patient
from app.models.billing import Invoice, InvoiceItem
from app.schemas.appointment import AppointmentCreate
from fastapi import HTTPException
from typing import List, Dict, Any
import datetime

def book_appointment(db: Session, data: AppointmentCreate) -> Appointment:
    """Books an OPD appointment with slot conflict verification and token assignment."""
    # Verify doctor exists
    doctor = db.query(User).filter(User.id == data.doctor_id, User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    # Slot conflict check (single slot per doctor)
    existing = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.appointment_date == data.appointment_date,
        Appointment.time_slot == data.time_slot,
        Appointment.status != "CANCELLED"
    ).first()
    
    if existing:
        doc_title = doctor.full_name if doctor.full_name.startswith("Dr.") else f"Dr. {doctor.full_name}"
        raise HTTPException(
            status_code=400,
            detail=f"Time slot {data.time_slot} is already booked for {doc_title} on {data.appointment_date}."
        )
        
    # Generate daily sequential token number for this doctor & date
    daily_count = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.appointment_date == data.appointment_date
    ).count()
    token = daily_count + 1
    
    appointment = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        department=data.department,
        appointment_date=data.appointment_date,
        time_slot=data.time_slot,
        token_number=token,
        status="SCHEDULED",
        reason_for_visit=data.reason_for_visit
    )
    db.add(appointment)
    db.flush()

    # Automatically generate OPD Consultation Invoice in Billing Queue
    fee = float(doctor.consultation_fee or 0.0)
    if fee > 0:
        inv_count = db.query(Invoice).count() + 1
        inv_num = f"INV-2026-{inv_count:04d}"
        invoice = Invoice(
            invoice_number=inv_num,
            patient_id=data.patient_id,
            total_amount=fee,
            net_payable=fee,
            paid_amount=0.0,
            payment_status="UNPAID",
        )
        db.add(invoice)
        db.flush()
        doc_display = doctor.full_name if doctor.full_name.startswith("Dr.") else f"Dr. {doctor.full_name}"
        inv_item = InvoiceItem(
            invoice_id=invoice.id,
            item_type="CONSULTATION",
            description=f"OPD Consultation - {doc_display} ({doctor.department})",
            quantity=1,
            unit_price=fee,
            total_price=fee
        )
        db.add(inv_item)

    db.commit()
    db.refresh(appointment)
    return appointment

def get_doctor_queue(db: Session, doctor_id: int, date_str: str) -> List[Dict[str, Any]]:
    """Fetches ordered OPD queue for doctor with live status."""
    appointments = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == date_str,
        Appointment.status != "CANCELLED"
    ).order_by(Appointment.token_number.asc()).all()
    
    queue = []
    for appt in appointments:
        patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
        queue.append({
            "id": appt.id,
            "doctor_id": appt.doctor_id,
            "token_number": appt.token_number,
            "patient_id": appt.patient_id,
            "patient_name": patient.full_name if patient else "Unknown",
            "patient_phone": patient.phone_number if patient else "",
            "patient_mrn": patient.mrn if patient else "",
            "age": patient.age if patient else "-",
            "gender": patient.gender if patient else "-",
            "time_slot": appt.time_slot,
            "status": appt.status,
            "reason_for_visit": appt.reason_for_visit,
        })
    return queue

def update_appointment_status(db: Session, appt_id: int, status: str) -> Appointment:
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt.status = status
    db.commit()
    db.refresh(appt)
    return appt

def get_reception_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes real-time OPD intake KPIs, doctor capacity utilization,
    and front-desk actionable alerts for the receptionist workstation.
    """
    today_str = datetime.date.today().isoformat()
    
    # 1. Today's appointments
    today_appts = db.query(Appointment).filter(Appointment.appointment_date == today_str, Appointment.status != "CANCELLED").all()
    total_appts = len(today_appts)
    checked_in = len([a for a in today_appts if a.status == "CHECKED_IN"])
    completed = len([a for a in today_appts if a.status == "COMPLETED"])
    scheduled = len([a for a in today_appts if a.status == "SCHEDULED"])

    # 2. Total registered patients
    total_patients = db.query(Patient).count()

    # 3. Doctor Capacity Utilization
    doctors = db.query(User).filter(User.role == "DOCTOR", User.is_active == True).all()
    doc_capacity = []
    alerts = []

    for doc in doctors:
        doc_appts = [a for a in today_appts if a.doctor_id == doc.id]
        booked_count = len(doc_appts)
        max_slots = 12 # Standard 12 slots per OPD session (3 hours @ 15 min slots)
        utilization_pct = min(round((booked_count / max_slots * 100), 1), 100.0)
        
        doc_name = doc.full_name if doc.full_name.startswith("Dr.") else f"Dr. {doc.full_name}"

        status = "AVAILABLE"
        if booked_count >= max_slots:
            status = "FULL"
            alerts.append({
                "type": "CAPACITY_FULL",
                "severity": "danger",
                "doctor_id": doc.id,
                "message": f"OPD Full: {doc_name} ({doc.department}) has reached 100% capacity ({booked_count}/{max_slots} slots). Direct walk-ins to alternate physician.",
                "action": "View Schedule"
            })
        elif booked_count >= max_slots * 0.75:
            status = "NEAR_CAPACITY"
            alerts.append({
                "type": "NEAR_CAPACITY",
                "severity": "warning",
                "doctor_id": doc.id,
                "message": f"High Demand: {doc_name} ({doc.department}) has {max_slots - booked_count} slot(s) remaining ({booked_count}/{max_slots} booked).",
                "action": "Guide Walk-in"
            })

        doc_capacity.append({
            "doctor_id": doc.id,
            "doctor_name": doc_name,
            "department": doc.department,
            "booked_slots": booked_count,
            "max_slots": max_slots,
            "available_slots": max(0, max_slots - booked_count),
            "utilization_pct": utilization_pct,
            "status": status
        })

    # Alert for waiting patients
    if checked_in > 5:
        alerts.append({
            "type": "WAITING_SURGE",
            "severity": "warning",
            "message": f"Waiting Area Surge: {checked_in} patients are currently checked in. Coordinate with Triage Nurse.",
            "action": "View Waiting"
        })

    return {
        "kpis": {
            "today_appointments": total_appts,
            "checked_in_waiting": checked_in,
            "completed_consultations": completed,
            "scheduled_upcoming": scheduled,
            "total_patients": total_patients,
            "active_doctors": len(doctors)
        },
        "doctor_capacity": doc_capacity,
        "alerts": alerts
    }
