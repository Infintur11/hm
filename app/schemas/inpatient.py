from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BedOut(BaseModel):
    id: int
    bed_number: str
    ward_name: str
    bed_type: str
    daily_rate: int
    status: str
    current_patient_id: Optional[int] = None
    patient_name: Optional[str] = None

    class Config:
        from_attributes = True

class BedStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(VACANT|OCCUPIED|CLEANING)$")

class AdmissionCreate(BaseModel):
    patient_id: int
    bed_id: int
    attending_doctor_id: int
    admission_reason: str
    expected_days: int = 3

class DischargeOrder(BaseModel):
    inpatient_record_id: int
    discharge_condition: str = "RECOVERED"
    discharge_summary: str
    allow_override: bool = False
    override_reason: Optional[str] = None

class IPMOAdminister(BaseModel):
    order_id: int
    notes: Optional[str] = None

class IPMOCreate(BaseModel):
    inpatient_record_id: int
    patient_id: int
    medicine_name: str
    dosage: str
    frequency: str
    route: str = "ORAL"
    scheduled_slot: str
    notes: Optional[str] = None

