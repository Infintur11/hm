from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.clinical import Encounter
from app.models.pharmacy import PrescriptionItem, Medicine
from app.models.billing import Invoice, InvoiceItem
from app.models.lab import LabOrder
import datetime

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)

def get_optional_user(request: Request, db: Session) -> User:
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub") or payload.get("user_id")
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()

ROLE_HOME_REDIRECTS = {
    "SUPER_ADMIN": "/admin",
    "ADMIN": "/admin",
    "DOCTOR": "/doctor",
    "NURSE": "/nurse",
    "RECEPTIONIST": "/reception",
    "PHARMACIST": "/pharmacy",
    "LAB_TECH": "/lab",
    "LAB": "/lab",
    "CASHIER": "/billing",
}

ROLE_PAGE_ACCESS = {
    "/admin": ["SUPER_ADMIN", "ADMIN"],
    "/reception": ["SUPER_ADMIN", "ADMIN", "RECEPTIONIST"],
    "/doctor": ["SUPER_ADMIN", "ADMIN", "DOCTOR"],
    "/nurse": ["SUPER_ADMIN", "NURSE"],
    "/lab": ["SUPER_ADMIN", "ADMIN", "DOCTOR", "LAB_TECH", "LAB"],
    "/pharmacy": ["SUPER_ADMIN", "ADMIN", "PHARMACIST"],
    "/billing": ["SUPER_ADMIN", "ADMIN", "CASHIER"],
}

@router.get("/", response_class=HTMLResponse)
def page_home(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user and user.role != "SUPER_ADMIN":
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    role_home = ROLE_HOME_REDIRECTS.get(user.role, "/") if user else "/"
    return templates.TemplateResponse(request=request, name="pages/index.html", context={
        "request": request,
        "user": user,
        "role_home": role_home,
        "settings": settings,
        "title": "Clinical Portal"
    })

@router.get("/login", response_class=HTMLResponse)
def page_login(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/doctor"), status_code=303)
    return templates.TemplateResponse(request=request, name="pages/login.html", context={
        "request": request,
        "settings": settings,
        "title": "Hospital Staff Login"
    })

@router.get("/reception", response_class=HTMLResponse)
def page_reception(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/reception"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    doctors = db.query(User).filter(User.role == "DOCTOR", User.is_active == True).all()
    today_str = datetime.date.today().isoformat()
    return templates.TemplateResponse(request=request, name="pages/reception.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/reception"),
        "doctors": doctors,
        "today": today_str,
        "settings": settings,
        "title": "Reception & OPD Desk"
    })

@router.get("/doctor", response_class=HTMLResponse)
def page_doctor(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/doctor"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    doctors = db.query(User).filter(User.role == "DOCTOR", User.is_active == True).all()
    today_str = datetime.date.today().isoformat()
    return templates.TemplateResponse(request=request, name="pages/doctor.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/doctor"),
        "doctors": doctors,
        "today": today_str,
        "settings": settings,
        "title": "Doctor EHR Consultation"
    })

@router.get("/nurse", response_class=HTMLResponse)
def page_nurse(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/nurse"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    return templates.TemplateResponse(request=request, name="pages/nurse.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/nurse"),
        "settings": settings,
        "title": "Nurse Station & Inpatient Wards"
    })

@router.get("/lab", response_class=HTMLResponse)
def page_lab(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/lab"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    return templates.TemplateResponse(request=request, name="pages/lab.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/lab"),
        "settings": settings,
        "title": "Laboratory & Pathology"
    })

@router.get("/pharmacy", response_class=HTMLResponse)
def page_pharmacy(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/pharmacy"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    return templates.TemplateResponse(request=request, name="pages/pharmacy.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/pharmacy"),
        "settings": settings,
        "title": "Closed-Loop Pharmacy"
    })

@router.get("/billing", response_class=HTMLResponse)
def page_billing(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/billing"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    return templates.TemplateResponse(request=request, name="pages/billing.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/billing"),
        "settings": settings,
        "title": "Cashier Desk & Billing"
    })

@router.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ROLE_PAGE_ACCESS["/admin"]:
        return RedirectResponse(ROLE_HOME_REDIRECTS.get(user.role, "/login"), status_code=303)
    doctors = db.query(User).filter(User.role == "DOCTOR", User.is_active == True).order_by(User.full_name).all()
    return templates.TemplateResponse(request=request, name="pages/admin.html", context={
        "request": request,
        "user": user,
        "role_home": ROLE_HOME_REDIRECTS.get(user.role, "/admin"),
        "settings": settings,
        "doctors": doctors,
        "title": "Hospital Management & KPIs"
    })

@router.get("/receipt/{invoice_id}", response_class=HTMLResponse)
def page_print_receipt(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    patient = db.query(Patient).filter(Patient.id == inv.patient_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).all()
    cashier = db.query(User).filter(User.id == inv.cashier_id).first() if inv.cashier_id else None

    # Resolve Attending Doctor
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
    if not doctor and inv.patient_id and patient and getattr(patient, "referred_by_doctor_id", None):
        doctor = db.query(User).filter(User.id == patient.referred_by_doctor_id).first()

    return templates.TemplateResponse(request=request, name="pages/receipt_print.html", context={
        "request": request,
        "invoice": inv,
        "patient": patient,
        "items": items,
        "cashier": cashier,
        "doctor": doctor,
        "settings": settings,
        "title": f"Official Receipt - {inv.invoice_number}"
    })


@router.get("/rx/{encounter_id}", response_class=HTMLResponse)
def page_print_rx(encounter_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    enc = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    patient = db.query(Patient).filter(Patient.id == enc.patient_id).first()
    doctor = db.query(User).filter(User.id == enc.doctor_id).first()
    rx_items = db.query(PrescriptionItem).filter(PrescriptionItem.encounter_id == enc.id).all()
    labs = db.query(LabOrder).filter(LabOrder.encounter_id == enc.id).all()

    return templates.TemplateResponse(request=request, name="pages/rx_print.html", context={
        "request": request,
        "encounter": enc,
        "patient": patient,
        "doctor": doctor,
        "prescriptions": rx_items,
        "labs": labs,
        "settings": settings,
        "title": f"Clinical Prescription - {patient.full_name if patient else ''}"
    })
