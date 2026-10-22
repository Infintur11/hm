from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.appointment import AppointmentCreate, AppointmentStatusUpdate, AppointmentOut
from app.services.appointment_service import (
    book_appointment,
    get_doctor_queue,
    update_appointment_status,
    get_reception_analytics
)
from app.api.deps import get_current_user, require_permissions
from typing import List, Dict, Any
import datetime

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])

@router.get("/analytics")
def api_get_reception_analytics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time OPD queue velocity, doctor capacity, and receptionist alerts."""
    return get_reception_analytics(db)

@router.post("/", response_model=AppointmentOut)
def api_book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("appointment:book"))
):
    """Books an appointment slot with collision checking and token numbering."""
    return book_appointment(db, data)

@router.get("/doctor-queue", response_model=List[Dict[str, Any]])
def api_get_doctor_queue(
    doctor_id: int,
    date: str = Query(None, description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    """Fetches queue of booked patients for the doctor."""
    if user.role == "DOCTOR" and doctor_id != user.id:
        raise HTTPException(status_code=403, detail="Doctors can view only their own patient queue")
    if user.role not in ("DOCTOR", "RECEPTIONIST", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="This patient queue is not available for your role")
    target_date = date or datetime.date.today().isoformat()
    return get_doctor_queue(db, doctor_id, target_date)

@router.patch("/{appointment_id}/status")
def api_update_appointment_status(
    appointment_id: int,
    data: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("patient:read"))
):
    return update_appointment_status(db, appointment_id, data.status)
