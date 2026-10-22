from sqlalchemy import Column, Integer, Float, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from app.core.database import Base

class LabTestTemplate(Base):
    __tablename__ = "lab_test_templates"

    id = Column(Integer, primary_key=True, index=True)
    test_code = Column(String(50), unique=True, nullable=False, index=True) # e.g. "CBC", "LIPID", "KFT", "XRAY_CHEST"
    test_name = Column(String(100), nullable=False)                         # e.g. "Complete Blood Count (CBC)"
    department = Column(String(50), nullable=False)                         # Hematology, Biochemistry, Radiology, Microbiology, Pathology
    modality = Column(String(50), nullable=True)                            # XRAY, CT, MRI, USG, MAMMO, or None
    sample_type = Column(String(50), nullable=False)                        # Whole Blood (EDTA), Serum, Urine, None (Radiology)
    standard_rate = Column(Integer, nullable=False, default=350)
    normal_range = Column(String(100), nullable=True)                       # e.g., "13.5 - 17.5"
    unit_of_measurement = Column(String(30), nullable=True)                 # e.g., "g/dL", "mg/dL", "cells/mcL"
    parameters_json = Column(Text, nullable=True)                           # JSON array: [{"name": "Hemoglobin", "unit": "g/dL", "range": "13.5-17.5"}]
    template_text = Column(Text, nullable=True)                             # Default boilerplate findings/impression for radiology
    is_active = Column(Boolean, default=True)

class LabOrder(Base):
    __tablename__ = "lab_orders"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    ordered_by_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("lab_test_templates.id"), nullable=False)
    test_name = Column(String(100), nullable=False)
    modality = Column(String(50), nullable=True)
    sample_status = Column(String(30), default="ORDERED", index=True)       # ORDERED, SAMPLE_COLLECTED, ANALYZING, COMPLETED
    sample_barcode = Column(String(50), nullable=True, index=True)          # e.g., "BAR-89211"
    clinical_notes = Column(Text, nullable=True)
    collected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("lab_orders.id"), unique=True, nullable=False)
    result_value = Column(String(100), nullable=False)                      # e.g. "Completed", "Opacities observed", "14.2"
    reference_range = Column(String(100), nullable=True)
    unit = Column(String(30), nullable=True)
    is_abnormal = Column(Boolean, default=False)
    panic_flag = Column(String(50), nullable=True)                          # "CRITICAL HIGH", "CRITICAL LOW", "ABNORMAL", "NORMAL"
    technician_notes = Column(Text, nullable=True)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    verified_at = Column(DateTime, default=datetime.utcnow)

    # Multi-parameter Lab Results (JSON array of {name, value, unit, range, flag})
    parameter_results = Column(Text, nullable=True)

    # Radiology Specific Diagnostics & PACS imaging
    modality = Column(String(50), nullable=True)                            # XRAY, CT, MRI, USG
    image_url = Column(String(255), nullable=True)                           # Raw DICOM/Scan upload URL
    annotated_image_url = Column(String(255), nullable=True)                 # Radiologist annotated scan URL
    clinical_history = Column(Text, nullable=True)                          # Indication / Chief complaint
    technique = Column(Text, nullable=True)                                 # Projections / Views / Contrast protocol
    findings = Column(Text, nullable=True)                                  # Detailed anatomical observation
    impression = Column(Text, nullable=True)                                # Concluding radiologic diagnosis

    # Doctor Clinical Review & Authentication Loop
    doctor_approval_status = Column(String(50), default="PENDING_REVIEW")   # PENDING_REVIEW, APPROVED, REVISION_REQUESTED
    doctor_notes = Column(Text, nullable=True)                              # Specific clinical changes requested by doctor
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)     # Authenticating doctor
    doctor_approved_at = Column(DateTime, nullable=True)

    # Receptionist Dispatch Track
    dispatch_status = Column(String(50), default="NOT_DISPATCHED")          # NOT_DISPATCHED, DISPATCHED
    dispatched_at = Column(DateTime, nullable=True)
    dispatch_channels = Column(String(100), nullable=True)                  # e.g. "EMAIL,WHATSAPP,SMS"

