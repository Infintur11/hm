from sqlalchemy.orm import Session
from app.models.billing import Invoice, InvoiceItem
from app.models.patient import Patient
from app.models.user import User
from app.schemas.billing import PaymentCollectRequest
from fastapi import HTTPException
from typing import List, Dict, Any
import datetime

from app.models.clinical import Encounter
from app.models.appointment import Appointment
import json

def _resolve_attending_doctor(db: Session, inv: Invoice) -> tuple:
    """Helper to resolve (doctor_id, doctor_name) for any invoice."""
    doctor = None
    if inv.attending_doctor_id:
        doctor = db.query(User).filter(User.id == inv.attending_doctor_id).first()
    if not doctor and inv.encounter_id:
        enc = db.query(Encounter).filter(Encounter.id == inv.encounter_id).first()
        if enc and enc.doctor_id:
            doctor = db.query(User).filter(User.id == enc.doctor_id).first()
    if not doctor and inv.patient_id:
        appt = db.query(Appointment).filter(Appointment.patient_id == inv.patient_id).order_by(Appointment.id.desc()).first()
        if appt and appt.doctor_id:
            doctor = db.query(User).filter(User.id == appt.doctor_id).first()
    if not doctor and inv.patient_id:
        pat = db.query(Patient).filter(Patient.id == inv.patient_id).first()
        if pat and getattr(pat, "referred_by_doctor_id", None):
            doctor = db.query(User).filter(User.id == pat.referred_by_doctor_id).first()
    
    if doctor:
        if not inv.attending_doctor_id:
            inv.attending_doctor_id = doctor.id
        doc_name = doctor.full_name if doctor.full_name.startswith("Dr.") else f"Dr. {doctor.full_name}"
        if doctor.department:
            doc_name += f" ({doctor.department})"
        return doctor.id, doc_name
    return None, "Consulting Physician"

def get_invoices(db: Session, status_filter: str = None, patient_id: int = None) -> List[Dict[str, Any]]:
    query = db.query(Invoice).order_by(Invoice.created_at.desc())
    if status_filter:
        query = query.filter(Invoice.payment_status == status_filter)
    if patient_id:
        query = query.filter(Invoice.patient_id == patient_id)
        
    invoices = query.all()
    results = []
    for inv in invoices:
        patient = db.query(Patient).filter(Patient.id == inv.patient_id).first()
        doc_id, doc_name = _resolve_attending_doctor(db, inv)
        results.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "patient_id": inv.patient_id,
            "patient_name": patient.full_name if patient else "Patient",
            "patient_phone": patient.phone_number if patient else "",
            "patient_mrn": patient.mrn if patient else "",
            "attending_doctor_id": doc_id,
            "attending_doctor_name": doc_name,
            "total_amount": inv.total_amount,
            "discount_amount": inv.discount_amount,
            "net_payable": inv.net_payable,
            "paid_amount": inv.paid_amount,
            "payment_status": inv.payment_status,
            "payment_method": inv.payment_method,
            "bank_name": inv.bank_name,
            "cheque_number": inv.cheque_number,
            "upi_id": inv.upi_id,
            "billing_type": getattr(inv, "billing_type", "WALK_IN") or "WALK_IN",
            "corporate_client_id": getattr(inv, "corporate_client_id", None),
            "corporate_policy_id": getattr(inv, "corporate_policy_id", None),
            "corporate_claim_amount": getattr(inv, "corporate_claim_amount", 0.0) or 0.0,
            "corporate_claim_status": getattr(inv, "corporate_claim_status", "NOT_APPLICABLE") or "NOT_APPLICABLE",
            "cash_denominations_json": inv.cash_denominations_json,
            "split_payments_json": inv.split_payments_json,
            "created_at": inv.created_at.strftime("%d-%b-%Y %H:%M")
        })
    return results

