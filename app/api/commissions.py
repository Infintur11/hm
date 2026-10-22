import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_permissions
from app.models.commission import CommissionRule, SettlementRequest
from app.models.user import User
from app.schemas.commission import (
    CommissionRuleCreate, SettlementRequestCreate, SettlementDecision, PayoutCreate,
    CommissionAdjustmentCreate,
)
from app.services import commission_service as service
from app.services.pdf_service import generate_monthly_commission_pdf, generate_doctor_statement_pdf

router = APIRouter(prefix="/api/commissions", tags=["Commissions & Settlements"])


def _is_finance(user: User) -> bool:
    return user.role in ("ADMIN", "SUPER_ADMIN")


def _authorize_doctor_or_finance(user: User, doctor_id: int):
    if user.role == "DOCTOR" and user.id != doctor_id:
        raise HTTPException(status_code=403, detail="Doctors may access only their own commission records")
    if user.role != "DOCTOR" and not _is_finance(user):
        raise HTTPException(status_code=403, detail="Access denied")


def _rule_out(rule):
    return {"id": rule.id, "name": rule.name, "doctor_id": rule.doctor_id,
            "department": rule.department, "service_type": rule.service_type,
            "calculation_type": rule.calculation_type,
            "rate": str(rule.rate) if rule.rate is not None else None,
            "fixed_amount": str(rule.fixed_amount) if rule.fixed_amount is not None else None,
            "require_all_patient_bills_paid": bool(rule.require_all_patient_bills_paid),
            "min_settlement_threshold": float(rule.min_settlement_threshold or 0.0),
            "is_active": bool(rule.is_active if rule.is_active is not None else rule.active),
            "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
            "active": rule.active}


