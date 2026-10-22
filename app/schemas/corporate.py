from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CorporateClientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=50)
    category: str = Field(default="INSURANCE_TPA") # INSURANCE_TPA, CORPORATE_TIEUP, GOVERNMENT_SCHEME
    monthly_credit_limit: float = Field(..., gt=0)
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None

class CorporateClientUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    monthly_credit_limit: Optional[float] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class CorporateLimitUpdate(BaseModel):
    monthly_credit_limit: float = Field(..., gt=0)
    notes: Optional[str] = None

class CorporateClientOut(BaseModel):
    id: int
    name: str
    code: str
    category: str
    monthly_credit_limit: float
    current_utilized_credit: float
    available_credit: float
    utilization_percentage: float
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CustomKpiCreate(BaseModel):
    query_key: str = Field(..., min_length=2, max_length=60)
    title: Optional[str] = None
    accent_color: Optional[str] = "emerald"

class CustomKpiOut(BaseModel):
    id: int
    title: str
    query_key: str
    metric_type: str
    accent_color: str
    subtitle: Optional[str] = None
    current_value: str
    numeric_value: float
    display_order: int
    is_active: bool

    class Config:
        from_attributes = True
