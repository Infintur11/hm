from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class MedicineCreate(BaseModel):
    brand_name: str
    generic_name: str
    category: str
    dosage_form: str
    strength: str
    stock_quantity: int = 100
    reorder_level: int = 20
    unit_price: float = 10.0
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None

class DispenseRequest(BaseModel):
    prescription_item_id: int
    override_reason: Optional[str] = None

class RestockRequest(BaseModel):
    medicine_id: int
    quantity_to_add: int
    batch_number: Optional[str] = None

class PrescriptionItemOut(BaseModel):
    id: int
    encounter_id: int
    patient_id: int
    patient_name: Optional[str] = None
    medicine_name: str
    dosage: str
    frequency: str
    duration_days: int
    instructions: str
    quantity_prescribed: int
    is_dispensed: bool
    is_paid: bool = False
    invoice_number: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
