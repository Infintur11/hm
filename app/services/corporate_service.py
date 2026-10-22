from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.corporate import CorporateClient
from app.models.billing import Invoice
from fastapi import HTTPException
from typing import List, Dict, Any, Optional
import datetime

def get_corporate_clients(db: Session, active_only: bool = False) -> List[Dict[str, Any]]:
    query = db.query(CorporateClient)
    if active_only:
        query = query.filter(CorporateClient.is_active == True)
    clients = query.order_by(CorporateClient.name.asc()).all()
    
    results = []
    for c in clients:
        limit = float(c.monthly_credit_limit or 0.0)
        # Dynamically tally billed claim sum directly from invoices table
        inv_claim_sum = db.query(func.coalesce(func.sum(Invoice.corporate_claim_amount), 0.0)).filter(Invoice.corporate_client_id == c.id).scalar() or 0.0
        inv_count = db.query(func.count(Invoice.id)).filter(Invoice.corporate_client_id == c.id).scalar() or 0
        
        utilized = float(inv_claim_sum) if inv_count > 0 else float(c.current_utilized_credit or 0.0)
        available = max(0.0, limit - utilized)
        pct = round((utilized / limit) * 100, 1) if limit > 0 else 0.0
        
        results.append({
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "category": c.category,
            "monthly_credit_limit": limit,
            "current_utilized_credit": utilized,
            "available_credit": available,
            "utilization_percentage": pct,
            "contact_person": c.contact_person,
            "contact_phone": c.contact_phone,
            "contact_email": c.contact_email,
            "notes": c.notes,
            "is_active": c.is_active,
            "invoice_count": inv_count,
            "created_at": c.created_at.strftime("%d-%b-%Y")
        })
    return results

def get_corporate_client_detail(db: Session, client_id: int) -> Dict[str, Any]:
    from app.models.patient import Patient
    c = db.query(CorporateClient).filter(CorporateClient.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Corporate client not found")
    
    limit = float(c.monthly_credit_limit or 0.0)
    inv_claim_sum = db.query(func.coalesce(func.sum(Invoice.corporate_claim_amount), 0.0)).filter(Invoice.corporate_client_id == c.id).scalar() or 0.0
    invoices = db.query(Invoice).filter(Invoice.corporate_client_id == c.id).order_by(Invoice.created_at.desc()).all()
    
    utilized = float(inv_claim_sum) if len(invoices) > 0 else float(c.current_utilized_credit or 0.0)
    available = max(0.0, limit - utilized)
    pct = round((utilized / limit) * 100, 1) if limit > 0 else 0.0

    inv_details = []
    for inv in invoices:
        patient = db.query(Patient).filter(Patient.id == inv.patient_id).first()
        inv_details.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "patient_name": patient.full_name if patient else "Patient",
            "patient_mrn": patient.mrn if patient else "-",
            "policy_id": inv.corporate_policy_id or "-",
            "net_payable": float(inv.net_payable or 0.0),
            "claim_amount": float(inv.corporate_claim_amount or inv.net_payable or 0.0),
            "claim_status": inv.corporate_claim_status or "SETTLED",
            "payment_status": inv.payment_status,
            "created_at": inv.created_at.strftime("%d-%b-%Y %H:%M") if inv.created_at else "-"
        })

    return {
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "category": c.category,
        "monthly_credit_limit": limit,
        "current_utilized_credit": utilized,
        "available_credit": available,
        "utilization_percentage": pct,
        "contact_person": c.contact_person,
        "contact_phone": c.contact_phone,
        "contact_email": c.contact_email,
        "notes": c.notes,
        "is_active": c.is_active,
        "created_at": c.created_at.strftime("%d-%b-%Y"),
        "invoices": inv_details
    }

def create_corporate_client(db: Session, data) -> Dict[str, Any]:
    existing = db.query(CorporateClient).filter(CorporateClient.code == data.code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Corporate partner with code '{data.code}' already exists")
    
    client = CorporateClient(
        name=data.name.strip(),
        code=data.code.strip().upper(),
        category=data.category,
        monthly_credit_limit=float(data.monthly_credit_limit),
        current_utilized_credit=0.0,
        contact_person=data.contact_person,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        notes=data.notes,
        is_active=True
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"status": "SUCCESS", "id": client.id, "name": client.name, "monthly_credit_limit": client.monthly_credit_limit}

def update_corporate_client(db: Session, client_id: int, data) -> Dict[str, Any]:
    client = db.query(CorporateClient).filter(CorporateClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Corporate partner not found")
    
    if data.name is not None:
        client.name = data.name.strip()
    if data.category is not None:
        client.category = data.category
    if data.monthly_credit_limit is not None:
        client.monthly_credit_limit = float(data.monthly_credit_limit)
    if data.contact_person is not None:
        client.contact_person = data.contact_person
    if data.contact_phone is not None:
        client.contact_phone = data.contact_phone
    if data.contact_email is not None:
        client.contact_email = data.contact_email
    if data.notes is not None:
        client.notes = data.notes
    if data.is_active is not None:
        client.is_active = data.is_active
        
    db.commit()
    db.refresh(client)
    return {"status": "SUCCESS", "id": client.id, "monthly_credit_limit": client.monthly_credit_limit}

def update_credit_limit(db: Session, client_id: int, new_limit: float, notes: Optional[str] = None) -> Dict[str, Any]:
    client = db.query(CorporateClient).filter(CorporateClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Corporate partner not found")
    
    old_limit = client.monthly_credit_limit
    client.monthly_credit_limit = float(new_limit)
    if notes:
        existing_notes = client.notes or ""
        timestamp = datetime.datetime.utcnow().strftime("%d-%b-%Y %H:%M")
        client.notes = f"{existing_notes}\n[{timestamp}] Limit adjusted from Rs.{old_limit} to Rs.{new_limit}: {notes}".strip()
        
    db.commit()
    db.refresh(client)
    return {
        "status": "SUCCESS",
        "id": client.id,
        "name": client.name,
        "previous_limit": old_limit,
        "new_limit": client.monthly_credit_limit
    }

def get_corporate_summary(db: Session) -> Dict[str, Any]:
    clients = db.query(CorporateClient).filter(CorporateClient.is_active == True).all()
    total_limit = sum(float(c.monthly_credit_limit or 0.0) for c in clients)
    
    total_utilized = 0.0
    for c in clients:
        billed_sum = db.query(func.coalesce(func.sum(Invoice.corporate_claim_amount), 0.0)).filter(Invoice.corporate_client_id == c.id).scalar() or 0.0
        inv_cnt = db.query(func.count(Invoice.id)).filter(Invoice.corporate_client_id == c.id).scalar() or 0
        total_utilized += float(billed_sum) if inv_cnt > 0 else float(c.current_utilized_credit or 0.0)
        
    total_available = max(0.0, total_limit - total_utilized)
    avg_util = round((total_utilized / total_limit * 100), 1) if total_limit > 0 else 0.0

    return {
        "total_active_partners": len(clients),
        "total_credit_pool": total_limit,
        "total_utilized": total_utilized,
        "total_available": total_available,
        "overall_utilization_pct": avg_util
    }
