from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text
from datetime import datetime
from app.core.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False) # e.g. "INV-2026-0001"
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=True, index=True)
    inpatient_record_id = Column(Integer, ForeignKey("inpatient_records.id"), nullable=True, index=True)
    
    total_amount = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, default=0.0)
    net_payable = Column(Float, nullable=False, default=0.0)
    paid_amount = Column(Float, default=0.0)
    payment_status = Column(String(20), default="UNPAID", index=True)            # UNPAID, PARTIAL, PAID
    payment_method = Column(String(30), nullable=True)                           # CASH, UPI, CARD, CHEQUE, INSURANCE, SPLIT
    transaction_ref = Column(String(100), nullable=True)
    cashier_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    attending_doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Direct doctor link on invoice
    split_payments_json = Column(Text, nullable=True)                           # JSON array of split payment modes
    cash_denominations_json = Column(Text, nullable=True)                       # JSON cash count tally (500,200,100,50,20,10,5,2,1)
    bank_name = Column(String(100), nullable=True)                              # For Cheque
    cheque_number = Column(String(50), nullable=True)                           # For Cheque
    upi_id = Column(String(100), nullable=True)                                 # For UPI 16-digit txn ID
    billing_type = Column(String(30), default="WALK_IN", index=True)            # WALK_IN or CORPORATE_TIEUP
    corporate_client_id = Column(Integer, ForeignKey("corporate_clients.id"), nullable=True, index=True)
    corporate_policy_id = Column(String(100), nullable=True)                  # Policy # / Employee ID
    corporate_claim_amount = Column(Float, default=0.0)
    corporate_claim_status = Column(String(30), default="NOT_APPLICABLE")      # NOT_APPLICABLE, PENDING_CLAIM, APPROVED, SETTLED
    created_at = Column(DateTime, default=datetime.utcnow)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    item_type = Column(String(50), nullable=False)                               # CONSULTATION, LAB_TEST, BED_CHARGE, PHARMACY, PROCEDURE
    description = Column(String(200), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
