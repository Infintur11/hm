from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    department: str
    appointment_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$") # YYYY-MM-DD
    time_slot: str                                                      # e.g., "09:00 - 09:15"
    reason_for_visit: Optional[str] = "Routine Consultation"

class AppointmentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(SCHEDULED|CHECKED_IN|IN_CONSULTATION|COMPLETED|CANCELLED)$")

class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: int
    doctor_name: Optional[str] = None
    department: str
    appointment_date: str
    time_slot: str
    token_number: int
    status: str
    reason_for_visit: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
