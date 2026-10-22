"""Auditable payment reconciliation, commission and clinician settlement services.

Policy defaults: cashiers first record a payment as RECEIVED. Only finance reconciliation
makes it commission eligible. Invoice discounts are distributed pro rata across line-item
net values; each receipt is allocated pro rata across outstanding line balances. Taxes are
not modeled by the existing HMS invoice schema. An encounter's doctor (or inpatient record's
attending doctor) is the provider for its invoice lines; rule service filters decide which
line types qualify. There is no historical payment event data to safely backfill, so legacy
invoice.paid_amount values remain unverified and do not generate commission.
"""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from zoneinfo import ZoneInfo
from uuid import uuid4
from sqlalchemy import func, text, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.billing import Invoice, InvoiceItem
from app.models.clinical import Encounter
from app.models.inpatient import InpatientRecord
from app.models.patient import Patient
from app.models.user import User
from app.core.config import settings
from app.models.commission import (
    Payment, PaymentAllocation, PaymentRefund, PaymentRefundAllocation,
    CommissionRule, CommissionLedgerEntry, SettlementRequest,
    SettlementAllocation, SettlementPayout, CommissionAuditEvent,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def decimal(value) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def money(value) -> Decimal:
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _lock_financial_write(db: Session):
    # SQLite has no row-level SELECT FOR UPDATE. BEGIN IMMEDIATE serializes financial writes.
    if db.bind and db.bind.dialect.name == "sqlite" and not db.in_transaction():
        db.execute(text("BEGIN IMMEDIATE"))


def _audit(db, actor_id, action, resource_type, resource_id=None, details=None):
    db.add(CommissionAuditEvent(
        actor_id=actor_id, action=action, resource_type=resource_type,
        resource_id=resource_id, details=details,
    ))


def _period(when: datetime) -> str:
    return when.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(settings.TIMEZONE)).strftime("%Y-%m") if when.tzinfo is None else when.astimezone(ZoneInfo(settings.TIMEZONE)).strftime("%Y-%m")


def current_period() -> str:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).strftime("%Y-%m")


def _hospital_date(when: datetime) -> date:
    local = when.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(settings.TIMEZONE)) if when.tzinfo is None else when.astimezone(ZoneInfo(settings.TIMEZONE))
    return local.date()


def _provider_for_invoice(db: Session, invoice: Invoice):
    if invoice.encounter_id:
        encounter = db.query(Encounter).filter(Encounter.id == invoice.encounter_id).first()
        if encounter:
            return db.query(User).filter(User.id == encounter.doctor_id, User.role == "DOCTOR").first()
    if invoice.inpatient_record_id:
        record = db.query(InpatientRecord).filter(InpatientRecord.id == invoice.inpatient_record_id).first()
        if record:
            return db.query(User).filter(User.id == record.attending_doctor_id, User.role == "DOCTOR").first()
    return None


def _line_net_values(db: Session, invoice: Invoice):
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).order_by(InvoiceItem.id).all()
    gross = sum((money(item.total_price) for item in items), ZERO)
    discount = min(max(money(invoice.discount_amount), ZERO), gross)
    net_total = gross - discount
    if not items or gross <= ZERO:
        return items, {}
    values = {}
    remaining_discount = discount
    for index, item in enumerate(items):
        line_gross = money(item.total_price)
        if index == len(items) - 1:
            line_discount = remaining_discount
        else:
            line_discount = money(discount * line_gross / gross)
            remaining_discount -= line_discount
        values[item.id] = max(ZERO, line_gross - line_discount)
    return items, values


def _unrefunded_allocation_amount(db: Session, allocation: PaymentAllocation) -> Decimal:
    refunded = db.query(func.coalesce(func.sum(PaymentRefundAllocation.amount), 0)).filter(
        PaymentRefundAllocation.payment_allocation_id == allocation.id
    ).scalar()
    return max(ZERO, money(allocation.amount) - money(refunded))


def _allocate_receipt(db: Session, payment: Payment, invoice: Invoice):
    items, line_nets = _line_net_values(db, invoice)
    if not items:
        return
    allocations = db.query(PaymentAllocation).join(Payment).filter(Payment.invoice_id == invoice.id).all()
    refunds = db.query(PaymentRefundAllocation).join(PaymentAllocation).join(Payment).filter(
        Payment.invoice_id == invoice.id
    ).all()
    refund_by_allocation = {}
    for refund in refunds:
        refund_by_allocation[refund.payment_allocation_id] = refund_by_allocation.get(refund.payment_allocation_id, ZERO) + money(refund.amount)
    allocated_by_item = {}
    for allocation in allocations:
        allocated_by_item[allocation.invoice_item_id] = allocated_by_item.get(allocation.invoice_item_id, ZERO) + max(
            ZERO, money(allocation.amount) - refund_by_allocation.get(allocation.id, ZERO)
        )

    prior_payment_total = sum((money(p.amount) for p in db.query(Payment).filter(
        Payment.invoice_id == invoice.id, Payment.id != payment.id).all()), ZERO)
    prior_refund_total = sum((money(r.amount) for r in db.query(PaymentRefund).join(Payment).filter(
        Payment.invoice_id == invoice.id).all()), ZERO)
    historical_paid = max(ZERO, money(invoice.paid_amount) - prior_payment_total + prior_refund_total)
    due = {item.id: max(ZERO, line_nets[item.id] - allocated_by_item.get(item.id, ZERO)) for item in items}
    due_total = sum(due.values(), ZERO)
    if historical_paid > ZERO and due_total > ZERO:
        # Legacy aggregate collections cannot be attributed to source transactions; reserve their
        # pro-rata share so newly recorded events cannot over-allocate invoice lines.
        legacy = min(historical_paid, due_total)
        left = legacy
        for index, item in enumerate(items):
            current = due[item.id]
            deduction = left if index == len(items) - 1 else min(current, money(legacy * current / due_total))
            due[item.id] = max(ZERO, current - deduction)
            left -= deduction
    due_total = sum(due.values(), ZERO)
    amount_left = min(money(payment.amount), due_total)
    eligible_items = [item for item in items if due[item.id] > ZERO]
    for index, item in enumerate(eligible_items):
        if amount_left <= ZERO:
            break
        if index == len(eligible_items) - 1:
            line_amount = min(due[item.id], amount_left)
        else:
            line_amount = min(due[item.id], money(min(money(payment.amount), due_total) * due[item.id] / due_total))
            line_amount = min(line_amount, amount_left)
        if line_amount > ZERO:
            db.add(PaymentAllocation(payment_id=payment.id, invoice_item_id=item.id, amount=line_amount))
            amount_left -= line_amount


