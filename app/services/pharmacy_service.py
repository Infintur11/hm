from sqlalchemy.orm import Session
from app.models.pharmacy import PrescriptionItem, Medicine
from app.models.billing import Invoice
from app.models.patient import Patient
from app.schemas.pharmacy import DispenseRequest
from fastapi import HTTPException
from typing import List, Dict, Any
import datetime

def get_dispensary_queue(db: Session) -> List[Dict[str, Any]]:
    """
    Returns active prescriptions with Closed-Loop payment verification status.
    """
    items = db.query(PrescriptionItem).order_by(PrescriptionItem.created_at.desc()).limit(50).all()
    queue = []
    for item in items:
        patient = db.query(Patient).filter(Patient.id == item.patient_id).first()
        invoice = db.query(Invoice).filter(Invoice.encounter_id == item.encounter_id).first()
        
        is_paid = (invoice.payment_status == "PAID") if invoice else False
        med = db.query(Medicine).filter(Medicine.id == item.medicine_id).first() if item.medicine_id else None

        queue.append({
            "id": item.id,
            "encounter_id": item.encounter_id,
            "patient_id": item.patient_id,
            "patient_name": patient.full_name if patient else "Patient",
            "patient_phone": patient.phone_number if patient else "",
            "medicine_name": item.medicine_name,
            "dosage": item.dosage,
            "frequency": item.frequency,
            "duration_days": item.duration_days,
            "instructions": item.instructions,
            "quantity_prescribed": item.quantity_prescribed,
            "current_stock": med.stock_quantity if med else 0,
            "is_dispensed": item.is_dispensed,
            "is_paid": is_paid,
            "invoice_number": invoice.invoice_number if invoice else "No Invoice",
            "created_at": item.created_at.strftime("%d-%b %H:%M")
        })
    return queue

