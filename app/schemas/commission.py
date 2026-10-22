from datetime import date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class CommissionRuleCreate(BaseModel):
    idempotency_key: Optional[str] = Field(None, max_length=120)
    name: Optional[str] = Field(None, max_length=120)
    doctor_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=100)
    service_type: Optional[Literal["CONSULTATION", "LAB_TEST", "BED_CHARGE", "PHARMACY", "PROCEDURE", "INPATIENT_STAY"]] = None
    calculation_type: Literal["PERCENTAGE", "FIXED", "FIXED_PER_SERVICE"]
    rate: Optional[Decimal] = Field(None, ge=0)
    fixed_amount: Optional[Decimal] = Field(None, ge=0)
    require_all_patient_bills_paid: Optional[bool] = True
    min_settlement_threshold: Optional[float] = 0.0
    is_active: Optional[bool] = True
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    @model_validator(mode="after")
    def validate_rule(self):
        import uuid
        from datetime import date as d_date
        if not self.idempotency_key:
            self.idempotency_key = f"rule-{uuid.uuid4().hex}"
        if not self.effective_from:
            self.effective_from = d_date.today()
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        if not self.name:
            st = self.service_type or "ALL"
            r = self.rate or self.fixed_amount or 0
            self.name = f"Rule-{st}-{self.calculation_type}-{r}"
        if self.calculation_type == "PERCENTAGE":
            if self.rate is None and self.fixed_amount is not None:
                self.rate = self.fixed_amount
            if self.rate is None:
                raise ValueError("Percentage rules require a rate")
        elif self.calculation_type in ("FIXED", "FIXED_PER_SERVICE"):
            if self.fixed_amount is None and self.rate is not None:
                self.fixed_amount = self.rate
            elif self.rate is None and self.fixed_amount is not None:
                self.rate = self.fixed_amount
            if self.fixed_amount is None:
                raise ValueError("Fixed rules require fixed_amount or rate")
        if not any((self.doctor_id, self.department, self.service_type)):
            # If none specified, treat as global rule (or require at least one if strict)
            pass
        return self


class SettlementRequestCreate(BaseModel):
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    idempotency_key: str = Field(..., min_length=8, max_length=120)


class SettlementDecision(BaseModel):
    note: Optional[str] = Field(None, max_length=500)


class PayoutCreate(BaseModel):
    payment_method: Literal["BANK_TRANSFER", "CASH", "UPI", "CHEQUE"]
    payment_reference: str = Field(..., min_length=3, max_length=120)
    idempotency_key: str = Field(..., min_length=8, max_length=120)
    evidence_note: str = Field(..., min_length=3, max_length=500)


class PaymentRefundCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(..., min_length=3, max_length=500)
    reference: Optional[str] = Field(None, max_length=120)
    idempotency_key: str = Field(..., min_length=8, max_length=120)


class CommissionAdjustmentCreate(BaseModel):
    doctor_id: int
    period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(..., max_digits=14, decimal_places=2)
    reason: str = Field(..., min_length=5, max_length=500)
    idempotency_key: str = Field(..., min_length=8, max_length=120)

    @model_validator(mode="after")
    def nonzero(self):
        if self.amount == 0:
            raise ValueError("Adjustment amount cannot be zero")
        return self
