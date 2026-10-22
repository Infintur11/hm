from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    mrn = Column(String(50), unique=True, index=True, nullable=False)  # Medical Record Number (e.g. MRN-2026-0001)
    full_name = Column(String(100), nullable=False, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    aadhar_card_no = Column(String(20), nullable=True, index=True)
    date_of_birth = Column(String(20), nullable=True)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)  # MALE, FEMALE, OTHER
    blood_group = Column(String(10), nullable=True)  # A+, B+, O+, AB+, etc.
    allergies = Column(Text, nullable=True)          # e.g., "Penicillin, Sulfa drugs"
    chronic_conditions = Column(Text, nullable=True) # e.g., "Type 2 Diabetes, Hypertension"
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    referred_by_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    billing_category = Column(String(30), default="WALK_IN") # WALK_IN or CORPORATE_TIEUP
    corporate_client_id = Column(Integer, ForeignKey("corporate_clients.id"), nullable=True, index=True)
    corporate_policy_id = Column(String(100), nullable=True) # Policy # / TPA Card / Employee ID
    created_at = Column(DateTime, default=datetime.utcnow)