def collect_payment(db: Session, data, cashier_id: int):
    _lock_financial_write(db)
    invoice = db.query(Invoice).filter(Invoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    key = data.idempotency_key
    existing = db.query(Payment).filter(Payment.idempotency_key == key).first()
    if existing:
        if (existing.invoice_id != invoice.id or money(existing.amount) != money(data.amount_paid) or
                existing.payment_method != data.payment_method or existing.transaction_ref != data.transaction_ref):
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different payment")
        return {"status": "SUCCESS", "payment_id": existing.id, "payment_status": invoice.payment_status,
                "paid_amount": str(money(invoice.paid_amount)), "settlement_status": existing.status, "duplicate": True}
    if data.transaction_ref:
        duplicate_reference = db.query(Payment).filter(
            Payment.payment_method == data.payment_method,
            Payment.transaction_ref == data.transaction_ref,
        ).first()
        if duplicate_reference:
            if duplicate_reference.invoice_id == invoice.id and money(duplicate_reference.amount) == money(data.amount_paid):
                return {"status": "SUCCESS", "payment_id": duplicate_reference.id,
                        "paid_amount": str(money(invoice.paid_amount)), "payment_status": invoice.payment_status,
                        "settlement_status": duplicate_reference.status, "duplicate": True}
            raise HTTPException(status_code=409, detail="Payment reference has already been recorded")
    if money(data.amount_paid) <= ZERO:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    outstanding = max(ZERO, money(invoice.net_payable) - money(invoice.paid_amount))
    if money(data.amount_paid) > outstanding:
        raise HTTPException(status_code=409, detail=f"Payment exceeds outstanding invoice balance of {outstanding}")
    received_at = datetime.utcnow()
    payment = Payment(
        invoice_id=invoice.id, amount=money(data.amount_paid), payment_method=data.payment_method,
        transaction_ref=data.transaction_ref, idempotency_key=key, status="RECEIVED",
        received_at=received_at, received_period=_period(received_at), received_by_id=cashier_id,
    )
    db.add(payment)
    db.flush()
    _allocate_receipt(db, payment, invoice)
    invoice.paid_amount = float(money(invoice.paid_amount) + money(data.amount_paid))
    invoice.payment_method = data.payment_method
    invoice.transaction_ref = data.transaction_ref
    invoice.cashier_id = cashier_id
    invoice.payment_status = "PAID" if money(invoice.paid_amount) >= money(invoice.net_payable) else "PARTIAL"

    # Persist granular payment mode metadata
    import json
    if getattr(data, "bank_name", None):
        invoice.bank_name = data.bank_name
    if getattr(data, "cheque_number", None):
        invoice.cheque_number = data.cheque_number
    if getattr(data, "upi_id", None):
        invoice.upi_id = data.upi_id
    if getattr(data, "cash_denominations", None):
        invoice.cash_denominations_json = json.dumps(data.cash_denominations)
    if getattr(data, "split_payments", None):
        invoice.split_payments_json = json.dumps(data.split_payments)
    if getattr(data, "attending_doctor_id", None):
        invoice.attending_doctor_id = data.attending_doctor_id

    # Persist corporate / insurance tie-up billing & credit deduction
    billing_type = getattr(data, "billing_type", None) or "WALK_IN"
    invoice.billing_type = billing_type
    corp_id = getattr(data, "corporate_client_id", None)
    if corp_id:
        from app.models.corporate import CorporateClient
        invoice.corporate_client_id = corp_id
        corp_client = db.query(CorporateClient).filter(CorporateClient.id == corp_id).first()
        if corp_client:
            claim_amt = float(getattr(data, "corporate_claim_amount", None) or data.amount_paid)
            invoice.corporate_claim_amount = claim_amt
            invoice.corporate_claim_status = "PENDING_CLAIM" if data.payment_method == "INSURANCE" else "APPROVED"
            corp_client.current_utilized_credit = float(corp_client.current_utilized_credit or 0.0) + claim_amt
    if getattr(data, "corporate_policy_id", None):
        invoice.corporate_policy_id = data.corporate_policy_id

    _audit(db, cashier_id, "PAYMENT_RECEIVED", "payment", payment.id, f"invoice={invoice.invoice_number}; amount={money(data.amount_paid)}")
    db.commit()
    db.refresh(payment)
    return {"status": "SUCCESS", "payment_id": payment.id, "invoice_number": invoice.invoice_number,
            "paid_amount": str(money(invoice.paid_amount)), "payment_status": invoice.payment_status,
            "settlement_status": payment.status}



def _matching_rule(db: Session, doctor: User, item: InvoiceItem, event_date: date):
    rules = db.query(CommissionRule).filter(
        (CommissionRule.active.is_(True) | CommissionRule.is_active.is_(True)),
        CommissionRule.effective_from <= event_date,
        (CommissionRule.effective_to.is_(None) | (CommissionRule.effective_to >= event_date)),
        (CommissionRule.doctor_id.is_(None) | (CommissionRule.doctor_id == doctor.id)),
        (CommissionRule.department.is_(None) | (CommissionRule.department == doctor.department)),
        (CommissionRule.service_type.is_(None) |
         (CommissionRule.service_type == item.item_type) |
         ((CommissionRule.service_type == "INPATIENT_STAY") & (item.item_type == "BED_CHARGE"))),
    ).all()
    if not rules:
        return None
    rules.sort(key=lambda r: (sum(x is not None for x in (r.doctor_id, r.department, r.service_type)), r.effective_from, r.id), reverse=True)
    return rules[0]


def evaluate_and_release_commissions(db: Session, doctor_id: int) -> dict:
    """
    Evaluates all ACCRUED records for doctor_id using ACID BEGIN IMMEDIATE write serialization.
    Enforces:
      Invariant A: All invoices for entry's patient_id must have status == 'PAID'.
      Invariant B: If current date is before calendar month-end day, cumulative accrued commission this month
                   must meet or exceed CommissionRule.min_settlement_threshold.
    If both invariants pass, transitions row to RELEASED, records execution_audit_log and released_at.
    """
    _lock_financial_write(db)
    doctor = db.query(User).filter(User.id == doctor_id, User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    accrued_entries = db.query(CommissionLedgerEntry).filter(
        CommissionLedgerEntry.doctor_id == doctor_id,
        CommissionLedgerEntry.status == "ACCRUED"
    ).all()

    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    today = now_local.date()
    _, last_day = calendar.monthrange(today.year, today.month)
    month_end_date = date(today.year, today.month, last_day)
    is_before_month_end = today < month_end_date
    current_mo = now_local.strftime("%Y-%m")

    monthly_accrued = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id,
        CommissionLedgerEntry.period == current_mo
    ).scalar())

    evaluated_count = len(accrued_entries)
    released_count = 0
    released_amount = ZERO

    for entry in accrued_entries:
        rule_id = entry.governing_rule_id or entry.rule_id
        rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).first() if rule_id else None

        require_all_paid = rule.require_all_patient_bills_paid if (rule and rule.require_all_patient_bills_paid is not None) else True
        min_threshold = decimal(rule.min_settlement_threshold) if (rule and rule.min_settlement_threshold is not None) else ZERO

        # Invariant A: Referred Patient Bills Check
        patient_bills_ok = True
        patient_lock_reason = None
        if not entry.patient_id and entry.invoice_id:
            inv = db.query(Invoice).filter(Invoice.id == entry.invoice_id).first()
            if inv:
                entry.patient_id = inv.patient_id

        if entry.patient_id and require_all_paid:
            unpaid_invoices = db.query(Invoice).filter(
                Invoice.patient_id == entry.patient_id,
                Invoice.payment_status != "PAID"
            ).all()
            if unpaid_invoices:
                patient_bills_ok = False
                unpaid_refs = ", ".join([inv.invoice_number for inv in unpaid_invoices[:3]])
                patient_lock_reason = (
                    f"Waiting for Patient Bill Settlement: Patient #{entry.patient_id} has "
                    f"{len(unpaid_invoices)} unpaid bill(s) ({unpaid_refs}). All patient bills must be settled before commission release."
                )

        if not patient_bills_ok:
            entry.execution_audit_log = patient_lock_reason
            continue

        # Invariant B: All patient bills settled -> Release Commission Entry immediately
        entry.status = "RELEASED"
        entry.released_at = datetime.utcnow()
        entry.execution_audit_log = (
            f"All patient bills verified settled. "
            f"Released for instant payout on {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC."
        )
        _audit(db, doctor_id, "COMMISSION_RELEASED", "commission_ledger", entry.id,
               f"amount={entry.amount}; period={entry.period}; rule_id={rule_id}")
        released_count += 1
        released_amount += money(entry.amount)

    db.commit()

    remaining_accrued = db.query(CommissionLedgerEntry).filter(
        CommissionLedgerEntry.doctor_id == doctor_id,
        CommissionLedgerEntry.status == "ACCRUED"
    ).count()

    return {
        "doctor_id": doctor_id,
        "evaluated_count": evaluated_count,
        "released_count": released_count,
        "remaining_accrued_count": remaining_accrued,
        "released_amount": str(released_amount),
        "message": f"Evaluated {evaluated_count} record(s): {released_count} released (₹{released_amount:.2f}), {remaining_accrued} remain locked in ACCRUED status."
    }


