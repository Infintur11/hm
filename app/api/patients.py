from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientOut
from app.services.patient_service import register_patient, search_patients, get_patient_by_id
from app.api.deps import get_current_user, require_permissions
from typing import List

router = APIRouter(prefix="/api/patients", tags=["Patients"])

@router.get("/", response_model=List[PatientOut])
def api_list_patients(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    """Returns recent registered patients."""
    return db.query(Patient).order_by(Patient.created_at.desc()).limit(limit).all()

@router.post("/", response_model=PatientOut)
def api_register_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:create"))
):
    """Registers a new patient and generates unique MRN."""
    return register_patient(db, data)

@router.get("/search", response_model=List[PatientOut])
def api_search_patients(
    q: str = Query("", description="Search term for name, phone, aadhar, or MRN"),
    limit: int = 20,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    """Fast live search for patients."""
    return search_patients(db, q, limit)

@router.get("/{patient_id}", response_model=PatientOut)
def api_get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    patient = get_patient_by_id(db, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
