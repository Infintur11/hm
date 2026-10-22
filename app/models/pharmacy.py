from sqlalchemy import Column, Integer, Float, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String(100), nullable=False, index=True)   # e.g., "Dolo 650", "Augmentin 625"
    generic_name = Column(String(100), nullable=False, index=True) # e.g., "Paracetamol", "Amoxicillin + Clavulanic Acid"
    category = Column(String(50), nullable=False)                  # Antibiotic, Analgesic, Antipyretic, Cardiovascular
    dosage_form = Column(String(30), nullable=False)               # Tablet, Capsule, Syrup, Injection, Inhaler
    strength = Column(String(30), nullable=False)                  # "650 mg", "500 mg", "10 mg"
    stock_quantity = Column(Integer, default=0, nullable=False)
    reorder_level = Column(Integer, default=20, nullable=False)
    unit_price = Column(Float, nullable=False, default=10.0)
    batch_number = Column(String(50), nullable=True)
    expiry_date = Column(String(20), nullable=True)                # YYYY-MM
    is_active = Column(Boolean, default=True)

class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)
    medicine_name = Column(String(100), nullable=False)
    dosage = Column(String(50), nullable=False)                    # "650 mg", "10 ml"
    frequency = Column(String(30), nullable=False)                 # "1-0-1", "1-0-0", "0-0-1", "SOS"
    duration_days = Column(Integer, default=3, nullable=False)
    instructions = Column(String(100), default="After Food")       # "Before Food", "After Food", "At Bedtime"
    quantity_prescribed = Column(Integer, default=6)
    
    # Closed-Loop Pharmacy Verification
    is_dispensed = Column(Boolean, default=False, index=True)
    dispensed_at = Column(DateTime, nullable=True)
    dispensed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