def get_invoice_detail(db: Session, invoice_id: int) -> Dict[str, Any]:
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    patient = db.query(Patient).filter(Patient.id == inv.patient_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).all()
    doc_id, doc_name = _resolve_attending_doctor(db, inv)
    
    corp_name = None
    if getattr(inv, "corporate_client_id", None):
        from app.models.corporate import CorporateClient
        corp = db.query(CorporateClient).filter(CorporateClient.id == inv.corporate_client_id).first()
        if corp:
            corp_name = corp.name

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "patient": {
            "name": patient.full_name if patient else "Patient",
            "mrn": patient.mrn if patient else "-",
            "phone": patient.phone_number if patient else "-",
            "age_gender": f"{patient.age} / {patient.gender}" if patient else "-"
        },
        "attending_doctor_id": doc_id,
        "attending_doctor_name": doc_name,
        "billing_type": getattr(inv, "billing_type", "WALK_IN") or "WALK_IN",
        "corporate_client_id": getattr(inv, "corporate_client_id", None),
        "corporate_client_name": corp_name,
        "corporate_policy_id": getattr(inv, "corporate_policy_id", None),
        "corporate_claim_amount": getattr(inv, "corporate_claim_amount", 0.0) or 0.0,
        "corporate_claim_status": getattr(inv, "corporate_claim_status", "NOT_APPLICABLE") or "NOT_APPLICABLE",
        "total_amount": inv.total_amount,
        "discount_amount": inv.discount_amount,
        "net_payable": inv.net_payable,
        "paid_amount": inv.paid_amount,
        "payment_status": inv.payment_status,
        "payment_method": inv.payment_method,
        "transaction_ref": inv.transaction_ref,
        "bank_name": inv.bank_name,
        "cheque_number": inv.cheque_number,
        "upi_id": inv.upi_id,
        "cash_denominations_json": inv.cash_denominations_json,
        "split_payments_json": inv.split_payments_json,
        "created_at": inv.created_at.strftime("%d-%b-%Y %H:%M"),
        "items": [
            {
                "id": itm.id,
                "type": itm.item_type,
                "description": itm.description,
                "quantity": itm.quantity,
                "unit_price": itm.unit_price,
                "total_price": itm.total_price
            } for itm in items
        ]
    }


def collect_payment(db: Session, data: PaymentCollectRequest, cashier_id: int) -> Dict[str, Any]:
    from app.services.commission_service import collect_payment as record_receipt
    return record_receipt(db, data, cashier_id)

def get_cashier_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes cashier settlement KPIs, payment method mix,
    accounts receivable balances, and financial clearance alerts.
    """
    from sqlalchemy import func
    from app.models.pharmacy import PrescriptionItem

    invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).all()
    total_invoices = len(invoices)
    paid_invoices = [i for i in invoices if i.payment_status == "PAID"]
    unpaid_invoices = [i for i in invoices if i.payment_status != "PAID"]

    total_collected = sum(i.paid_amount for i in invoices)
    total_receivable = sum((i.net_payable - i.paid_amount) for i in unpaid_invoices)

    # Payment methods breakdown
    methods: Dict[str, Dict[str, Any]] = {}
    for i in paid_invoices:
        m = i.payment_method or "CASH"
        if m not in methods:
            methods[m] = {"method": m, "count": 0, "total_amount": 0.0}
        methods[m]["count"] += 1
        methods[m]["total_amount"] += round(i.paid_amount, 2)

    # Alerts for cashier
    alerts = []
    
    # 1. Unpaid invoices that have active prescriptions waiting at dispensary
    for inv in unpaid_invoices[:5]:
        p = db.query(Patient).filter(Patient.id == inv.patient_id).first()
        p_name = p.full_name if p else "Patient"
        # Check if there are prescription items for this encounter
        if inv.encounter_id:
            prescriptions = db.query(PrescriptionItem).filter(
                PrescriptionItem.encounter_id == inv.encounter_id,
                PrescriptionItem.is_dispensed == False
            ).all()
            if prescriptions:
                alerts.append({
                    "type": "PHARMACY_PAYMENT_LOCK",
                    "severity": "danger",
                    "invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "message": f"Closed-Loop Payment Lock: Invoice {inv.invoice_number} for {p_name} (₹{inv.net_payable:.2f}) is UNPAID, blocking medication dispensing for {len(prescriptions)} prescribed item(s).",
                    "action": "Collect Payment"
                })
            else:
                alerts.append({
                    "type": "UNPAID_INVOICE",
                    "severity": "warning",
                    "invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "message": f"Settlement Pending: Invoice {inv.invoice_number} for {p_name} has outstanding balance of ₹{inv.net_payable - inv.paid_amount:.2f}.",
                    "action": "Settle Bill"
                })

    return {
        "kpis": {
            "total_collected": round(total_collected, 2),
            "total_receivable_unpaid": round(total_receivable, 2),
            "paid_invoices_count": len(paid_invoices),
            "unpaid_invoices_count": len(unpaid_invoices),
            "total_invoices": total_invoices
        },
        "payment_methods": list(methods.values()),
        "alerts": alerts
    }