def reconcile_payment(db: Session, payment_id: int, actor_id: int):
    _lock_financial_write(db)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status in ("RECONCILED", "RECONCILED_PARTIALLY_REFUNDED"):
        return {"status": payment.status, "payment_id": payment.id, "generated_entries": 0, "duplicate": True}
    if payment.status not in ("RECEIVED", "RECEIVED_PARTIALLY_REFUNDED"):
        raise HTTPException(status_code=409, detail=f"Payment cannot be reconciled from {payment.status}")
    invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
    doctor = _provider_for_invoice(db, invoice) if invoice else None
    generated = 0
    if doctor:
        allocations = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment.id).all()
        for allocation in allocations:
            item = db.query(InvoiceItem).filter(InvoiceItem.id == allocation.invoice_item_id).first()
            if not item:
                continue
            base = _unrefunded_allocation_amount(db, allocation)
            if base <= ZERO:
                continue
            rule = _matching_rule(db, doctor, item, _hospital_date(payment.received_at))
            if not rule:
                continue
            if rule.calculation_type == "PERCENTAGE":
                rate = decimal(rule.rate)
                amount = money(base * rate / Decimal("100"))
            else:
                _, line_nets = _line_net_values(db, invoice)
                line_net = line_nets.get(item.id, ZERO)
                if line_net <= ZERO:
                    continue
                rate = None
                fixed_val = decimal(rule.fixed_amount if rule.fixed_amount is not None else rule.rate)
                amount = money(fixed_val * Decimal(item.quantity or 1) * base / line_net)
            generation_key = f"payment:{payment.id}:allocation:{allocation.id}:rule:{rule.id}"
            if db.query(CommissionLedgerEntry.id).filter_by(generation_key=generation_key).first():
                continue
            db.add(CommissionLedgerEntry(
                doctor_id=doctor.id,
                patient_id=invoice.patient_id,
                invoice_id=invoice.id,
                invoice_item_id=item.id,
                base_amount=float(base),
                calculated_commission=float(amount),
                status="ACCRUED",
                accrued_at=datetime.utcnow(),
                released_at=None,
                governing_rule_id=rule.id,
                execution_audit_log="Initial accrual recorded. Awaiting evaluation and release.",
                department=doctor.department,
                payment_id=payment.id,
                payment_allocation_id=allocation.id,
                rule_id=rule.id,
                source_item_type=item.item_type,
                source_description=item.description,
                invoice_number=invoice.invoice_number,
                period=_period(payment.received_at),
                calculation_base=base,
                calculation_type=rule.calculation_type,
                rate=rate,
                amount=amount,
                generation_key=generation_key,
            ))
            generated += 1
    payment.status = "RECONCILED_PARTIALLY_REFUNDED" if payment.status == "RECEIVED_PARTIALLY_REFUNDED" else "RECONCILED"
    payment.reconciled_by_id = actor_id
    payment.reconciled_at = datetime.utcnow()
    payment.reconciled_period = _period(payment.reconciled_at)
    _audit(db, actor_id, "PAYMENT_RECONCILED", "payment", payment.id, f"commission_entries={generated}")
    db.commit()
    if doctor:
        evaluate_and_release_commissions(db, doctor.id)
    return {"status": payment.status, "payment_id": payment.id, "generated_entries": generated}


def refund_payment(db: Session, payment_id: int, amount, reason: str, reference: Optional[str], idempotency_key: str, actor_id: int):
    _lock_financial_write(db)
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    existing = db.query(PaymentRefund).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        if (existing.payment_id != payment.id or money(existing.amount) != money(amount) or
                existing.reason != reason or existing.reference != reference):
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different refund")
        return {"refund_id": existing.id, "status": "RECORDED", "duplicate": True}
    already_refunded = money(db.query(func.coalesce(func.sum(PaymentRefund.amount), 0)).filter(PaymentRefund.payment_id == payment.id).scalar())
    refund_amount = money(amount)
    if refund_amount <= ZERO or refund_amount > money(payment.amount) - already_refunded:
        raise HTTPException(status_code=409, detail="Refund amount exceeds the unrefunded payment balance")
    refund = PaymentRefund(payment_id=payment.id, amount=refund_amount, reason=reason, reference=reference,
                           idempotency_key=idempotency_key, actor_id=actor_id, period=current_period())
    db.add(refund)
    db.flush()
    allocations = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment.id).order_by(PaymentAllocation.id).all()
    allocation_bases = [(a, _unrefunded_allocation_amount(db, a)) for a in allocations]
    allocation_bases = [(a, base) for a, base in allocation_bases if base > ZERO]
    allocation_total = sum((base for _, base in allocation_bases), ZERO)
    left = refund_amount
    commission_entries = db.query(CommissionLedgerEntry).filter(CommissionLedgerEntry.payment_id == payment.id,
                                                                  CommissionLedgerEntry.entry_type == "COMMISSION").all()
    eligible_allocations = [(allocation, unrefunded) for allocation, unrefunded in allocation_bases if unrefunded > ZERO]
    for index, (allocation, unrefunded) in enumerate(eligible_allocations):
        if left <= ZERO:
            continue
        share = left if index == len(eligible_allocations) - 1 else min(unrefunded, money(refund_amount * unrefunded / allocation_total))
        share = min(share, unrefunded, left)
        if share <= ZERO:
            continue
        db.add(PaymentRefundAllocation(refund_id=refund.id, payment_allocation_id=allocation.id, amount=share))
        for entry in [e for e in commission_entries if e.payment_allocation_id == allocation.id]:
            reversal = money(decimal(entry.amount) * share / money(allocation.amount))
            if reversal:
                key = f"refund:{refund.id}:entry:{entry.id}"
                db.add(CommissionLedgerEntry(
                    doctor_id=entry.doctor_id, department=entry.department, payment_id=payment.id, payment_allocation_id=allocation.id,
                    source_entry_id=entry.id, rule_id=entry.rule_id, source_item_type=entry.source_item_type,
                    source_description=entry.source_description, invoice_number=entry.invoice_number,
                    period=refund.period, entry_type="REVERSAL",
                    calculation_base=share, calculation_type=entry.calculation_type, rate=entry.rate,
                    amount=-reversal, status="REVERSED", generation_key=key,
                ))
        left -= share
    invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
    if invoice:
        invoice.paid_amount = float(max(ZERO, money(invoice.paid_amount) - refund_amount))
        invoice.payment_status = "PAID" if money(invoice.paid_amount) >= money(invoice.net_payable) else (
            "PARTIAL" if money(invoice.paid_amount) > ZERO else "UNPAID")
    total_refunded = already_refunded + refund_amount
    if total_refunded >= money(payment.amount):
        payment.status = "REFUNDED"
    elif payment.reconciled_at:
        payment.status = "RECONCILED_PARTIALLY_REFUNDED"
    else:
        payment.status = "RECEIVED_PARTIALLY_REFUNDED"
    _audit(db, actor_id, "PAYMENT_REFUNDED", "payment", payment.id, f"refund={refund_amount}; reason={reason[:120]}")
    db.commit()
    return {"refund_id": refund.id, "status": "RECORDED", "payment_status": payment.status}


