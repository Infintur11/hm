from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class VitalsCreate(BaseModel):
    patient_id: int
    encounter_id: Optional[int] = None
    temperature_f: Optional[float] = Field(None, ge=90.0, le=110.0)
    blood_pressure_systolic: Optional[int] = Field(None, ge=50, le=260)
    blood_pressure_diastolic: Optional[int] = Field(None, ge=30, le=160)
    heart_rate_bpm: Optional[int] = Field(None, ge=30, le=220)
    respiratory_rate: Optional[int] = Field(None, ge=6, le=60)
    spo2_percent: Optional[int] = Field(None, ge=50, le=100)
    weight_kg: Optional[float] = Field(None, ge=1.0, le=300.0)
    height_cm: Optional[float] = Field(None, ge=30.0, le=250.0)
    triage_notes: Optional[str] = None

class VitalsOut(BaseModel):
    id: int
    patient_id: int
    recorded_at: datetime
    temperature_f: Optional[float]
    blood_pressure_systolic: Optional[int]
    blood_pressure_diastolic: Optional[int]
    heart_rate_bpm: Optional[int]
    respiratory_rate: Optional[int]
    spo2_percent: Optional[int]
    weight_kg: Optional[float]
    height_cm: Optional[float]
    bmi: Optional[float]
    is_abnormal: bool
    clinical_flags: Optional[str]
    triage_notes: Optional[str]

    class Config:
        from_attributes = True

class PrescriptionItemInput(BaseModel):
    medicine_id: Optional[int] = None
    medicine_name: str
    dosage: str = "650 mg"
    frequency: str = "1-0-1"
    duration_days: int = 3
    instructions: str = "After Food"
    quantity: int = 6

class EncounterCreate(BaseModel):
    patient_id: int
    doctor_id: Optional[int] = None
    appointment_id: Optional[int] = None
    chief_complaint: str
    clinical_notes: Optional[str] = None
    diagnosis: str
    icd10_code: Optional[str] = None
    prescriptions: List[PrescriptionItemInput] = []
    lab_test_template_ids: List[int] = []
    admission_recommended: bool = False
    admission_ward_preference: Optional[str] = None
    admission_instructions: Optional[str] = None
