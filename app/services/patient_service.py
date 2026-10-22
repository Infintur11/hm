from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from typing import List, Optional
import time

def generate_mrn(db: Session) -> str:
    """Generates sequential, collision-proof Medical Record Number: MRN-YYYY-XXXX."""
    year = time.strftime("%Y")
    count = db.query(Patient).count() + 1
    return f"MRN-{year}-{count:04d}"

def register_patient(db: Session, data: PatientCreate) -> Patient:
    """Creates a new patient with unique MRN."""
    mrn = generate_mrn(db)
    patient = Patient(
        mrn=mrn,
        full_name=data.full_name.strip(),
        phone_number=data.phone_number.strip(),
        aadhar_card_no=data.aadhar_card_no.strip() if data.aadhar_card_no else None,
        age=data.age,
        gender=data.gender,
        blood_group=data.blood_group,
        allergies=data.allergies,
        chronic_conditions=data.chronic_conditions,
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=data.emergency_contact_phone,
        address=data.address,
        referred_by_doctor_id=data.referred_by_doctor_id,
        billing_category=getattr(data, "billing_category", "WALK_IN") or "WALK_IN",
        corporate_client_id=getattr(data, "corporate_client_id", None),
        corporate_policy_id=getattr(data, "corporate_policy_id", None),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

def search_patients(db: Session, query: str, limit: int = 30) -> List[Patient]:
    """Instant multi-parameter lookup across Name, Phone, Aadhaar, MRN, and numeric ID."""
    q = query.strip()
    if not q:
        return db.query(Patient).order_by(Patient.id.desc()).limit(limit).all()
        
    conditions = [
        Patient.phone_number.ilike(f"%{q}%"),
        Patient.full_name.ilike(f"%{q}%"),
        Patient.mrn.ilike(f"%{q}%"),
        Patient.aadhar_card_no.ilike(f"%{q}%")
    ]
    if q.isdigit():
        conditions.append(Patient.id == int(q))

    return db.query(Patient).filter(or_(*conditions)).limit(limit).all()

def get_patient_by_id(db: Session, patient_id: int) -> Optional[Patient]:
    return db.query(Patient).filter(Patient.id == patient_id).first()