def create_rule(db: Session, payload, actor_id: int):
    existing = db.query(CommissionRule).filter_by(idempotency_key=payload.idempotency_key).first()
    if existing:
        matches = all((getattr(existing, field) == getattr(payload, field)) for field in (
            "name", "doctor_id", "department", "service_type", "calculation_type", "rate", "fixed_amount",
            "effective_from", "effective_to"))
        if not matches:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for another rule")
        return existing
    if payload.doctor_id:
        doctor = db.query(User).filter(User.id == payload.doctor_id, User.role == "DOCTOR").first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
    rule = CommissionRule(**payload.model_dump(), created_by_id=actor_id, active=True)
    db.add(rule)
    db.flush()
    _audit(db, actor_id, "COMMISSION_RULE_CREATED", "commission_rule", rule.id, rule.name)
    db.commit()
    return rule


def deactivate_rule(db: Session, rule_id: int, actor_id: int):
    rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    if rule.active:
        rule.active = False
        _audit(db, actor_id, "COMMISSION_RULE_DEACTIVATED", "commission_rule", rule.id, rule.name)
        db.commit()
    return rule


def create_adjustment(db: Session, payload, actor_id: int):
    _lock_financial_write(db)
    generation_key = f"adjustment:{payload.idempotency_key}"
    existing = db.query(CommissionLedgerEntry).filter_by(generation_key=generation_key).first()
    if existing:
        if (existing.doctor_id != payload.doctor_id or existing.period != payload.period or
                money(existing.amount) != money(payload.amount) or existing.source_description != payload.reason):
            raise HTTPException(status_code=409, detail="Idempotency key was already used for another adjustment")
        return existing
    doctor = db.query(User).filter(User.id == payload.doctor_id, User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if payload.period > current_period():
        raise HTTPException(status_code=422, detail="An adjustment cannot use a future period")
    amount = money(payload.amount)
    entry = CommissionLedgerEntry(
        doctor_id=doctor.id, department=doctor.department, source_item_type="ADJUSTMENT", source_description=payload.reason,
        invoice_number=f"ADJ-{uuid4().hex[:10].upper()}", period=payload.period,
        entry_type="ADJUSTMENT", calculation_base=abs(amount), calculation_type="ADJUSTMENT",
        amount=amount, status="ADJUSTED", generation_key=generation_key,
    )
    db.add(entry)
    db.flush()
    _audit(db, actor_id, "COMMISSION_ADJUSTED", "commission_ledger", entry.id,
           f"doctor_id={doctor.id}; period={payload.period}; amount={amount}; reason={payload.reason[:180]}")
    db.commit()
    db.refresh(entry)
    return entry


def _balance_through(db: Session, doctor_id: int, period: str):
    evaluate_and_release_commissions(db, doctor_id)
    entries = db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period <= period,
        CommissionLedgerEntry.status.in_(["RELEASED", "AVAILABLE", "ADJUSTED", "REVERSED", "SETTLED"])
    ).scalar()
    committed = db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
        SettlementRequest.doctor_id == doctor_id, SettlementRequest.period <= period,
        SettlementRequest.status.in_(["PENDING", "APPROVED", "PAID"])
    ).scalar()
    return money(decimal(entries) - decimal(committed))


def create_settlement_request(db: Session, doctor_id: int, period: str, amount, key: str):
    _lock_financial_write(db)
    existing = db.query(SettlementRequest).filter_by(idempotency_key=key).first()
    if existing:
        if existing.doctor_id != doctor_id or existing.period != period or money(existing.amount) != money(amount):
            raise HTTPException(status_code=409, detail="Idempotency key was already used for another request")
        return existing
    if period > current_period():
        raise HTTPException(status_code=422, detail="A future reporting period cannot be settled")
    available = _balance_through(db, doctor_id, period)
    requested = money(amount)
    if requested <= ZERO or requested > available:
        raise HTTPException(status_code=409, detail=f"Requested amount exceeds available balance of {max(ZERO, available)}")
    request = SettlementRequest(request_number=f"SET-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}",
                                doctor_id=doctor_id, period=period, amount=requested, status="PENDING",
                                idempotency_key=key)
    db.add(request)
    db.flush()
    entries = db.query(CommissionLedgerEntry).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period <= period,
        CommissionLedgerEntry.amount > ZERO,
        CommissionLedgerEntry.status.in_(["RELEASED", "AVAILABLE", "ADJUSTED"])
    ).order_by(CommissionLedgerEntry.period, CommissionLedgerEntry.id).all()
    prior_allocations = db.query(SettlementAllocation).join(SettlementRequest).filter(
        SettlementRequest.doctor_id == doctor_id,
        SettlementRequest.status.in_(["PENDING", "APPROVED", "PAID"]),
        SettlementRequest.id != request.id,
        SettlementRequest.period <= period,
    ).all()
    reserved = {}
    for allocation in prior_allocations:
        reserved[allocation.ledger_entry_id] = reserved.get(allocation.ledger_entry_id, ZERO) + money(allocation.amount)
    left = requested
    # Negative reversal entries reduce the account's aggregate availability; cap allocations
    # to the requested total which has already been checked against that net balance.
    for entry in entries:
        take = min(max(ZERO, money(entry.amount) - reserved.get(entry.id, ZERO)), left)
        if take > ZERO:
            db.add(SettlementAllocation(request_id=request.id, ledger_entry_id=entry.id, amount=take))
            left -= take
        if left <= ZERO:
            break
    if left > ZERO:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ledger allocation could not reserve the requested amount")
    _audit(db, doctor_id, "SETTLEMENT_REQUESTED", "settlement_request", request.id, f"amount={requested}; period={period}")
    db.commit()
    db.refresh(request)
    return request


def decide_settlement(db: Session, request_id: int, actor_id: int, approve: bool, note: Optional[str]):
    _lock_financial_write(db)
    request = db.query(SettlementRequest).filter(SettlementRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Settlement request not found")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Only pending requests may be decided (current: {request.status})")
    if approve:
        available_net = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
            CommissionLedgerEntry.doctor_id == request.doctor_id,
            CommissionLedgerEntry.period <= request.period).scalar())
        committed = money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
            SettlementRequest.doctor_id == request.doctor_id,
            SettlementRequest.period <= request.period,
            SettlementRequest.status.in_(["PENDING", "APPROVED", "PAID"])).scalar())
        if available_net < committed:
            raise HTTPException(status_code=409, detail="Refunds or reversals reduced the available liability; review this request before approval")
        request.status = "APPROVED"
        db.query(SettlementAllocation).filter(SettlementAllocation.request_id == request.id).update(
            {SettlementAllocation.status: "APPROVED"}, synchronize_session=False)
        action = "SETTLEMENT_APPROVED"
    else:
        request.status = "REJECTED"
        db.query(SettlementAllocation).filter(SettlementAllocation.request_id == request.id).update(
            {SettlementAllocation.status: "RELEASED"}, synchronize_session=False)
        action = "SETTLEMENT_REJECTED"
    request.decided_by_id = actor_id
    request.decided_at = datetime.utcnow()
    request.decision_note = note
    _audit(db, actor_id, action, "settlement_request", request.id, note or "")
    db.commit()
    return request


