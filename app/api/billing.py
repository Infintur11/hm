from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.schemas.billing import PaymentCollectRequest
from app.services.billing_service import (
    get_invoices,
    get_invoice_detail,
    collect_payment,
    get_cashier_analytics
)
from app.models.billing import Invoice, InvoiceItem
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.inpatient import Bed
from app.api.deps import get_current_user, require_permissions
from app.schemas.commission import PaymentRefundCreate
from app.services.commission_service import pending_payments, payment_history, reconcile_payment, refund_payment
from app.models.commission import Payment
from typing import List, Dict, Any, Optional
import datetime

router = APIRouter(prefix="/api/billing", tags=["Billing & Cashier"])

@router.get("/cashier-analytics")
def api_get_cashier_analytics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time cashier settlement KPIs, AR balance, and pharmacy payment lock alerts."""
    return get_cashier_analytics(db)

@router.get("/invoices")
def api_get_invoices(
    status: str = Query(None, description="Filter by UNPAID, PARTIAL, or PAID"),
    patient_id: Optional[int] = Query(None, description="Filter by patient ID"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return get_invoices(db, status, patient_id)

@router.get("/invoices/{invoice_id}")
def api_get_invoice_detail(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Detailed invoice receipt breakdown for printing."""
    return get_invoice_detail(db, invoice_id)

@router.post("/collect")
def api_collect_payment(
    data: PaymentCollectRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("billing:reconcile"))
):
    """Collects cashier payment and unlocks closed-loop pharmacy dispensing."""
    return collect_payment(db, data, user.id)

@router.get("/payments/pending-reconciliation")
def api_pending_payment_reconciliation(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), user=Depends(require_permissions("billing:reconcile"))
):
    return pending_payments(db, page, page_size)

@router.get("/payments/history")
def api_payment_history(
    period: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), user=Depends(require_permissions("commission:manage"))
):
    return payment_history(db, period, page, page_size)

@router.post("/payments/{payment_id}/reconcile")
def api_reconcile_payment(
    payment_id: int, db: Session = Depends(get_db), user=Depends(require_permissions("billing:reconcile"))
):
    return reconcile_payment(db, payment_id, user.id)

@router.post("/payments/{payment_id}/refund")
def api_refund_payment(
    payment_id: int, data: PaymentRefundCreate, db: Session = Depends(get_db),
    user=Depends(require_permissions("commission:manage"))
):
    return refund_payment(db, payment_id, data.amount, data.reason, data.reference, data.idempotency_key, user.id)

@router.get("/analytics/kpis")
def api_get_financial_kpis(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time hospital KPIs for Executive & Admin Dashboard."""
    total_revenue = db.query(func.sum(Invoice.paid_amount)).scalar() or 0.0
    pending_revenue = db.query(func.sum(Invoice.net_payable - Invoice.paid_amount)).filter(Invoice.payment_status != "PAID").scalar() or 0.0
    total_patients = db.query(Patient).count()
    
    # Bed Occupancy
    total_beds = db.query(Bed).count()
    occupied_beds = db.query(Bed).filter(Bed.status == "OCCUPIED").count()
    occupancy_pct = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0
    
    # Today's OPD appointments
    today_str = datetime.date.today().isoformat()
    today_appts = db.query(Appointment).filter(Appointment.appointment_date == today_str).count()

    return {
        "total_revenue": total_revenue,
        "pending_revenue": pending_revenue,
        "total_patients": total_patients,
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "occupancy_rate_pct": occupancy_pct,
        "today_appointments": today_appts
    }
