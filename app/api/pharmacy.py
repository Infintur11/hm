from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.pharmacy import DispenseRequest, RestockRequest
from app.services.pharmacy_service import (
    get_dispensary_queue,
    dispense_prescription_item,
    get_pharmacy_analytics,
    restock_medicine
)
from app.models.pharmacy import Medicine
from app.api.deps import get_current_user, require_permissions
from typing import List, Dict, Any

router = APIRouter(prefix="/api/pharmacy", tags=["Pharmacy"])

@router.get("/analytics")
def api_get_pharmacy_analytics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time Formulary Inventory KPIs, Category Mix, Reorder Thresholds & Stockout Forecast."""
    return get_pharmacy_analytics(db)

@router.post("/restock")
def api_restock_medicine(
    data: RestockRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("pharmacy:inventory"))
):
    """Restocks formulary medicine with batch tracking and immediately updates KPIs."""
    item = restock_medicine(db, data.medicine_id, data.quantity_to_add, data.batch_number)
    return {
        "status": "RESTOCKED",
        "id": item.id,
        "brand_name": item.brand_name,
        "new_stock": item.stock_quantity,
        "batch_number": item.batch_number
    }

@router.get("/queue")
def api_get_pharmacy_queue(db: Session = Depends(get_db), user=Depends(require_permissions("pharmacy:dispense"))):
    """Fetches real-time prescription queue with Closed-Loop payment verification."""
    return get_dispensary_queue(db)

@router.post("/dispense")
def api_dispense_item(
    data: DispenseRequest,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("pharmacy:dispense"))
):
    """
    Closed-Loop Dispensing:
    Validates payment before dispensing; decrements inventory.
    """
    item = dispense_prescription_item(db, data, user.id)
    return {"status": "DISPENSED", "id": item.id, "medicine_name": item.medicine_name}

@router.get("/medicines")
def api_get_medicines(db: Session = Depends(get_db), user=Depends(require_permissions("pharmacy:inventory"))):
    meds = db.query(Medicine).filter(Medicine.is_active == True).order_by(Medicine.brand_name.asc()).all()
    return [
        {
            "id": m.id,
            "brand_name": m.brand_name,
            "generic_name": m.generic_name,
            "category": m.category,
            "dosage_form": m.dosage_form,
            "strength": m.strength,
            "stock_quantity": m.stock_quantity,
            "reorder_level": m.reorder_level,
            "unit_price": m.unit_price,
            "batch_number": m.batch_number or "N/A",
            "expiry_date": m.expiry_date or "N/A",
            "is_low_stock": m.stock_quantity <= m.reorder_level
        } for m in meds
    ]
