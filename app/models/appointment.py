from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department = Column(String(100), nullable=False)
    appointment_date = Column(String(20), nullable=False, index=True)  # YYYY-MM-DD
    time_slot = Column(String(20), nullable=False)                     # e.g., "09:00 - 09:15"
    token_number = Column(Integer, nullable=False)                     # e.g., 101, 102
    status = Column(String(30), default="SCHEDULED", index=True)        # SCHEDULED, CHECKED_IN, IN_CONSULTATION, COMPLETED, CANCELLED
    reason_for_visit = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
