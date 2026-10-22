from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=15)
    aadhar_card_no: Optional[str] = None
    age: int = Field(..., ge=0, le=130)
    gender: str = Field(..., pattern="^(MALE|FEMALE|OTHER)$")
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    address: Optional[str] = None
    referred_by_doctor_id: Optional[int] = None
    billing_category: Optional[str] = "WALK_IN"
    corporate_client_id: Optional[int] = None
    corporate_policy_id: Optional[str] = None

class PatientOut(BaseModel):
    id: int
    mrn: str
    full_name: str
    phone_number: str
    aadhar_card_no: Optional[str] = None
    age: int
    gender: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    address: Optional[str] = None
    referred_by_doctor_id: Optional[int] = None
    billing_category: Optional[str] = "WALK_IN"
    corporate_client_id: Optional[int] = None
    corporate_policy_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
