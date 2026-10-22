# City Hospital Enterprise HMS — Minimalist Clinical Edition

> Production-Grade, Enterprise Hospital Management System built with **Python (FastAPI & SQLAlchemy)**, **Modular HTML/CSS/JS (Vanilla & Clean Tokens)**, and **SQLite**.  
> Derived directly from clinical domain synthesis of Frappe Healthcare, engineered with strict zero-leakage invariants and **Nielsen's Healthcare HCI Principles**.

---

## Instant Quickstart (Single Command)

```bash
cd production_hms
python app.py
```

The application automatically initializes the SQLite database (`hospital.db`), seeds master data (beds, doctors, nurses, medicines, lab test templates, and patients), and serves the application live on:

- **Web Application Portal:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive OpenAPI (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc Docs:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Pre-Seeded Demo Credentials & Role Workstation Matrix

| Role Portal | Username | Password | Target System Capabilities | Allowed Back-End Permissions | Present UI Workstation Customizations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Super Admin** (`super_admin`) | `superadmin` | `super123` | System Administration, Security Audit Logs, Master Data Purges | `*` (All Privileges), `system:purge`, `user:delete` | Full master configuration control panel visible with audit trail and system purge triggers. |
| **Hospital Admin** (`admin`) | `admin` | `admin123` | Analytics Engine, Staff User Creation & Operational Logs | `user:read`, `user:create`, `analytics:view` | **Hidden Clinical Screens:** All clinical diagnostic tabs and pharmacy logs are stripped out. Destructive delete operations are entirely hidden. |
| **Receptionist** (`receptionist`) | `recep.riya` | `recep123` | Demographics & Token Generator | `patient:create`, `patient:read`, `appointment:book` | **Masked EHR History Data:** Medical diagnoses, clinical symptoms, case histories, and lab results are hidden from view. |
| **Nurse** (`nurse`) | `nurse.mary` | `nurse123` | Triage Inputs & Bed Matrix | `clinical:triage`, `inpatient:manage`, `ipmo:administer` | **Read-only Rx Fields:** Can view medication listings for treatment delivery but cannot add, change, or sign off prescriptions. |
| **Doctor** (`doctor`) | `dr.sharma` / `dr.anita` | `doc123` | Full SOAP Workspace & Rx | `patient:read`, `clinical:encounter`, `rx:write`, `lab:order` | **Read-only Invoice States:** Can see if an invoice is pending or paid, but cannot alter fees, apply medical discounts, or manually settle balances. |
| **Pharmacist** (`pharmacist`) | `pharma.kumar` | `pharma123` | Dispensary Pipeline View | `pharmacy:dispense`, `pharmacy:inventory` | **Invoice Balance Warnings:** High-visibility status icons lock the interface unless a clean zero balance is returned from the billing module. |
| **Lab Tech** (`lab`) | `lab.john` | `lab123` | Specimen Worklist Matrix | `lab:view_worklist`, `lab:write_result` | **Reference Boundaries Alerts:** Displays inline notifications highlighting critical out-of-bounds physiological values and panic thresholds. |
| **Cashier** (`cashier`) | `cashier.karan` | `cash123` | Payment Reconciliation & Settlements | `billing:reconcile`, `invoice:print` | **Masked Clinical Data:** Clinical medical documentation files are hidden from lookups. |

---

## Clean Modular Architecture

```
production_hms/
├── app.py                       # Single command application runner: python app.py
├── requirements.txt             # Lean dependencies (fastapi, uvicorn, sqlalchemy, pydantic, jinja2)
├── hospital.db                  # Auto-created SQLite database with initial seed data
├── app/
│   ├── core/                    # Infrastructure configs
│   │   ├── config.py            # Hospital metadata, database URL, token secrets
│   │   ├── database.py          # SQLAlchemy engine, session maker, declarative base
│   │   └── security.py          # Salted PBKDF2 hashing & tamper-proof session tokens
│   ├── models/                  # Declarative SQLAlchemy ORM Entities
│   │   ├── user.py              # User RBAC (ADMIN, DOCTOR, NURSE, RECEPTIONIST, PHARMACIST, LAB_TECH)
│   │   ├── patient.py           # Patient (MRN, Name, Phone, Aadhaar, Age, Gender, BloodGroup, Allergies)
│   │   ├── appointment.py       # Appointments, token numbers, slot collision locks
│   │   ├── clinical.py          # VitalSigns (BMI calc, abnormal flags), Encounter (SOAP), TreatmentTemplate
│   │   ├── inpatient.py         # Beds (Ward, Type, Status), InpatientRecord, IPMO Medication Orders
│   │   ├── lab.py               # LabTestTemplate, LabOrder, LabResult with panic values
│   │   ├── pharmacy.py          # Medicine formulary, PrescriptionItem with closed-loop lock
│   │   └── billing.py           # Invoice, itemized line items, payment capture
│   ├── schemas/                 # Pydantic v2 Request/Response DTOs
│   ├── services/                # Business logic & clinical guardrails
│   │   ├── patient_service.py   # Collision-proof sequential MRN generation & multi-parameter search
│   │   ├── appointment_service.py # Overlap checks & queue routing
│   │   ├── clinical_service.py  # Vitals evaluation, SOAP encounter & auto-billing
│   │   ├── inpatient_service.py # Bed allocation, IPMO administration & discharge clearance
│   │   ├── lab_service.py       # Sample barcoding & reference range verification
│   │   ├── pharmacy_service.py  # Closed-Loop Pharmacy Gatekeeper
│   │   └── billing_service.py   # Consolidated billing & cashier reconciliation
│   ├── api/                     # RESTful JSON Routers
│   │   ├── auth.py, patients.py, appointments.py, clinical.py, inpatient.py, lab.py, pharmacy.py, billing.py
│   │   ├── web/
│   │   └── routes.py            # Server-rendered Jinja2 web views & printable templates
│   ├── seed.py                  # Initial master data seeder
│   └── main.py                  # FastAPI application bootstrap & lifespan
├── static/
│   ├── css/
│   │   ├── tokens.css           # Clean clinical tokens (slate blue, emerald, amber, crimson)
│   │   ├── base.css             # Accessible resets, typography, responsive layout
│   │   ├── components.css       # Cards, badges, buttons, tables, bed chips, modals, toasts
│   │   └── print.css            # Official thermal receipt & prescription print formats
│   └── js/
│       ├── core.js              # Unified fetch client, modal manager, keyboard shortcuts (Ctrl+K)
│       ├── reception.js         # Instant search & 30-sec registration
│       ├── doctor.js            # SOAP consultation notes & 1-click treatment protocols
│       ├── nurse.js             # Real-time vitals feedback & bed matrix toggles
│       ├── lab.js               # Specimen collection barcode & result verification
│       ├── pharmacy.js          # Closed-loop payment lock queue & inventory decrement
│       └── billing.js           # Line-item invoice builder & payment collection
├── templates/
│   ├── layouts/base.html        # Accessible HTML5 base shell
│   ├── components/navbar.html   # Role-aware responsive navigation
│   └── pages/                   # Dedicated minimalist portals for each hospital role
└── tests/
    └── test_hms_core.py         # Pytest integration suite (100% passing)
```

---

## Enforced Production Invariants & Guardrails

1. **Closed-Loop Pharmacy Dispensing Guardrail:**
   - Prescriptions are locked in the pharmacy queue with a visual warning: `[LOCKED] Payment Locked`.
   - The dispensing endpoint raises `403 Forbidden` if an attempt is made to dispense an unpaid prescription. Once cashier payment is collected, the badge turns green (`[PAID] Bill Paid`) and dispensing succeeds, automatically decrementing formulary stock.
2. **Double-Booking Slot Shield:**
   - Appointment slot booking verifies: `doctor_id`, `date`, and `time_slot`. Conflicting overlapping bookings are rejected with a clear human-readable error.
3. **Bed Conflict & Turnaround State Machine:**
   - Hospital beds follow a strict state progression: `VACANT` $\rightarrow$ `OCCUPIED` (upon patient admission) $\rightarrow$ `CLEANING` (upon discharge) $\rightarrow$ `VACANT` (once sanitized by nursing staff).
4. **Clinical Threshold Auto-Flagging:**
   - The vitals engine calculates BMI automatically and flags out-of-range parameters (e.g. Systolic BP $\ge 140$ as *Hypertension*, SpO2 $< 94\%$ as *Hypoxemia*).
5. **Discharge Billing Block Invariant:**
   - Patient discharge is blocked with `403 Forbidden` while there are open, unadministered medication chart logs (IPMO), incomplete diagnostic tests, or outstanding unpaid patient bills. An Emergency Clinical Override bypass is provided with mandatory clinical justification recording for complete audit immutability.

## Doctor Commission & Settlement

The HMS now includes reconciled-payment commission accrual, effective-dated rules, doctor statements, finance review, audited refunds/adjustments, and payout recording. Finance must configure a commission rule before accrual starts. Receipts recorded on an invoice remain ineligible until reconciled; historical aggregate invoice balances are not automatically credited.

See [COMMISSION_SETTLEMENT.md](COMMISSION_SETTLEMENT.md) for the repository audit, allocation defaults, permissions, endpoints, data-preservation approach, and test coverage.

Use `HMS_TIMEZONE` to configure reporting periods (defaults to `Asia/Kolkata`). Use `HMS_DATABASE_URL` to direct the app or tests to a different SQLite database.
The app runner starts without a file watcher by default; set `HMS_RELOAD=true` for development reloads. `HMS_HOST` can override the bind address.

---

## Running Tests

To run the automated integration test suite:

```bash
pytest -q
```

The test suite uses an isolated temporary SQLite database and does not clear `hospital.db`.
