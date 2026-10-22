from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from datetime import datetime
from app.core.database import Base

class CorporateClient(Base):
    __tablename__ = "corporate_clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)       # e.g. "Star Health Insurance TPA"
    code = Column(String(50), unique=True, index=True, nullable=False) # e.g. "STAR-HLTH"
    category = Column(String(50), default="INSURANCE_TPA")      # INSURANCE_TPA, CORPORATE_TIEUP, GOVERNMENT_SCHEME
    monthly_credit_limit = Column(Float, nullable=False, default=500000.0) # Admin & Superadmin adjustable
    current_utilized_credit = Column(Float, nullable=False, default=0.0)
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    contact_email = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomDashboardKpi(Base):
    __tablename__ = "custom_dashboard_kpis"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(120), nullable=False)                 # User-friendly card title
    query_key = Column(String(60), nullable=False)              # Key mapping to pre-built SQL query
    metric_type = Column(String(20), default="CURRENCY")        # CURRENCY, PERCENT, COUNT, TEXT
    accent_color = Column(String(30), default="emerald")        # emerald, blue, amber, violet, rose, cyan
    subtitle = Column(String(150), nullable=True)               # Explanatory subtitle
    display_order = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
