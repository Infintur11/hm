from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class LabTemplateCreate(BaseModel):
    test_code: str
    test_name: str
    department: str
    modality: Optional[str] = None
    sample_type: str = "Specimen"
    standard_rate: int = 350
    normal_range: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    parameters_json: Optional[str] = None
    template_text: Optional[str] = None
    is_active: bool = True

class LabTemplateUpdate(BaseModel):
    test_code: Optional[str] = None
    test_name: Optional[str] = None
    department: Optional[str] = None
    modality: Optional[str] = None
    sample_type: Optional[str] = None
    standard_rate: Optional[int] = None
    normal_range: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    parameters_json: Optional[str] = None
    template_text: Optional[str] = None
    is_active: Optional[bool] = None

class LabOrderCreate(BaseModel):
    patient_id: int
    template_id: int
    ordered_by_doctor_id: Optional[int] = None
    encounter_id: Optional[int] = None
    clinical_notes: Optional[str] = None

class LabResultEntry(BaseModel):
    order_id: int
    result_value: str
    is_abnormal: bool = False
    panic_flag: Optional[str] = "NORMAL"
    technician_notes: Optional[str] = None
    parameter_results: Optional[str] = None
    # Radiology specific fields
    modality: Optional[str] = None
    image_url: Optional[str] = None
    annotated_image_url: Optional[str] = None
    clinical_history: Optional[str] = None
    technique: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None

class RadiologyAnnotationSave(BaseModel):
    order_id: int
    image_data: str # base64 data url

class LabOrderOut(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    ordered_by_doctor_id: int
    doctor_name: Optional[str] = None
    template_id: int
    test_name: str
    department: Optional[str] = None
    modality: Optional[str] = None
    sample_status: str
    sample_barcode: Optional[str] = None
    clinical_notes: Optional[str] = None
    collected_at: Optional[datetime] = None
    created_at: datetime
    result_value: Optional[str] = None
    reference_range: Optional[str] = None
    unit: Optional[str] = None
    is_abnormal: Optional[bool] = None
    panic_flag: Optional[str] = None
    technician_notes: Optional[str] = None
    parameter_results: Optional[str] = None
    image_url: Optional[str] = None
    annotated_image_url: Optional[str] = None
    clinical_history: Optional[str] = None
    technique: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True

