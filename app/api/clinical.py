from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.clinical import VitalsCreate, VitalsOut, EncounterCreate
from app.services.clinical_service import (
    record_vitals,
    get_latest_vitals,
    get_recent_vitals,
    finalize_encounter,
    get_doctor_analytics
)
from app.models.clinical import TreatmentTemplate
from app.api.deps import get_current_user, require_permissions
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/clinical", tags=["Clinical"])

@router.get("/analytics")
def api_get_doctor_analytics(
    doctor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time clinical queue KPIs, waiting room anomaly alerts & allergy flags."""
    if user.role == "DOCTOR":
        doc_id = user.id
    elif user.role in ("SUPER_ADMIN", "ADMIN"):
        doc_id = doctor_id
    else:
        raise HTTPException(status_code=403, detail="This clinical dashboard is not available for your role")
    return get_doctor_analytics(db, doc_id)

@router.post("/vitals", response_model=VitalsOut)
def api_record_vitals(
    data: VitalsCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("clinical:triage"))
):
    """Logs patient vitals with auto-calculated BMI and abnormal range alerts."""
    return record_vitals(db, data, user.id)

@router.get("/vitals/recent")
def api_get_recent_vitals(
    limit: int = 30,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    """Fetches recent recorded triage vitals audit logs with timestamps."""
    return get_recent_vitals(db, limit=limit)

@router.get("/vitals/latest/{patient_id}")
def api_get_latest_vitals(
    patient_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    return get_latest_vitals(db, patient_id)

@router.post("/encounter")
def api_finalize_encounter(
    data: EncounterCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("clinical:encounter", "rx:write"))
):
    """Submits doctor SOAP encounter, generates Rx, Lab Orders & Cashier Invoice."""
    if user.role == "DOCTOR":
        # Never trust a doctor ID supplied by the browser; bind the encounter to
        # the signed-in clinician even if an old page submits a stale value.
        data.doctor_id = user.id
    elif not data.doctor_id:
        data.doctor_id = user.id
    return finalize_encounter(db, data)

@router.get("/templates")
def api_get_treatment_templates(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    templates = db.query(TreatmentTemplate).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "department": t.department,
            "diagnosis": t.diagnosis,
            "icd10_code": t.icd10_code,
            "default_complaint": t.default_complaint,
            "default_rx": t.default_rx_json,
            "default_labs": t.default_labs_json
        } for t in templates
    ]