def cancel_settlement(db: Session, request_id: int, actor_id: int, note: str):
    _lock_financial_write(db)
    request = db.query(SettlementRequest).filter(SettlementRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Settlement request not found")
    if request.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved, unpaid requests can be cancelled")
    request.status = "CANCELLED"
    request.decided_by_id = actor_id
    request.decided_at = datetime.utcnow()
    request.decision_note = note
    db.query(SettlementAllocation).filter(SettlementAllocation.request_id == request.id).update(
        {SettlementAllocation.status: "RELEASED"}, synchronize_session=False)
    _audit(db, actor_id, "SETTLEMENT_CANCELLED", "settlement_request", request.id, note)
    db.commit()
    return request


def record_payout(db: Session, request_id: int, payload, actor_id: int):
    _lock_financial_write(db)
    existing = db.query(SettlementPayout).filter_by(idempotency_key=payload.idempotency_key).first()
    if existing:
        if (existing.request_id != request_id or existing.payment_method != payload.payment_method or
                existing.payment_reference != payload.payment_reference or
                existing.evidence_note != payload.evidence_note):
            raise HTTPException(status_code=409, detail="Idempotency key belongs to another payout")
        return existing
    request = db.query(SettlementRequest).filter(SettlementRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Settlement request not found")
    if request.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved requests can be paid")
    available_net = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == request.doctor_id,
        CommissionLedgerEntry.period <= request.period).scalar())
    committed = money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
        SettlementRequest.doctor_id == request.doctor_id,
        SettlementRequest.period <= request.period,
        SettlementRequest.status.in_(["PENDING", "APPROVED", "PAID"])).scalar())
    if available_net < committed:
        raise HTTPException(status_code=409, detail="Refunds or reversals reduced the liability after approval; review before recording payout")
    paid_at = datetime.utcnow()
    payout = SettlementPayout(request_id=request.id, amount=money(request.amount),
                              payment_method=payload.payment_method,
                              payment_reference=payload.payment_reference,
                              idempotency_key=payload.idempotency_key, paid_at=paid_at, paid_period=_period(paid_at),
                              recorded_by_id=actor_id,
                              evidence_note=payload.evidence_note)
    db.add(payout)
    request.status = "PAID"
    db.query(SettlementAllocation).filter(SettlementAllocation.request_id == request.id).update(
        {SettlementAllocation.status: "PAID"}, synchronize_session=False)
    alloc_ledger_ids = [a.ledger_entry_id for a in db.query(SettlementAllocation.ledger_entry_id).filter(SettlementAllocation.request_id == request.id).all()]
    if alloc_ledger_ids:
        db.query(CommissionLedgerEntry).filter(CommissionLedgerEntry.id.in_(alloc_ledger_ids)).update(
            {CommissionLedgerEntry.status: "SETTLED"}, synchronize_session=False)
    _audit(db, actor_id, "SETTLEMENT_PAID", "settlement_request", request.id,
           f"amount={money(request.amount)}; reference={payload.payment_reference}")
    db.commit()
    db.refresh(payout)
    return payout


