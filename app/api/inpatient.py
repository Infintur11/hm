from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.inpatient import AdmissionCreate, DischargeOrder, IPMOAdminister, IPMOCreate, BedStatusUpdate
from app.services.inpatient_service import (
    get_bed_matrix,
    admit_patient,
    administer_ipmo,
    create_ipmo,
    check_discharge_clearance,
    discharge_patient,
    get_nurse_analytics
)
from app.models.inpatient import Bed, InpatientMedicationOrder, InpatientRecord
from app.models.patient import Patient
from app.api.deps import get_current_user, require_permissions
from typing import List, Dict, Any

router = APIRouter(prefix="/api/inpatient", tags=["Inpatient"])

@router.get("/analytics")
def api_get_nurse_analytics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Real-time bed occupancy rate, IPMO schedule stats, and nursing shift alerts."""
    return get_nurse_analytics(db)

@router.get("/bed-matrix")
def api_get_bed_matrix(db: Session = Depends(get_db), user=Depends(require_permissions("inpatient:manage"))):
    """Returns visual bed board grouped by ward with status chips."""
    return get_bed_matrix(db)

@router.patch("/beds/{bed_id}/status")
def api_update_bed_status(
    bed_id: int,
    data: BedStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("inpatient:manage"))
):
    bed = db.query(Bed).filter(Bed.id == bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    bed.status = data.status
    if data.status == "VACANT":
        bed.current_patient_id = None
    db.commit()
    db.refresh(bed)
    return {"status": "SUCCESS", "bed_number": bed.bed_number, "new_status": bed.status}

@router.get("/active-admission/{bed_id}")
def api_get_active_admission(bed_id: int, db: Session = Depends(get_db), user=Depends(require_permissions("inpatient:manage"))):
    """Returns the active admission record for a given bed."""
    rec = db.query(InpatientRecord).filter(
        InpatientRecord.bed_id == bed_id,
        InpatientRecord.status == "ADMITTED"
    ).order_by(InpatientRecord.admission_date.desc()).first()
    if not rec:
        raise HTTPException(status_code=404, detail="No active admission on this bed")
    patient = db.query(Patient).filter(Patient.id == rec.patient_id).first()
    return {
        "id": rec.id,
        "ip_number": rec.ip_number,
        "patient_id": rec.patient_id,
        "patient_name": patient.full_name if patient else "Patient",
        "patient_mrn": patient.mrn if patient else "-",
        "admission_date": rec.admission_date.strftime("%d-%b-%Y %H:%M"),
        "admission_reason": rec.admission_reason
    }

@router.post("/admit")
def api_admit_patient(
    data: AdmissionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("inpatient:manage"))
):
    """Allocates bed and creates InpatientRecord."""
    record = admit_patient(db, data)
    return {"status": "ADMITTED", "ip_number": record.ip_number, "bed_id": record.bed_id, "inpatient_record_id": record.id}

@router.get("/ipmo-queue")
def api_get_ipmo_queue(db: Session = Depends(get_db), user=Depends(require_permissions("ipmo:administer"))):
    """Nurse medication administration schedule checklist."""
    orders = db.query(InpatientMedicationOrder).filter(
        InpatientMedicationOrder.status == "PENDING"
    ).order_by(InpatientMedicationOrder.created_at.asc()).all()

    queue = []
    for ord in orders:
        patient = db.query(Patient).filter(Patient.id == ord.patient_id).first()
        rec = db.query(InpatientRecord).filter(InpatientRecord.id == ord.inpatient_record_id).first()
        bed = db.query(Bed).filter(Bed.id == rec.bed_id).first() if rec else None
        
        queue.append({
            "id": ord.id,
            "patient_name": patient.full_name if patient else "Patient",
            "mrn": patient.mrn if patient else "-",
            "bed_number": bed.bed_number if bed else "-",
            "ward_name": bed.ward_name if bed else "-",
            "medicine_name": ord.medicine_name,
            "dosage": ord.dosage,
            "frequency": ord.frequency,
            "route": ord.route,
            "scheduled_slot": ord.scheduled_slot,
            "status": ord.status
        })
    return queue

@router.post("/ipmo")
def api_create_ipmo(
    data: IPMOCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("rx:write"))
):
    """Schedules a new medication dose on the inpatient nurse chart."""
    order = create_ipmo(db, data)
    return {"status": "SCHEDULED", "id": order.id, "medicine_name": order.medicine_name}

@router.post("/administer-ipmo")
def api_administer_ipmo(
    data: IPMOAdminister,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("ipmo:administer"))
):
    """Marks medication administered by nurse."""
    ord = administer_ipmo(db, data, user.id)
    return {"status": "ADMINISTERED", "id": ord.id}

@router.get("/clearance/{inpatient_record_id}")
def api_check_clearance(
    inpatient_record_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("inpatient:manage"))
):
    """Evaluates the Discharge Billing Block Invariant before final discharge."""
    return check_discharge_clearance(db, inpatient_record_id)

@router.post("/discharge")
def api_discharge_patient(
    data: DischargeOrder,
    db: Session = Depends(get_db),
    user=Depends(require_permissions("inpatient:manage"))
):
    """Discharges inpatient, enforces invariant, calculates bed charges, and creates bill."""
    return discharge_patient(db, data)

