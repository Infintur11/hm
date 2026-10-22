from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False, index=True)  # SUPER_ADMIN, ADMIN, DOCTOR, NURSE, RECEPTIONIST, PHARMACIST, LAB_TECH, CASHIER
    department = Column(String(100), nullable=True)        # Cardiology, General Medicine, Pediatrics, etc.
    consultation_fee = Column(Integer, default=500)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    """System & Security Audit Log for Super Admin compliance and tracking"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, nullable=True)
    actor_name = Column(String(100), nullable=False)
    actor_role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True) # LOGIN, DATA_PURGE, USER_DELETE, OVERRIDE, DISPENSE
    resource = Column(String(100), nullable=False)
    details = Column(String(255), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
    timestamp = Column(DateTime, default=datetime.utcnow)