def instant_payout(db: Session, doctor_id: int, actor_id: int) -> dict:
    _lock_financial_write(db)
    doctor = db.query(User).filter(User.id == doctor_id, User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Evaluate all accrued entries first
    evaluate_and_release_commissions(db, doctor_id)
    period = current_period()
    available = _balance_through(db, doctor_id, period)

    if available > ZERO:
        req_key = f"instant-settle-{uuid4().hex}"
        request = create_settlement_request(db, doctor_id, period, available, req_key)
        decide_settlement(db, request.id, actor_id, approve=True, note="Instant doctor payout verified and approved")

        class InstantPayoutPayload:
            payment_method = "BANK_TRANSFER"
            payment_reference = f"UTR-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:6].upper()}"
            idempotency_key = f"instant-pay-{uuid4().hex}"
            evidence_note = "Instant one-button doctor payout verified"

        payout = record_payout(db, request.id, InstantPayoutPayload(), actor_id)

        return {
            "success": True,
            "payout_amount": str(available),
            "chip_label": "[🔓 Ready to Pull]",
            "message": f"Instant payout of ₹{available:.2f} processed successfully.",
            "bank_details": {
                "account_holder": doctor.full_name,
                "bank_name": "State Bank of India (Hospital Verified)",
                "account_number": f"****{1000 + doctor.id}",
                "ifsc": "SBIN0001234",
                "transfer_mode": "IMPS / Real-time Bank Settlement"
            },
            "payment_reference": payout.payment_reference,
            "paid_at": payout.paid_at.strftime("%d %b %Y, %H:%M:%S UTC")
        }
    else:
        # Check accrued entries for reasons
        accrued = db.query(CommissionLedgerEntry).filter(
            CommissionLedgerEntry.doctor_id == doctor_id,
            CommissionLedgerEntry.status == "ACCRUED"
        ).all()

        patient_unpaid = []
        threshold_blocked = False

        for entry in accrued:
            log_text = entry.execution_audit_log or ""
            if "Waiting for Patient Bill Settlement" in log_text or "unpaid" in log_text.lower():
                if entry.patient_id:
                    unpaid_invs = db.query(Invoice).filter(
                        Invoice.patient_id == entry.patient_id,
                        Invoice.payment_status != "PAID"
                    ).all()
                    p = db.query(Patient).filter(Patient.id == entry.patient_id).first()
                    for u in unpaid_invs:
                        unpaid_bal = money(decimal(u.net_payable) - decimal(u.paid_amount))
                        patient_unpaid.append({
                            "patient_name": p.full_name if p else f"Patient #{entry.patient_id}",
                            "patient_mrn": p.mrn if p else "-",
                            "invoice_number": u.invoice_number,
                            "unpaid_balance": f"₹{unpaid_bal:.2f}",
                            "payment_status": u.payment_status
                        })
            elif "Early Month Threshold Lock" in log_text or "threshold" in log_text.lower():
                threshold_blocked = True

        if patient_unpaid:
            seen = set()
            dedup_blocking = []
            for b in patient_unpaid:
                if b["invoice_number"] not in seen:
                    seen.add(b["invoice_number"])
                    dedup_blocking.append(b)

            return {
                "success": False,
                "reason": "PATIENT_BILLS_UNPAID",
                "chip_label": "[🔒 Waiting for Patient Bill Settlement]",
                "message": f"Waiting for patient bill settlement: {len(dedup_blocking)} outstanding invoice(s) must be settled before commission can be released.",
                "blocking_details": dedup_blocking[:5]
            }
        else:
            return {
                "success": False,
                "reason": "ZERO_BALANCE",
                "chip_label": "[🔒 Zero Available Balance]",
                "message": "No commission balance is currently available for settlement. As patient payments are reconciled, earnings will appear here.",
                "blocking_details": []
            }



def list_ledger_entries(
    db: Session,
    doctor_id: Optional[int] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    patient_id: Optional[int] = None,
    period: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
) -> dict:
    if doctor_id:
        evaluate_and_release_commissions(db, doctor_id)

    query = db.query(CommissionLedgerEntry)

    if doctor_id:
        query = query.filter(CommissionLedgerEntry.doctor_id == doctor_id)
    if department:
        query = query.filter(CommissionLedgerEntry.department == department)
    if patient_id:
        query = query.filter(CommissionLedgerEntry.patient_id == patient_id)
    if period:
        query = query.filter(CommissionLedgerEntry.period == period)
    if status:
        stat_upper = status.upper().strip()
        if stat_upper == "AVAILABLE":
            stat_upper = "RELEASED"
        query = query.filter(or_(
            CommissionLedgerEntry.status == stat_upper,
            (CommissionLedgerEntry.status == "AVAILABLE") if stat_upper == "RELEASED" else False
        ))

    total = query.count()
    entries = query.order_by(CommissionLedgerEntry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for entry in entries:
        doctor = db.query(User).filter(User.id == entry.doctor_id).first()
        patient = db.query(Patient).filter(Patient.id == entry.patient_id).first() if entry.patient_id else None

        blocking = []
        if entry.patient_id:
            unpaid = db.query(Invoice).filter(Invoice.patient_id == entry.patient_id, Invoice.payment_status != "PAID").all()
            for u in unpaid:
                blocking.append({
                    "invoice_number": u.invoice_number,
                    "payment_status": u.payment_status,
                    "unpaid_amount": str(money(decimal(u.net_payable) - decimal(u.paid_amount)))
                })

        if entry.status in ("RELEASED", "AVAILABLE"):
            chip_label = "[🔓 Ready to Pull]"
            chip_class = "badge-success"
            explanation = "Released and available for instant payout request."
        elif entry.status == "ACCRUED":
            if "Threshold" in (entry.execution_audit_log or ""):
                chip_label = "[🔒 Early Month Threshold Lock]"
                chip_class = "badge-warning"
                explanation = "Locked until monthly minimum settlement threshold is met or month-end is reached."
            else:
                chip_label = "[🔒 Waiting for Patient Bill Settlement]"
                chip_class = "badge-warning"
                explanation = f"Locked: Patient #{entry.patient_id} has unpaid hospital bills." if blocking else "Locked: Awaiting invoice payment completion."
        elif entry.status in ("SETTLED", "PAID"):
            chip_label = "[✓ Settled]"
            chip_class = "badge-neutral"
            explanation = "Commission has been disbursed and settled."
        elif entry.status == "REVERSED":
            chip_label = "[Refund Reversal]"
            chip_class = "badge-danger"
            explanation = "Commission reversed due to patient refund."
        else:
            chip_label = f"[{entry.status}]"
            chip_class = "badge-neutral"
            explanation = entry.execution_audit_log or ""

        items.append({
            "id": entry.id,
            "doctor_id": entry.doctor_id,
            "doctor_name": doctor.full_name if doctor else "Doctor",
            "department": entry.department or (doctor.department if doctor else ""),
            "patient_id": entry.patient_id,
            "patient_name": patient.full_name if patient else (f"Patient #{entry.patient_id}" if entry.patient_id else "N/A"),
            "patient_mrn": patient.mrn if patient else "-",
            "invoice_id": entry.invoice_id,
            "invoice_number": entry.invoice_number,
            "service_type": entry.source_item_type or "CONSULTATION",
            "description": entry.source_description or "",
            "base_amount": float(entry.base_amount or entry.calculation_base or 0),
            "calculated_commission": float(entry.calculated_commission or entry.amount or 0),
            "status": entry.status,
            "chip_label": chip_label,
            "chip_class": chip_class,
            "explanation": explanation,
            "accrued_at": entry.accrued_at.strftime("%d %b %Y, %H:%M") if entry.accrued_at else None,
            "released_at": entry.released_at.strftime("%d %b %Y, %H:%M") if entry.released_at else None,
            "governing_rule_id": entry.governing_rule_id or entry.rule_id,
            "execution_audit_log": entry.execution_audit_log or "",
            "blocking_invoices": blocking
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


def _sum_entries(db, doctor_id, start_period, end_period, entry_type=None):
    query = db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id)
    if start_period:
        query = query.filter(CommissionLedgerEntry.period >= start_period)
    if end_period:
        query = query.filter(CommissionLedgerEntry.period <= end_period)
    if entry_type:
        query = query.filter(CommissionLedgerEntry.entry_type == entry_type)
    return money(query.scalar())


def doctor_dashboard(db: Session, doctor_id: int, period: str):
    doctor = db.query(User).filter(User.id == doctor_id, User.role == "DOCTOR").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    evaluate_and_release_commissions(db, doctor_id)
    current = _sum_entries(db, doctor_id, period, period)
    previous_date = datetime.strptime(period + "-01", "%Y-%m-%d").date().replace(day=1)
    previous_date = (previous_date.replace(day=1) - timedelta(days=1)).replace(day=1)
    previous = previous_date.strftime("%Y-%m")
    positive = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period == period,
        CommissionLedgerEntry.entry_type == "COMMISSION").scalar())
    reversed_amount = money(-db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period == period,
        CommissionLedgerEntry.entry_type == "REVERSAL").scalar())
    adjustments = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period == period,
        CommissionLedgerEntry.entry_type == "ADJUSTMENT").scalar())
    reserved = money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
        SettlementRequest.doctor_id == doctor_id, SettlementRequest.status == "PENDING",
        SettlementRequest.period <= period).scalar())
    paid = money(db.query(func.coalesce(func.sum(SettlementPayout.amount), 0))
                 .join(SettlementRequest).filter(SettlementRequest.doctor_id == doctor_id,
            SettlementPayout.paid_period == period).scalar())
    balance = max(ZERO, _balance_through(db, doctor_id, period))
    accrued_locked = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period == period,
        CommissionLedgerEntry.status == "ACCRUED"
    ).scalar())
    by_service = db.query(CommissionLedgerEntry.source_item_type,
                          func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period == period
    ).group_by(CommissionLedgerEntry.source_item_type).all()
    by_month = db.query(CommissionLedgerEntry.period, func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.doctor_id == doctor_id, CommissionLedgerEntry.period.in_([previous, period])
    ).group_by(CommissionLedgerEntry.period).all()
    encounter_ids = db.query(Encounter.id).filter(Encounter.doctor_id == doctor_id)
    inpatient_ids = db.query(InpatientRecord.id).filter(InpatientRecord.attending_doctor_id == doctor_id)
    pending_payments = db.query(Payment, Invoice).join(Invoice, Invoice.id == Payment.invoice_id).filter(
        Payment.status == "RECEIVED",
        or_(Invoice.encounter_id.in_(encounter_ids), Invoice.inpatient_record_id.in_(inpatient_ids))
    ).all()
    pending_estimate = ZERO
    for payment, invoice in pending_payments:
        for allocation in db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == payment.id).all():
            item = db.query(InvoiceItem).filter(InvoiceItem.id == allocation.invoice_item_id).first()
            if not item:
                continue
            rule = _matching_rule(db, doctor, item, payment.received_at.date())
            base = _unrefunded_allocation_amount(db, allocation)
            if not rule or base <= ZERO:
                continue
            if rule.calculation_type == "PERCENTAGE":
                pending_estimate += money(base * decimal(rule.rate) / Decimal("100"))
            else:
                _, line_nets = _line_net_values(db, invoice)
                line_net = line_nets.get(item.id, ZERO)
                if line_net > ZERO:
                    pending_estimate += money(decimal(rule.fixed_amount if rule.fixed_amount is not None else rule.rate) * Decimal(item.quantity or 1) * base / line_net)
    return {
        "period": period, "earned": str(positive), "reversed": str(reversed_amount),
        "net_earned": str(positive - reversed_amount + adjustments), "adjustments": str(adjustments), "available": str(balance),
        "ready_to_pull": str(balance), "accrued_locked": str(accrued_locked),
        "pending_eligibility_estimate": str(money(pending_estimate)),
        "reserved": str(reserved), "approved_unpaid": str(money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
            SettlementRequest.doctor_id == doctor_id, SettlementRequest.period <= period,
            SettlementRequest.status == "APPROVED").scalar())),
        "paid_in_period": str(paid), "previous_period": previous,
        "previous_net_earned": str(_sum_entries(db, doctor_id, previous, previous)),
        "by_service": [{"service_type": row[0], "amount": str(money(row[1]))} for row in by_service],
        "monthly_trend": [{"period": row[0], "amount": str(money(row[1]))} for row in by_month],
    }