def dispense_prescription_item(db: Session, data: DispenseRequest, pharmacist_id: int) -> PrescriptionItem:
    """
    CLOSED-LOOP PHARMACY GUARDRAIL:
    Medicines can ONLY be dispensed if the linked invoice is PAID or an emergency override is recorded.
    """
    item = db.query(PrescriptionItem).filter(PrescriptionItem.id == data.prescription_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Prescription item not found")
        
    if item.is_dispensed:
        raise HTTPException(status_code=400, detail="Item has already been dispensed.")

    invoice = db.query(Invoice).filter(Invoice.encounter_id == item.encounter_id).first()
    is_paid = (invoice.payment_status == "PAID") if invoice else False

    if not is_paid and not data.override_reason:
        raise HTTPException(
            status_code=403,
            detail=f"Closed-Loop Guardrail: Cannot dispense {item.medicine_name}. Invoice {invoice.invoice_number if invoice else ''} is UNPAID. Direct patient to Cashier desk."
        )

    # Deduct stock
    if item.medicine_id:
        med = db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
        if med:
            if med.stock_quantity < item.quantity_prescribed:
                raise HTTPException(status_code=400, detail=f"Insufficient inventory. Only {med.stock_quantity} available.")
            med.stock_quantity -= item.quantity_prescribed

    item.is_dispensed = True
    item.dispensed_at = datetime.datetime.utcnow()
    item.dispensed_by_id = pharmacist_id

    db.commit()
    db.refresh(item)
    return item

def restock_medicine(db: Session, medicine_id: int, quantity: int, batch_number: str = None) -> Medicine:
    """Restocks a formulary medicine and updates inventory quantity."""
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Restock quantity must be greater than zero.")
        
    med.stock_quantity += quantity
    if batch_number:
        med.batch_number = batch_number
        
    db.commit()
    db.refresh(med)
    return med

def get_pharmacy_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes real-time inventory KPIs, category distribution,
    stock-vs-reorder thresholds, runout velocity forecast, and critical alerts.
    """
    medicines = db.query(Medicine).filter(Medicine.is_active == True).order_by(Medicine.brand_name.asc()).all()
    
    # Baseline prescription stats
    total_rx = db.query(PrescriptionItem).count()
    dispensed_rx = db.query(PrescriptionItem).filter(PrescriptionItem.is_dispensed == True).count()
    pending_rx = total_rx - dispensed_rx
    clearance_pct = round((dispensed_rx / total_rx * 100), 1) if total_rx > 0 else 100.0

    # Stock metrics
    total_skus = len(medicines)
    total_units = sum(m.stock_quantity for m in medicines)
    total_value = round(sum(m.stock_quantity * m.unit_price for m in medicines), 2)
    low_stock_meds = [m for m in medicines if m.stock_quantity <= m.reorder_level]
    out_of_stock_meds = [m for m in medicines if m.stock_quantity == 0]

    # Category distribution for Pie/Doughnut Chart
    cat_stats: Dict[str, Dict[str, Any]] = {}
    for m in medicines:
        cat = m.category.strip()
        if cat not in cat_stats:
            cat_stats[cat] = {"category": cat, "skus": 0, "units": 0, "value": 0.0}
        cat_stats[cat]["skus"] += 1
        cat_stats[cat]["units"] += m.stock_quantity
        cat_stats[cat]["value"] += round(m.stock_quantity * m.unit_price, 2)

    categories_list = list(cat_stats.values())
    categories_list.sort(key=lambda x: x["value"], reverse=True)

    # Actual consumption velocity from prescription items
    from sqlalchemy import func
    rx_usage = db.query(
        PrescriptionItem.medicine_id,
        func.sum(PrescriptionItem.quantity_prescribed).label("total_qty")
    ).group_by(PrescriptionItem.medicine_id).all()
    usage_map = {r[0]: (r[1] or 0) for r in rx_usage}

    # Stock-vs-Reorder comparison and Stockout Forecasting
    stock_comparison = []
    forecast_items = []
    alerts = []
    critical_runout_count = 0

    now = datetime.datetime.utcnow()

    # Category baseline daily consumption fallback rates for realistic clinical forecasting
    baseline_burn_rates = {
        "Antipyretic / Analgesic": 8.0,
        "Antibiotic": 5.0,
        "Antacid / PPI": 6.0,
        "Cardiovascular / Antihypertensive": 4.0,
        "Antidiabetic": 5.0,
        "Antidiabetic / Injectable": 2.5,
        "Emergency / Critical Care": 2.0,
        "IV Fluids": 6.0,
        "Respiratory": 3.0,
        "Cough Syrup": 4.0
    }

    for m in medicines:
        # Determine actual or baseline daily burn rate
        historic_qty = usage_map.get(m.id, 0)
        default_burn = baseline_burn_rates.get(m.category, 3.0)
        daily_burn = max(round(historic_qty / 3.0, 1) if historic_qty > 0 else default_burn, 0.5)

        days_left = round(m.stock_quantity / daily_burn, 1) if daily_burn > 0 else 999.0
        
        # Determine status
        if m.stock_quantity == 0:
            status = "OUT_OF_STOCK"
            urgency = "STOCKOUT"
            critical_runout_count += 1
            alerts.append({
                "type": "CRITICAL_STOCKOUT",
                "severity": "danger",
                "medicine_id": m.id,
                "medicine_name": m.brand_name,
                "message": f"CRITICAL: {m.brand_name} is completely OUT OF STOCK! Immediate procurement required.",
                "action": "Restock Immediately"
            })
        elif m.stock_quantity <= m.reorder_level:
            status = "CRITICAL"
            urgency = "URGENT"
            critical_runout_count += 1
            alerts.append({
                "type": "LOW_STOCK",
                "severity": "danger",
                "medicine_id": m.id,
                "medicine_name": m.brand_name,
                "message": f"Low Stock Warning: {m.brand_name} ({m.stock_quantity} left) is at or below reorder threshold ({m.reorder_level}). Projected runout in ~{int(days_left)} days.",
                "action": "Replenish Stock"
            })
        elif days_left <= 15:
            status = "WARNING"
            urgency = "REORDER_SOON"
            alerts.append({
                "type": "RUNOUT_RISK",
                "severity": "warning",
                "medicine_id": m.id,
                "medicine_name": m.brand_name,
                "message": f"Stockout Forecast: {m.brand_name} will deplete in ~{int(days_left)} days based on current burn velocity.",
                "action": "Order Batch"
            })
        else:
            status = "OPTIMAL"
            urgency = "HEALTHY"

        runout_dt = (now + datetime.timedelta(days=int(days_left))).strftime("%d-%b-%Y") if days_left < 365 else "Safe (>1 yr)"
        reorder_suggested = max(m.reorder_level * 3 - m.stock_quantity, m.reorder_level)

        item_data = {
            "id": m.id,
            "brand_name": m.brand_name,
            "generic_name": m.generic_name,
            "category": m.category,
            "stock_quantity": m.stock_quantity,
            "reorder_level": m.reorder_level,
            "unit_price": m.unit_price,
            "dosage_form": m.dosage_form,
            "health_status": status,
            "daily_burn_velocity": daily_burn,
            "days_remaining": days_left,
            "runout_date": runout_dt,
            "urgency": urgency,
            "suggested_reorder_qty": reorder_suggested,
            "batch_number": m.batch_number or "N/A",
            "expiry_date": m.expiry_date or "N/A"
        }
        stock_comparison.append(item_data)
        forecast_items.append(item_data)

    # Sort forecast items so most urgent appears first
    forecast_items.sort(key=lambda x: (x["days_remaining"], x["stock_quantity"]))

    return {
        "kpis": {
            "total_skus": total_skus,
            "total_units": total_units,
            "total_inventory_value": total_value,
            "low_stock_count": len(low_stock_meds),
            "out_of_stock_count": len(out_of_stock_meds),
            "prescriptions_total": total_rx,
            "prescriptions_dispensed": dispensed_rx,
            "prescriptions_pending": pending_rx,
            "clearance_rate_pct": clearance_pct,
            "critical_runout_count": critical_runout_count
        },
        "categories": categories_list,
        "stock_comparison": stock_comparison,
        "forecast": forecast_items,
        "alerts": alerts
    }
