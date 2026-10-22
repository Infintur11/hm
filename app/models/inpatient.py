from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class Bed(Base):
    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True)
    bed_number = Column(String(20), unique=True, nullable=False, index=True) # e.g. "BED-101", "ICU-01"
    ward_name = Column(String(50), nullable=False, index=True)                # "General Ward", "Cardiology ICU", "Pediatric Ward", "Deluxe Suite"
    bed_type = Column(String(30), nullable=False)                             # GENERAL, SEMI_PRIVATE, PRIVATE, ICU, EMERGENCY
    daily_rate = Column(Integer, nullable=False, default=1500)
    status = Column(String(20), default="VACANT", index=True)                 # VACANT, OCCUPIED, CLEANING
    current_patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)

class InpatientRecord(Base):
    __tablename__ = "inpatient_records"

    id = Column(Integer, primary_key=True, index=True)
    ip_number = Column(String(50), unique=True, index=True, nullable=False)   # e.g., "IPD-2026-0001"
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    bed_id = Column(Integer, ForeignKey("beds.id"), nullable=False, index=True)
    attending_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admission_date = Column(DateTime, default=datetime.utcnow)
    expected_discharge_date = Column(DateTime, nullable=True)
    discharge_date = Column(DateTime, nullable=True)
    admission_reason = Column(Text, nullable=False)
    discharge_summary = Column(Text, nullable=True)
    discharge_condition = Column(String(50), nullable=True)                   # STABLE, RECOVERED, REFERRED, AMA
    status = Column(String(20), default="ADMITTED", index=True)               # ADMITTED, DISCHARGED, TRANSFERRED
    created_at = Column(DateTime, default=datetime.utcnow)

class InpatientMedicationOrder(Base):
    """Inpatient Medication Order (IPMO) - Scheduled nurse administration chart"""
    __tablename__ = "inpatient_medication_orders"

    id = Column(Integer, primary_key=True, index=True)
    inpatient_record_id = Column(Integer, ForeignKey("inpatient_records.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    medicine_name = Column(String(100), nullable=False)
    dosage = Column(String(50), nullable=False)                               # e.g. "500 mg", "1 Ampoule"
    frequency = Column(String(50), nullable=False)                            # "TDS - Morning/Noon/Night", "BD", "OD"
    route = Column(String(30), default="ORAL")                                # ORAL, IV_INFUSION, IM_INJECTION, SUBLINGUAL
    scheduled_slot = Column(String(50), nullable=False)                       # "08:00 AM", "02:00 PM", "08:00 PM"
    status = Column(String(20), default="PENDING", index=True)                 # PENDING, ADMINISTERED, OMITTED
    administered_at = Column(DateTime, nullable=True)
    administered_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