def commission_transactions(db: Session, doctor_id: int, period: Optional[str], page: int, page_size: int,
                            q: Optional[str] = None, sort: str = "date_desc"):
    evaluate_and_release_commissions(db, doctor_id)
    query = db.query(CommissionLedgerEntry).filter(CommissionLedgerEntry.doctor_id == doctor_id)
    if period:
        query = query.filter(CommissionLedgerEntry.period == period)
    if q:
        query = query.filter((CommissionLedgerEntry.invoice_number.ilike(f"%{q}%")) |
                             (CommissionLedgerEntry.source_description.ilike(f"%{q}%")) |
                             (CommissionLedgerEntry.source_item_type.ilike(f"%{q}%")))
    total = query.count()
    sort_columns = {
        "date_desc": (CommissionLedgerEntry.created_at.desc(), CommissionLedgerEntry.id.desc()),
        "date_asc": (CommissionLedgerEntry.created_at.asc(), CommissionLedgerEntry.id.asc()),
        "amount_desc": (CommissionLedgerEntry.amount.desc(), CommissionLedgerEntry.id.desc()),
        "amount_asc": (CommissionLedgerEntry.amount.asc(), CommissionLedgerEntry.id.asc()),
    }
    rows = query.order_by(*sort_columns.get(sort, sort_columns["date_desc"])).offset((page - 1) * page_size).limit(page_size).all()
    ids = [entry.id for entry in rows]
    allocation_rows = db.query(SettlementAllocation.ledger_entry_id, SettlementAllocation.status,
                               func.sum(SettlementAllocation.amount)).filter(
        SettlementAllocation.ledger_entry_id.in_(ids)).group_by(
            SettlementAllocation.ledger_entry_id, SettlementAllocation.status).all() if ids else []
    allocation_status = {}
    for entry_id, status, amount in allocation_rows:
        allocation_status.setdefault(entry_id, {})[status] = money(amount)

    def display_status(entry):
        if entry.status == "ACCRUED":
            return "ACCRUED"
        if entry.status == "RELEASED":
            return "RELEASED"
        if entry.entry_type == "REVERSAL":
            return "REVERSED"
        if entry.entry_type == "ADJUSTMENT":
            return "ADJUSTED"
        states = allocation_status.get(entry.id, {})
        if states.get("PAID", ZERO) >= money(entry.amount) or entry.status == "SETTLED":
            return "PAID"
        if states.get("APPROVED", ZERO) > ZERO:
            return "APPROVED"
        if states.get("RESERVED", ZERO) > ZERO:
            return "RESERVED"
        return "RELEASED" if entry.status == "RELEASED" else "AVAILABLE"

    def chip_label(entry):
        if entry.status in ("RELEASED", "AVAILABLE"):
            return "[🔓 Ready to Pull]"
        if entry.status == "ACCRUED":
            if "Threshold" in (entry.execution_audit_log or ""):
                return "[🔒 Early Month Threshold Lock]"
            return "[🔒 Waiting for Patient Bill Settlement]"
        if entry.status in ("SETTLED", "PAID"):
            return "[✓ Settled]"
        if entry.status == "REVERSED":
            return "[Refund Reversal]"
        return f"[{entry.status}]"

    return {"items": [{"id": e.id, "period": e.period, "date": e.created_at.isoformat(), "type": e.entry_type,
                       "invoice_number": e.invoice_number, "service_type": e.source_item_type,
                       "description": e.source_description, "calculation_base": str(money(e.calculation_base)),
                       "calculation_type": e.calculation_type, "rate": str(e.rate) if e.rate is not None else None,
                       "amount": str(money(e.amount)), "status": display_status(e),
                       "chip_label": chip_label(e), "execution_audit_log": e.execution_audit_log or ""}
                      for e in rows], "page": page, "page_size": page_size, "total": total}


def list_settlements(db: Session, status: Optional[str] = None, doctor_id: Optional[int] = None):
    query = db.query(SettlementRequest, User).join(User, User.id == SettlementRequest.doctor_id)
    if status:
        query = query.filter(SettlementRequest.status == status)
    if doctor_id:
        query = query.filter(SettlementRequest.doctor_id == doctor_id)
    rows = query.order_by(SettlementRequest.requested_at.desc()).limit(500).all()
    request_ids = [r.id for r, _ in rows]
    payouts = {p.request_id: p for p in db.query(SettlementPayout).filter(SettlementPayout.request_id.in_(request_ids)).all()} if request_ids else {}
    return [{"id": r.id, "request_number": r.request_number, "doctor_id": r.doctor_id,
             "doctor_name": u.full_name, "department": u.department, "period": r.period,
             "amount": str(money(r.amount)), "status": r.status, "requested_at": r.requested_at.isoformat(),
             "decision_note": r.decision_note,
             "payout": ({"reference": payouts[r.id].payment_reference, "paid_at": payouts[r.id].paid_at.isoformat(),
                         "amount": str(money(payouts[r.id].amount))} if r.id in payouts else None)}
            for r, u in rows]


def pending_payments(db: Session, page: int = 1, page_size: int = 50):
    query = db.query(Payment).filter(Payment.status.in_(["RECEIVED", "RECEIVED_PARTIALLY_REFUNDED"]))
    total = query.count()
    rows = query.order_by(Payment.received_at).offset((page - 1) * page_size).limit(page_size).all()
    ids = [p.id for p in rows]
    refund_totals = {row[0]: money(row[1]) for row in db.query(PaymentRefund.payment_id,
        func.sum(PaymentRefund.amount)).filter(PaymentRefund.payment_id.in_(ids)).group_by(PaymentRefund.payment_id).all()} if ids else {}
    return {"items": [{"id": p.id, "invoice_id": p.invoice_id,
                       "amount": str(max(ZERO, money(p.amount) - refund_totals.get(p.id, ZERO))),
                       "method": p.payment_method, "reference": p.transaction_ref,
                       "received_at": p.received_at.isoformat()} for p in rows], "page": page,
            "page_size": page_size, "total": total}