@router.get("/ledger")
def get_ledger(
    doctor_id: Optional[int] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    patient_id: Optional[int] = None,
    period: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    target = doctor_id
    if user.role == "DOCTOR":
        if target and target != user.id:
            raise HTTPException(status_code=403, detail="Doctors may access only their own commission records")
        target = user.id
    elif not _is_finance(user):
        raise HTTPException(status_code=403, detail="Access denied")

    return service.list_ledger_entries(
        db,
        doctor_id=target,
        department=department,
        status=status,
        patient_id=patient_id,
        period=period,
        page=page,
        page_size=page_size
    )


@router.post("/evaluate")
def evaluate_commissions(
    doctor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    target = doctor_id
    if user.role == "DOCTOR":
        if target and target != user.id:
            raise HTTPException(status_code=403, detail="Doctors may evaluate only their own commission records")
        target = user.id
    elif not _is_finance(user):
        raise HTTPException(status_code=403, detail="Access denied")

    if target:
        res = service.evaluate_and_release_commissions(db, target)
        return {"evaluated_doctors": [target], "result": res}
    else:
        doctors = db.query(User).filter(User.role == "DOCTOR", User.is_active == True).all()
        results = {}
        for d in doctors:
            results[d.id] = service.evaluate_and_release_commissions(db, d.id)
        return {"evaluated_doctors": [d.id for d in doctors], "results": results}


@router.post("/instant-payout")
async def instant_payout(
    request: Request,
    doctor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    target = doctor_id
    if not target:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target = body.get("doctor_id")
        except Exception:
            pass

    if user.role == "DOCTOR":
        if target and target != user.id:
            raise HTTPException(status_code=403, detail="Doctors may request payouts only for themselves")
        target = user.id
    elif not _is_finance(user):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target:
        raise HTTPException(status_code=422, detail="doctor_id is required")

    return service.instant_payout(db, target, user.id)


@router.get("/dashboard")
def get_dashboard(period: str = Query(default_factory=service.current_period, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                  doctor_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = doctor_id or user.id
    _authorize_doctor_or_finance(user, target)
    return service.doctor_dashboard(db, target, period)


@router.get("/transactions")
def get_transactions(period: Optional[str] = None, q: Optional[str] = None, page: int = Query(1, ge=1),
                     page_size: int = Query(25, ge=1, le=100),
                     sort: str = Query("date_desc", pattern=r"^(date_desc|date_asc|amount_desc|amount_asc)$"),
                     doctor_id: Optional[int] = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = doctor_id or user.id
    _authorize_doctor_or_finance(user, target)
    return service.commission_transactions(db, target, period, page, page_size, q, sort)


@router.get("/statements/{period}")
def download_statement(period: str, doctor_id: Optional[int] = None, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    target = doctor_id or user.id
    _authorize_doctor_or_finance(user, target)
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=422, detail="Period must use YYYY-MM format")
    doctor = db.query(User).filter(User.id == target).first()
    rows = service.commission_transactions(db, target, period, 1, 10000)["items"]
    summary = service.doctor_dashboard(db, target, period)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Monthly Commission Statement", doctor.full_name if doctor else "Doctor", period])
    writer.writerow(["Earned", summary["earned"], "Reversed", summary["reversed"],
                     "Available", summary["available"], "Paid in period", summary["paid_in_period"]])
    writer.writerow(["Date", "Entry type", "Invoice", "Service", "Description", "Collected base", "Rule type", "Rate", "Commission"])
    for row in rows:
        writer.writerow([row["date"], row["type"], row["invoice_number"], row["service_type"],
                         row["description"], row["calculation_base"], row["calculation_type"],
                         row["rate"] or "", row["amount"]])
    safe_name = (doctor.username if doctor else f"doctor-{target}").replace("/", "-")
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="commission-{safe_name}-{period}.csv"'})


@router.post("/settlements", status_code=201)
def request_settlement(payload: SettlementRequestCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_permissions("commission:self"))):
    if user.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Settlement requests are available to doctors")
    request = service.create_settlement_request(db, user.id, payload.period, payload.amount, payload.idempotency_key)
    return {"id": request.id, "request_number": request.request_number, "doctor_id": request.doctor_id,
            "period": request.period, "amount": str(request.amount), "status": request.status,
            "requested_at": request.requested_at.isoformat()}


@router.get("/settlements")
def get_settlements(status: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "DOCTOR":
        return service.list_settlements(db, status, doctor_id=user.id)
    if not _is_finance(user):
        raise HTTPException(status_code=403, detail="Access denied")
    return service.list_settlements(db, status)


@router.post("/settlements/{request_id}/approve")
def approve_settlement(request_id: int, payload: SettlementDecision, db: Session = Depends(get_db),
                       user: User = Depends(require_permissions("commission:manage"))):
    request = service.decide_settlement(db, request_id, user.id, True, payload.note)
    return {"id": request.id, "status": request.status, "decided_at": request.decided_at.isoformat()}


@router.post("/settlements/{request_id}/reject")
def reject_settlement(request_id: int, payload: SettlementDecision, db: Session = Depends(get_db),
                      user: User = Depends(require_permissions("commission:manage"))):
    request = service.decide_settlement(db, request_id, user.id, False, payload.note)
    return {"id": request.id, "status": request.status, "decided_at": request.decided_at.isoformat()}


@router.post("/settlements/{request_id}/cancel")
def cancel_approved_settlement(request_id: int, payload: SettlementDecision, db: Session = Depends(get_db),
                               user: User = Depends(require_permissions("commission:manage"))):
    if not payload.note or not payload.note.strip():
        raise HTTPException(status_code=422, detail="A cancellation reason is required")
    request = service.cancel_settlement(db, request_id, user.id, payload.note.strip())
    return {"id": request.id, "status": request.status, "decided_at": request.decided_at.isoformat()}


@router.post("/settlements/{request_id}/payout")
def payout_settlement(request_id: int, payload: PayoutCreate, db: Session = Depends(get_db),
                      user: User = Depends(require_permissions("commission:payout"))):
    payout = service.record_payout(db, request_id, payload, user.id)
    return {"id": payout.id, "request_id": payout.request_id, "amount": str(payout.amount),
            "payment_reference": payout.payment_reference, "paid_at": payout.paid_at.isoformat()}


@router.get("/rules")
def get_rules(db: Session = Depends(get_db), user: User = Depends(require_permissions("commission:read_all"))):
    return [_rule_out(rule) for rule in db.query(CommissionRule).order_by(CommissionRule.active.desc(),
                                                                            CommissionRule.effective_from.desc()).limit(500).all()]


@router.post("/rules", status_code=201)
def add_rule(payload: CommissionRuleCreate, db: Session = Depends(get_db),
             user: User = Depends(require_permissions("commission:manage"))):
    return _rule_out(service.create_rule(db, payload, user.id))


@router.post("/rules/{rule_id}/deactivate")
def disable_rule(rule_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_permissions("commission:manage"))):
    return _rule_out(service.deactivate_rule(db, rule_id, user.id))


@router.get("/reports/monthly")
def monthly_report(period: str = Query(default_factory=service.current_period, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                   db: Session = Depends(get_db), user: User = Depends(require_permissions("commission:read_all"))):
    return service.finance_report(db, period)


@router.get("/reports/monthly.csv")
def monthly_report_csv(period: str = Query(default_factory=service.current_period, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                       db: Session = Depends(get_db), user: User = Depends(require_permissions("commission:read_all"))):
    report = service.finance_report(db, period)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Monthly Commission Finance Report", period])
    writer.writerow(["Reconciled collections", report["reconciled_collections"], "Commission earned", report["commission_earned"],
                     "Refund reversals", report["reversals"], "Net commission", report["net_commission"],
                     "Payouts", report["payouts"], "Outstanding liability", report["outstanding_liability"]])
    writer.writerow([])
    writer.writerow(["Doctor ID", "Doctor", "Department", "Net commission"])
    for row in report["doctors"]:
        writer.writerow([row["doctor_id"], row["doctor_name"], row["department"] or "", row["net_commission"]])
    writer.writerow([])
    writer.writerow(["Service type", "Net commission"])
    for row in report["by_service"]:
        writer.writerow([row["service_type"], row["amount"]])
    writer.writerow([])
    writer.writerow(["Department", "Net commission"])
    for row in report["by_department"]:
        writer.writerow([row["department"], row["amount"]])
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="hms-commission-report-{period}.csv"'})


@router.get("/reports/monthly.pdf")
def monthly_report_pdf(
    period: str = Query(default_factory=service.current_period, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions("commission:read_all"))
):
    report = service.finance_report(db, period)
    ledger_entries = service.list_ledger_entries(db, period=period, page=1, page_size=200).get("items", [])
    pdf_bytes = generate_monthly_commission_pdf(report, period, ledger_entries)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="hms-commission-report-{period}.pdf"'}
    )


@router.get("/statement.pdf")
def doctor_statement_pdf(
    period: str = Query(default_factory=service.current_period, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    doctor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    target_id = doctor_id or user.id
    _authorize_doctor_or_finance(user, target_id)
    doc_user = db.query(User).filter(User.id == target_id).first()
    if not doc_user:
        raise HTTPException(status_code=404, detail="Doctor not found")
    dashboard = service.doctor_dashboard(db, target_id, period)
    ledger_entries = service.list_ledger_entries(db, doctor_id=target_id, period=period, page=1, page_size=100).get("items", [])
    pdf_bytes = generate_doctor_statement_pdf(doc_user, dashboard, ledger_entries, period)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="commission-statement-{doc_user.username}-{period}.pdf"'}
    )


@router.post("/adjustments", status_code=201)
def create_adjustment(payload: CommissionAdjustmentCreate, db: Session = Depends(get_db),
                      user: User = Depends(require_permissions("commission:manage"))):
    entry = service.create_adjustment(db, payload, user.id)
    return {"id": entry.id, "doctor_id": entry.doctor_id, "period": entry.period,
            "amount": str(entry.amount), "reason": entry.source_description, "status": "RECORDED"}


@router.get("/audit")
def commission_audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db),
                     user: User = Depends(require_permissions("commission:read_all"))):
    return service.audit_events(db, limit)


@router.get("/payments/pending")
def get_pending_payments(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                         db: Session = Depends(get_db), user: User = Depends(require_permissions("billing:reconcile"))):
    return service.pending_payments(db, page, page_size)


@router.post("/payments/{payment_id}/reconcile")
def reconcile_payment(payment_id: int, db: Session = Depends(get_db),
                      user: User = Depends(require_permissions("billing:reconcile"))):
    return service.reconcile_payment(db, payment_id, user.id)
