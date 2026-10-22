from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class InvoiceItemInput(BaseModel):
    item_type: str = Field(..., pattern="^(CONSULTATION|LAB_TEST|BED_CHARGE|PHARMACY|PROCEDURE)$")
    description: str
    quantity: int = 1
    unit_price: float

class InvoiceCreate(BaseModel):
    patient_id: int
    encounter_id: Optional[int] = None
    inpatient_record_id: Optional[int] = None
    items: List[InvoiceItemInput]
    discount_amount: float = 0.0

class PaymentCollectRequest(BaseModel):
    invoice_id: int
    amount_paid: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    payment_method: str = Field(..., pattern="^(CASH|UPI|CARD|CHEQUE|INSURANCE|SPLIT)$")
    transaction_ref: Optional[str] = Field(None, max_length=120)
    idempotency_key: str = Field(..., min_length=8, max_length=120)
    bank_name: Optional[str] = Field(None, max_length=120)
    cheque_number: Optional[str] = Field(None, max_length=60)
    upi_id: Optional[str] = Field(None, max_length=60)
    insurance_provider: Optional[str] = Field(None, max_length=120)
    insurance_policy_number: Optional[str] = Field(None, max_length=120)
    cash_denominations: Optional[dict] = None
    split_payments: Optional[List[dict]] = None
    attending_doctor_id: Optional[int] = None
    billing_type: Optional[str] = "WALK_IN"
    corporate_client_id: Optional[int] = None
    corporate_policy_id: Optional[str] = None
    corporate_claim_amount: Optional[Decimal] = None

class InvoiceItemOut(BaseModel):
    id: int
    item_type: str
    description: str
    quantity: int
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True

class InvoiceOut(BaseModel):
    id: int
    invoice_number: str
    patient_id: int
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_mrn: Optional[str] = None
    attending_doctor_id: Optional[int] = None
    attending_doctor_name: Optional[str] = None
    encounter_id: Optional[int] = None
    inpatient_record_id: Optional[int] = None
    total_amount: float
    discount_amount: float
    net_payable: float
    paid_amount: float
    payment_status: str
    payment_method: Optional[str] = None
    transaction_ref: Optional[str] = None
    bank_name: Optional[str] = None
    cheque_number: Optional[str] = None
    upi_id: Optional[str] = None
    cash_denominations_json: Optional[str] = None
    split_payments_json: Optional[str] = None
    billing_type: Optional[str] = "WALK_IN"
    corporate_client_id: Optional[int] = None
    corporate_client_name: Optional[str] = None
    corporate_policy_id: Optional[str] = None
    corporate_claim_amount: Optional[float] = 0.0
    corporate_claim_status: Optional[str] = "NOT_APPLICABLE"
    created_at: datetime
    items: List[InvoiceItemOut] = []

    class Config:
        from_attributes = True