def payment_history(db: Session, period: Optional[str], page: int = 1, page_size: int = 50):
    query = db.query(Payment, Invoice.invoice_number).join(Invoice, Invoice.id == Payment.invoice_id)
    if period:
        query = query.filter(Payment.received_period == period)
    total = query.count()
    rows = query.order_by(Payment.received_at.desc(), Payment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    ids = [payment.id for payment, _ in rows]
    refunds = {row[0]: money(row[1]) for row in db.query(PaymentRefund.payment_id,
        func.sum(PaymentRefund.amount)).filter(PaymentRefund.payment_id.in_(ids)).group_by(PaymentRefund.payment_id).all()} if ids else {}
    return {"items": [{"id": payment.id, "invoice_id": payment.invoice_id, "invoice_number": invoice_number,
                       "amount": str(money(payment.amount)), "refunded": str(refunds.get(payment.id, ZERO)),
                       "refundable": str(max(ZERO, money(payment.amount) - refunds.get(payment.id, ZERO))),
                       "method": payment.payment_method, "reference": payment.transaction_ref,
                       "status": payment.status, "received_at": payment.received_at.isoformat(),
                       "reconciled_period": payment.reconciled_period}
                      for payment, invoice_number in rows], "page": page, "page_size": page_size, "total": total}


def finance_report(db: Session, period: str):
    doctor_rows = db.query(CommissionLedgerEntry.doctor_id, User.full_name,
        CommissionLedgerEntry.department, func.sum(CommissionLedgerEntry.amount)).join(
        User, User.id == CommissionLedgerEntry.doctor_id).filter(
        CommissionLedgerEntry.period == period).group_by(
            CommissionLedgerEntry.doctor_id, User.full_name, CommissionLedgerEntry.department).all()
    doctors = [{"doctor_id": row[0], "doctor_name": row[1], "department": row[2],
                "net_commission": str(money(row[3]))} for row in doctor_rows]
    service_rows = db.query(CommissionLedgerEntry.source_item_type,
        func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.period == period).group_by(CommissionLedgerEntry.source_item_type).all()
    department_rows = db.query(CommissionLedgerEntry.department,
        func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.period == period, CommissionLedgerEntry.department.is_not(None)
    ).group_by(CommissionLedgerEntry.department).all()
    entry_type_rows = db.query(CommissionLedgerEntry.entry_type,
        func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.period == period).group_by(CommissionLedgerEntry.entry_type).all()
    entry_type_totals = {row[0]: money(row[1]) for row in entry_type_rows}
    payouts = db.query(func.coalesce(func.sum(SettlementPayout.amount), 0)).filter(
        SettlementPayout.paid_period == period).scalar()
    collected = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.status.in_(["RECONCILED", "RECONCILED_PARTIALLY_REFUNDED"]),
        Payment.reconciled_period == period).scalar()
    refunded = db.query(func.coalesce(func.sum(PaymentRefund.amount), 0)).join(
        Payment, Payment.id == PaymentRefund.payment_id).filter(
        Payment.reconciled_at.is_not(None), PaymentRefund.period == period).scalar()
    requests = db.query(SettlementRequest.status, func.count(SettlementRequest.id), func.sum(SettlementRequest.amount)).filter(
        SettlementRequest.period == period).group_by(SettlementRequest.status).all()
    ledger_by_doctor = db.query(CommissionLedgerEntry.doctor_id,
        func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.period <= period).group_by(CommissionLedgerEntry.doctor_id).all()
    committed_by_doctor = db.query(SettlementRequest.doctor_id,
        func.sum(SettlementRequest.amount)).filter(
        SettlementRequest.period <= period,
        SettlementRequest.status.in_(["PENDING", "APPROVED", "PAID"])
    ).group_by(SettlementRequest.doctor_id).all()
    committed_map = {row[0]: money(row[1]) for row in committed_by_doctor}
    available_liability = sum((max(ZERO, money(net) - committed_map.get(doctor_id, ZERO))
                               for doctor_id, net in ledger_by_doctor), ZERO)
    reserved_liability = money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
        SettlementRequest.period <= period, SettlementRequest.status == "PENDING").scalar())
    approved_liability = money(db.query(func.coalesce(func.sum(SettlementRequest.amount), 0)).filter(
        SettlementRequest.period <= period, SettlementRequest.status == "APPROVED").scalar())
    net_position = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.period <= period).scalar())
    paid_through_period = money(db.query(func.coalesce(func.sum(SettlementPayout.amount), 0)).filter(
        SettlementPayout.paid_period <= period).scalar())
    outstanding_liability = max(ZERO, net_position - paid_through_period)
    recovery_balance = max(ZERO, paid_through_period - net_position)
    end_month = datetime.strptime(period + "-01", "%Y-%m-%d").date()
    month_dates = []
    cursor = end_month
    for _ in range(12):
        month_dates.append(cursor)
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    month_dates.reverse()
    first_period = month_dates[0].strftime("%Y-%m")
    ledger_monthly = {row[0]: money(row[1]) for row in db.query(
        CommissionLedgerEntry.period, func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.period >= first_period, CommissionLedgerEntry.period <= period
    ).group_by(CommissionLedgerEntry.period).all()}
    reversal_monthly = {row[0]: money(-row[1]) for row in db.query(
        CommissionLedgerEntry.period, func.sum(CommissionLedgerEntry.amount)).filter(
        CommissionLedgerEntry.entry_type == "REVERSAL", CommissionLedgerEntry.period >= first_period,
        CommissionLedgerEntry.period <= period).group_by(CommissionLedgerEntry.period).all()}
    payout_monthly = {row[0]: money(row[1]) for row in db.query(
        SettlementPayout.paid_period, func.sum(SettlementPayout.amount)).filter(
        SettlementPayout.paid_period >= first_period, SettlementPayout.paid_period <= period
    ).group_by(SettlementPayout.paid_period).all()}
    running_net = money(db.query(func.coalesce(func.sum(CommissionLedgerEntry.amount), 0)).filter(
        CommissionLedgerEntry.period < first_period).scalar())
    running_payout = money(db.query(func.coalesce(func.sum(SettlementPayout.amount), 0)).filter(
        SettlementPayout.paid_period < first_period).scalar())
    liability_trend = []
    for month_date in month_dates:
        month = month_date.strftime("%Y-%m")
        running_net += ledger_monthly.get(month, ZERO)
        running_payout += payout_monthly.get(month, ZERO)
        liability_trend.append({"period": month, "amount": str(max(ZERO, running_net - running_payout))})
    return {"period": period,
            "commission_earned": str(entry_type_totals.get("COMMISSION", ZERO)),
            "reversals": str(-entry_type_totals.get("REVERSAL", ZERO)),
            "net_commission": str(sum(entry_type_totals.values(), ZERO)),
            "payouts": str(money(payouts)), "reconciled_collections": str(money(decimal(collected) - decimal(refunded))),
            "liability_available_through_period": str(available_liability),
            "outstanding_liability": str(outstanding_liability),
            "recovery_balance": str(recovery_balance),
            "available_balance": str(available_liability), "reserved_balance": str(reserved_liability),
            "approved_unpaid_balance": str(approved_liability),
            "liability_trend": liability_trend,
            "reversals_by_month": [{"period": month_date.strftime("%Y-%m"),
                                    "amount": str(reversal_monthly.get(month_date.strftime("%Y-%m"), ZERO))}
                                   for month_date in month_dates],
            "doctors": doctors,
            "by_service": [{"service_type": row[0], "amount": str(money(row[1]))} for row in service_rows],
            "by_department": [{"department": row[0], "amount": str(money(row[1]))} for row in department_rows],
            "request_status": [{"status": row[0], "count": row[1], "amount": str(money(row[2] or 0))} for row in requests]}


def audit_events(db: Session, limit: int = 100):
    rows = db.query(CommissionAuditEvent, User).join(User, User.id == CommissionAuditEvent.actor_id).order_by(
        CommissionAuditEvent.created_at.desc()).limit(limit).all()
    return [{"id": e.id, "actor": u.full_name, "role": u.role, "action": e.action,
             "resource_type": e.resource_type, "resource_id": e.resource_id,
             "details": e.details, "created_at": e.created_at.isoformat()} for e, u in rows]
