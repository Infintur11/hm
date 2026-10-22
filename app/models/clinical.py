from sqlalchemy import Column, Integer, Float, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class VitalSigns(Base):
    __tablename__ = "vital_signs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=True, index=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Core Clinical Vitals
    temperature_f = Column(Float, nullable=True)          # Normal 97.0 - 99.0
    blood_pressure_systolic = Column(Integer, nullable=True) # Normal 90 - 120
    blood_pressure_diastolic = Column(Integer, nullable=True)# Normal 60 - 80
    heart_rate_bpm = Column(Integer, nullable=True)       # Normal 60 - 100
    respiratory_rate = Column(Integer, nullable=True)     # Normal 12 - 20
    spo2_percent = Column(Integer, nullable=True)         # Normal 95 - 100
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)
    
    is_abnormal = Column(Boolean, default=False)
    clinical_flags = Column(String(255), nullable=True)   # e.g., "Hypertensive crisis, Hypoxia"
    triage_notes = Column(Text, nullable=True)

class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True, index=True)
    encounter_date = Column(DateTime, default=datetime.utcnow)
    
    # SOAP Clinical Framework
    chief_complaint = Column(Text, nullable=False)        # Subjective: Patient symptoms
    clinical_notes = Column(Text, nullable=True)          # Objective: Physical examination
    diagnosis = Column(Text, nullable=False)              # Assessment: Clinical conclusion
    icd10_code = Column(String(50), nullable=True)        # Standardized medical code
    
    # Inpatient Recommendation
    admission_recommended = Column(Boolean, default=False)
    admission_ward_preference = Column(String(50), nullable=True)
    admission_instructions = Column(Text, nullable=True)
    
    status = Column(String(20), default="FINALIZED")      # DRAFT, FINALIZED
    created_at = Column(DateTime, default=datetime.utcnow)

class TreatmentTemplate(Base):
    __tablename__ = "treatment_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False) # e.g. "Acute Viral Fever Protocol"
    department = Column(String(100), nullable=False)
    diagnosis = Column(String(200), nullable=False)
    icd10_code = Column(String(50), nullable=True)
    default_complaint = Column(Text, nullable=True)
    default_rx_json = Column(Text, nullable=False)          # JSON string of medicines & doses
    default_labs_json = Column(Text, nullable=True)         # JSON string of lab test codes
