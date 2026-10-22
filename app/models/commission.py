from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, ForeignKey, Numeric, Boolean,
    Text, UniqueConstraint, Index, Float,
)
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("payment_method", "transaction_ref", name="uq_payment_method_reference"),)

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_method = Column(String(30), nullable=False)
    transaction_ref = Column(String(120), nullable=True)
    idempotency_key = Column(String(120), nullable=False, unique=True)
    status = Column(String(24), nullable=False, default="RECEIVED", index=True)
    received_period = Column(String(7), nullable=False, index=True)
    received_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    reconciled_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    reconciled_period = Column(String(7), nullable=True, index=True)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (UniqueConstraint("payment_id", "invoice_item_id", name="uq_payment_item_allocation"),)

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    invoice_item_id = Column(Integer, ForeignKey("invoice_items.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)


class PaymentRefund(Base):
    __tablename__ = "payment_refunds"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    reason = Column(String(500), nullable=False)
    reference = Column(String(120), nullable=True)
    idempotency_key = Column(String(120), nullable=False, unique=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    period = Column(String(7), nullable=False, index=True)


class PaymentRefundAllocation(Base):
    __tablename__ = "payment_refund_allocations"

    id = Column(Integer, primary_key=True)
    refund_id = Column(Integer, ForeignKey("payment_refunds.id"), nullable=False, index=True)
    payment_allocation_id = Column(Integer, ForeignKey("payment_allocations.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)


class CommissionRule(Base):
    __tablename__ = "commission_rules"
    __table_args__ = (
        Index("ix_commission_rule_effective", "active", "effective_from", "effective_to"),
    )

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String(120), nullable=True, unique=True)
    name = Column(String(120), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    service_type = Column(String(50), nullable=True, index=True)  # CONSULTATION, LAB_TEST, PHARMACY, INPATIENT_STAY
    calculation_type = Column(String(24), nullable=False)  # PERCENTAGE, FIXED, FIXED_PER_SERVICE
    rate = Column(Float, nullable=True)
    fixed_amount = Column(Numeric(14, 2), nullable=True)
    require_all_patient_bills_paid = Column(Boolean, nullable=False, default=True)
    min_settlement_threshold = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, **kwargs):
        if "is_active" in kwargs and "active" not in kwargs:
            kwargs["active"] = kwargs["is_active"]
        elif "active" in kwargs and "is_active" not in kwargs:
            kwargs["is_active"] = kwargs["active"]
        if "name" not in kwargs or not kwargs["name"]:
            calc = kwargs.get("calculation_type", "PERCENTAGE")
            st = kwargs.get("service_type") or "ALL"
            r = kwargs.get("rate") or kwargs.get("fixed_amount") or 0
            kwargs["name"] = f"Rule-{st}-{calc}-{r}"
        if "idempotency_key" not in kwargs or not kwargs["idempotency_key"]:
            import uuid
            kwargs["idempotency_key"] = f"rule-{uuid.uuid4().hex}"
        super().__init__(**kwargs)


class CommissionLedgerEntry(Base):
    __tablename__ = "commission_ledger"
    __table_args__ = (
        UniqueConstraint("generation_key", name="uq_commission_generation_key"),
        Index("ix_commission_doctor_period", "doctor_id", "period"),
        Index("ix_commission_period_status", "period", "status"),
        Index("ix_commission_patient_id", "patient_id"),
    )

    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    invoice_item_id = Column(Integer, ForeignKey("invoice_items.id"), nullable=True, index=True)
    base_amount = Column(Float, nullable=True)
    calculated_commission = Column(Float, nullable=True)
    status = Column(String(24), nullable=False, default="ACCRUED", index=True)  # ACCRUED, RELEASED, SETTLED
    accrued_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    released_at = Column(DateTime, nullable=True)
    governing_rule_id = Column(Integer, ForeignKey("commission_rules.id"), nullable=True, index=True)
    execution_audit_log = Column(Text, nullable=True)

    # Legacy & operational fields
    department = Column(String(100), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    payment_allocation_id = Column(Integer, ForeignKey("payment_allocations.id"), nullable=True, index=True)
    source_entry_id = Column(Integer, ForeignKey("commission_ledger.id"), nullable=True, index=True)
    rule_id = Column(Integer, ForeignKey("commission_rules.id"), nullable=True, index=True)
    source_item_type = Column(String(50), nullable=True)
    source_description = Column(String(200), nullable=True)
    invoice_number = Column(String(50), nullable=True, index=True)
    period = Column(String(7), nullable=True, index=True)
    entry_type = Column(String(24), nullable=False, default="COMMISSION")
    calculation_base = Column(Numeric(14, 2), nullable=True)
    calculation_type = Column(String(24), nullable=True)
    rate = Column(Numeric(9, 4), nullable=True)
    amount = Column(Numeric(14, 2), nullable=True)
    generation_key = Column(String(160), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __init__(self, **kwargs):
        if "rule_id" in kwargs and "governing_rule_id" not in kwargs:
            kwargs["governing_rule_id"] = kwargs["rule_id"]
        elif "governing_rule_id" in kwargs and "rule_id" not in kwargs:
            kwargs["rule_id"] = kwargs["governing_rule_id"]
        if "calculation_base" in kwargs and "base_amount" not in kwargs:
            kwargs["base_amount"] = float(kwargs["calculation_base"]) if kwargs["calculation_base"] is not None else 0.0
        elif "base_amount" in kwargs and "calculation_base" not in kwargs:
            kwargs["calculation_base"] = kwargs["base_amount"]
        if "amount" in kwargs and "calculated_commission" not in kwargs:
            kwargs["calculated_commission"] = float(kwargs["amount"]) if kwargs["amount"] is not None else 0.0
        elif "calculated_commission" in kwargs and "amount" not in kwargs:
            kwargs["amount"] = kwargs["calculated_commission"]
        if "created_at" in kwargs and "accrued_at" not in kwargs:
            kwargs["accrued_at"] = kwargs["created_at"]
        elif "accrued_at" in kwargs and "created_at" not in kwargs:
            kwargs["created_at"] = kwargs["accrued_at"]
        if "status" not in kwargs:
            kwargs["status"] = "ACCRUED"
        super().__init__(**kwargs)


class SettlementRequest(Base):
    __tablename__ = "settlement_requests"
    __table_args__ = (Index("ix_settlement_doctor_period", "doctor_id", "period"),)

    id = Column(Integer, primary_key=True)
    request_number = Column(String(40), nullable=False, unique=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    idempotency_key = Column(String(120), nullable=False, unique=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    decided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(String(500), nullable=True)


class SettlementAllocation(Base):
    __tablename__ = "settlement_allocations"
    __table_args__ = (UniqueConstraint("request_id", "ledger_entry_id", name="uq_settlement_entry_allocation"),)

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("settlement_requests.id"), nullable=False, index=True)
    ledger_entry_id = Column(Integer, ForeignKey("commission_ledger.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(24), nullable=False, default="RESERVED", index=True)


class SettlementPayout(Base):
    __tablename__ = "settlement_payouts"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("settlement_requests.id"), nullable=False, unique=True, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_method = Column(String(30), nullable=False)
    payment_reference = Column(String(120), nullable=False, unique=True)
    idempotency_key = Column(String(120), nullable=False, unique=True)
    paid_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    paid_period = Column(String(7), nullable=False, index=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    evidence_note = Column(String(500), nullable=False)


class CommissionAuditEvent(Base):
    __tablename__ = "commission_audit_events"
    __table_args__ = (Index("ix_commission_audit_created", "created_at"),)

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
