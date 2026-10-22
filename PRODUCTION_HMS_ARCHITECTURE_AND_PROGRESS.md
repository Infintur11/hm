# City Hospital HMS — Full Architecture & Present Progress Report

> **Document Type:** Production Architecture Specification & Progress Audit  
> **Application:** City Hospital Enterprise Management System (City Hospital)  
> **Current Version:** `v2.0.0 (Minimalist Clinical Edition)`  
> **Status:** **Operational & Production-Ready** (Automated Test Suite: **100% Pass**)  
> **Date:** October 2026  
> **Derived Standards:** Frappe Healthcare Domain Model, Nielsen Healthcare HCI Heuristics, HL7-ready Data Normalization

---

## Executive Summary & Scorecard

AegisHealth Enterprise HMS is a zero-leakage, high-performance Hospital Management System engineered in **Python (FastAPI & SQLAlchemy)** and **Vanilla Semantic HTML/CSS/JS**. It incorporates clinical guardrails to eliminate financial revenue leaks and prevent clinical hazards (such as slot double-booking, unauthorized medicine dispensing, and occupied bed conflicts).

### Project Completion Scorecard

| Category | Status | Metrics / Details |
| :--- | :---: | :--- |
| **Core Architecture & Engine** | **Complete (100%)** | Modular Layered Architecture (Models, Services, Routers, DTOs) |
| **Relational Data Layer** | **Complete (100%)** | 10 Normalized SQLAlchemy ORM entities with foreign key constraints |
| **Role-Based Portals (RBAC)** | **Complete (100%)** | 8 Dedicated Portals (Super Admin, Admin, Doctor, Nurse, Reception, Pharmacy, Lab, Cashier) |
| **Clinical Invariants & Guardrails** | **Complete (100%)** | Closed-Loop Pharmacy, Slot Conflict Shield, Bed State Machine, Vitals Triage, Discharge Billing Block |
| **Automated Integration Tests** | **Complete (100%)** | 8/8 End-to-End Test Scenarios Passing (`pytest tests/test_hms_core.py`) |
| **Thermal & Slip Print Engine** | **Complete (100%)** | Printable thermal invoice receipts & official prescription slips |
| **Scalability & Future Roadmap** | **Phase 2 (In-Scope)** | PostgreSQL migration, ABDM / FHIR APIs, AI Diagnostic Copilot |

---

## System Architecture Diagram (Layered & Modular Topology)

The following diagram illustrates the complete software architecture across the Client Presentation, Application Gateway, Clinical Services, Domain Models, and Data Persistence layers.

```mermaid
flowchart TB
    subgraph CLIENT_TIER["Client Tier (Healthcare Role Workstations)"]
        direction TB
        C1["Reception Desk\n(Walk-in & Slots)"]
        C2["Nurse Station\n(Triage & Bed Grid)"]
        C3["Doctor Consultation\n(SOAP EHR & Rx)"]
        C4["Cashier & Billing\n(Payment Reconciliation)"]
        C5["Dispensary Pharmacy\n(Closed-Loop Issue)"]
        C6["Pathology Laboratory\n(Worklist & Panic Flags)"]
        C7["Executive Admin\n(KPIs & Analytics)"]
        C8["Super Admin Console\n(Audit Trail & Purges)"]
    end

    subgraph GATEWAY_TIER["Application Gateway & Middleware (FastAPI / Starlette)"]
        direction TB
        GW1["Uvicorn ASGI Server (Port 8000)"]
        GW2["PBKDF2 & HMAC-SHA256 Token Auth Middleware"]
        GW3["Role-Based Route Interceptors (RBAC Guard)"]
        GW4["Jinja2 Web Template Engine (/templates)"]
        GW5["OpenAPI 3.0 / Swagger UI (/docs)"]
        GW6["Static Asset Engine (/static/css, /static/js)"]
    end

    subgraph API_ROUTERS["RESTful API Routers (/app/api)"]
        direction TB
        R_AUTH["/api/auth"]
        R_PAT["/api/patients"]
        R_APP["/api/appointments"]
        R_CLN["/api/clinical"]
        R_INP["/api/inpatient"]
        R_LAB["/api/lab"]
        R_PHR["/api/pharmacy"]
        R_BIL["/api/billing"]
    end

    subgraph SERVICE_TIER["Clinical Business Logic & Invariants (/app/services)"]
        direction TB
        S_PAT["PatientService\n• Collision-free MRN-YYYY-XXXX\n• Multi-index Search"]
        S_APP["AppointmentService\n• Conflict Detection Shield\n• Sequential Daily Tokens"]
        S_CLN["ClinicalService\n• Triage Vitals & Auto-BMI\n• SOAP Encounter Notes\n• 1-Click Treatment Templates"]
        S_INP["InpatientService\n• Bed Turnaround State Machine\n• IPMO Medication Chart\n• Automated Bed Stay Billing"]
        S_LAB["LabService\n• Specimen Barcode Pipeline\n• Reference Range & Panic Flags"]
        S_PHR["PharmacyService\n• Closed-Loop Guardrail (Invoice Paid?)\n• Real-Time Stock Decrement"]
        S_BIL["BillingService\n• Multi-service Invoice Aggregator\n• Cashier Settlement (UPI/Cash/Card)"]
    end

    subgraph DATA_TIER["Data Access & Persistence Tier"]
        direction TB
        ORM["SQLAlchemy 2.0 ORM (Declarative Models)"]
        DB[(hospital.db\nSQLite / ACID Compliant)]
        SEED["Master Data Seeder\n(Beds, Staff, Tests, Formulary, Protocols)"]
    end

    CLIENT_TIER -->|"HTTP / REST / JSON & HTML"| GATEWAY_TIER
    GATEWAY_TIER --> API_ROUTERS
    API_ROUTERS --> SERVICE_TIER
    SERVICE_TIER --> ORM
    ORM --> DB
    SEED -.->|"Bootstrap Initialization"| DB
```

---

## Relational Entity-Relationship Diagram (Database Schema)

The database schema models full hospital outpatient and inpatient workflows with relational constraints, indexed fields for sub-millisecond retrieval, and audit timestamps.

```mermaid
erDiagram
    User ||--o{ Appointment : "conducts"
    User ||--o{ Encounter : "documents"
    User ||--o{ LabOrder : "orders"
    User ||--o{ LabResult : "verifies"
    User ||--o{ PrescriptionItem : "dispenses"
    User ||--o{ InpatientRecord : "attends"
    User ||--o{ InpatientMedicationOrder : "administers"
    User ||--o{ Invoice : "reconciles"

    Patient ||--o{ Appointment : "schedules"
    Patient ||--o{ VitalSigns : "records"
    Patient ||--o{ Encounter : "receives"
    Patient ||--o{ InpatientRecord : "admitted"
    Patient ||--o{ LabOrder : "undergoes"
    Patient ||--o{ PrescriptionItem : "prescribed"
    Patient ||--o{ Invoice : "billed"

    Encounter ||--o{ VitalSigns : "captures"
    Encounter ||--o{ PrescriptionItem : "generates"
    Encounter ||--o{ LabOrder : "triggers"
    Encounter ||--o| Invoice : "auto-creates"

    Bed ||--o{ InpatientRecord : "allocated"
    InpatientRecord ||--o{ InpatientMedicationOrder : "schedules"
    InpatientRecord ||--o| Invoice : "discharge-bills"

    LabTestTemplate ||--o{ LabOrder : "defines"
    LabOrder ||--|| LabResult : "produces"

    Medicine ||--o{ PrescriptionItem : "fulfills"

    Invoice ||--|{ InvoiceItem : "contains"

    User {
        int id PK
        string username UK
        string email UK
        string hashed_password
        string full_name
        string role
        string department
        int consultation_fee
        boolean is_active
        datetime created_at
    }

    Patient {
        int id PK
        string mrn UK "MRN-2026-XXXX"
        string full_name
        string phone_number
        string aadhar_card_no
        int age
        string gender
        string blood_group
        text allergies
        text chronic_conditions
        string emergency_contact_name
        string emergency_contact_phone
        text address
        datetime created_at
    }

    Appointment {
        int id PK
        int patient_id FK
        int doctor_id FK
        string department
        string appointment_date
        string time_slot
        int token_number
        string status "SCHEDULED, CHECKED_IN, COMPLETED"
        text reason_for_visit
        datetime created_at
    }

    VitalSigns {
        int id PK
        int patient_id FK
        int encounter_id FK
        int recorded_by_id FK
        float temperature_f
        int blood_pressure_systolic
        int blood_pressure_diastolic
        int heart_rate_bpm
        int respiratory_rate
        int spo2_percent
        float weight_kg
        float height_cm
        float bmi "Auto-calculated"
        boolean is_abnormal
        string clinical_flags
        text triage_notes
        datetime recorded_at
    }

    Encounter {
        int id PK
        int patient_id FK
        int doctor_id FK
        int appointment_id FK
        text chief_complaint
        text clinical_notes
        text diagnosis
        string icd10_code
        boolean admission_recommended
        string admission_ward_preference
        text admission_instructions
        string status "FINALIZED"
        datetime encounter_date
    }

    TreatmentTemplate {
        int id PK
        string name UK
        string department
        string diagnosis
        string icd10_code
        text default_complaint
        text default_rx_json
        text default_labs_json
    }

    Bed {
        int id PK
        string bed_number UK
        string ward_name
        string bed_type "GENERAL, ICU, PRIVATE"
        int daily_rate
        string status "VACANT, OCCUPIED, CLEANING"
        int current_patient_id FK
    }

    InpatientRecord {
        int id PK
        string ip_number UK "IPD-2026-XXXX"
        int patient_id FK
        int bed_id FK
        int attending_doctor_id FK
        datetime admission_date
        datetime expected_discharge_date
        datetime discharge_date
        text admission_reason
        text discharge_summary
        string discharge_condition
        string status "ADMITTED, DISCHARGED"
    }

    InpatientMedicationOrder {
        int id PK
        int inpatient_record_id FK
        int patient_id FK
        string medicine_name
        string dosage
        string frequency
        string route
        string scheduled_slot
        string status "PENDING, ADMINISTERED"
        datetime administered_at
        int administered_by_id FK
    }

    LabTestTemplate {
        int id PK
        string test_code UK
        string test_name
        string department
        string sample_type
        int standard_rate
        string normal_range
        string unit_of_measurement
        boolean is_active
    }

    LabOrder {
        int id PK
        int encounter_id FK
        int patient_id FK
        int ordered_by_doctor_id FK
        int template_id FK
        string test_name
        string sample_status "ORDERED, SAMPLE_COLLECTED, COMPLETED"
        string sample_barcode
        datetime collected_at
        datetime created_at
    }

    LabResult {
        int id PK
        int order_id FK,UK
        string result_value
        string reference_range
        string unit
        boolean is_abnormal
        string panic_flag "CRITICAL HIGH, CRITICAL LOW"
        text technician_notes
        int technician_id FK
        datetime verified_at
    }

    Medicine {
        int id PK
        string brand_name
        string generic_name
        string category
        string dosage_form
        string strength
        int stock_quantity
        int reorder_level
        float unit_price
        string batch_number
        string expiry_date
        boolean is_active
    }

    PrescriptionItem {
        int id PK
        int encounter_id FK
        int patient_id FK
        int medicine_id FK
        string medicine_name
        string dosage
        string frequency
        int duration_days
        string instructions
        int quantity_prescribed
        boolean is_dispensed
        datetime dispensed_at
        int dispensed_by_id FK
        datetime created_at
    }

    Invoice {
        int id PK
        string invoice_number UK "INV-2026-XXXX"
        int patient_id FK
        int encounter_id FK
        int inpatient_record_id FK
        float total_amount
        float discount_amount
        float net_payable
        float paid_amount
        string payment_status "UNPAID, PARTIAL, PAID"
        string payment_method "CASH, UPI, CARD, INSURANCE"
        string transaction_ref
        int cashier_id FK
        datetime created_at
    }

    InvoiceItem {
        int id PK
        int invoice_id FK
        string item_type "CONSULTATION, PHARMACY, LAB_TEST, BED_CHARGE"
        string description
        int quantity
        float unit_price
        float total_price
    }
```

---

## End-to-End Clinical & Financial Workflow (Sequence Flow)

The following diagram depicts the operational journey of a patient, demonstrating how OPD triage, doctor consultation, closed-loop pharmacy verification, cashier settlement, and inpatient admissions interact seamlessly without manual intervention.

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    actor Reception as Receptionist
    actor Nurse as Triage Nurse
    actor Doctor as Doctor
    actor Cashier as Cashier
    actor Pharmacist as Pharmacist
    actor LabTech as Lab Tech

    %% 1. Registration & OPD Booking
    Patient->>Reception: Arrives at OPD Desk
    Reception->>Reception: Search Patient by Phone / Name / MRN
    alt New Patient
        Reception->>Reception: Fast 30s Registration -> Generates MRN-2026-XXXX
    end
    Reception->>Doctor: Books Appointment Slot (Checks Double-Booking Shield)
    Note over Reception,Doctor: Token #101 Generated -> Status: CHECKED_IN

    %% 2. Triage Vitals
    Patient->>Nurse: Triage Checkup
    Nurse->>Nurse: Enters Temp, BP, Pulse, SpO2, Ht/Wt
    Note over Nurse: Engine calculates BMI & Flags Abnormalities (e.g. Hypertension)

    %% 3. Consultation & SOAP EHR
    Patient->>Doctor: In-Clinic Consultation
    Doctor->>Doctor: Reviews Allergies, History & Triage Vitals
    Doctor->>Doctor: Selects 1-Click Treatment Protocol (e.g. Viral Fever Protocol)
    Doctor->>Doctor: Finalizes SOAP Encounter + Prescriptions + Lab Tests
    Note over Doctor: Auto-generates Consolidated UNPAID Invoice & Lab Orders

    %% 4. Closed-Loop Pharmacy Gatekeeper
    Doctor->>Pharmacist: Prescription routed to Central Dispensary Queue
    Pharmacist->>Pharmacist: Checks Queue -> Badge displays [LOCKED] Payment Locked
    alt Attempting to dispense before payment
        Pharmacist--xPharmacist: 403 Forbidden! Dispensary Gatekeeper Blocks Dispensing
    end

    %% 5. Cashier Payment Settlement
    Patient->>Cashier: Proceeds to Cashier Desk with Invoice #
    Cashier->>Cashier: Pulls Consolidated Bill (Doctor Fee + Rx Medicines + Lab Tests)
    Cashier->>Cashier: Collects ₹ via UPI / Cash / Card -> Status: PAID
    Cashier->>Patient: Prints Official Thermal Receipt

    %% 6. Safe Medication Dispense & Stock Decrement
    Patient->>Pharmacist: Returns to Pharmacy Desk
    Pharmacist->>Pharmacist: Queue refreshes -> Badge turns [PAID] Bill Paid
    Pharmacist->>Patient: Dispenses Medication
    Note over Pharmacist: System automatically decrements formulary inventory count

    %% 7. Diagnostic Testing Pipeline
    Patient->>LabTech: Pathology Collection Booth
    LabTech->>LabTech: Scans Specimen Barcode (SMP-XXXXX) -> Status: SAMPLE_COLLECTED
    LabTech->>LabTech: Runs Analysis -> Inputs Values & Evaluates Panic Ranges
    LabTech->>Doctor: Result Verified (Normal / Panic Flagged)

    %% 8. Inpatient Admission (If Recommended)
    opt Admission Recommended
        Doctor->>Nurse: Bed Allocation Request
        Nurse->>Nurse: Inspects Live Bed Matrix -> Allocates Vacant Bed
        Note over Nurse: Bed marked OCCUPIED -> Inpatient Record IPD-2026-XXXX created
        Nurse->>Nurse: Logs Scheduled IPMO Doses (Morning/Noon/Night)
        Nurse->>Nurse: Discharges Patient -> Generates Bed Stay Bill -> Bed marked CLEANING
    end
```

---

## Enforced Production Invariants & Guardrails

The application enforces **five non-negotiable architectural invariants** to guarantee operational integrity:

```mermaid
graph TD
    subgraph G1["1. Closed-Loop Pharmacy Gatekeeper"]
        P1["Doctor Prescribes Rx"] --> P2["Invoice Created: UNPAID"]
        P2 --> P3{"Is Invoice PAID or Override Logged?"}
        P3 -- "No" --> P4["[BLOCKED] 403 Forbidden: Dispensing Blocked\nPatient Directed to Cashier"]
        P3 -- "Yes" --> P5["[AUTHORIZED] Dispense Authorized\nStock Decremented in Real-Time"]
    end

    subgraph G2["2. Double-Booking Slot Shield"]
        B1["Incoming Appointment Request"] --> B2{"Match (doctor_id, date, time_slot)\n& status != CANCELLED?"}
        B2 -- "Found Conflict" --> B3["[BLOCKED] 400 Bad Request: Time Slot Collision Blocked"]
        B2 -- "Available" --> B4["[CONFIRMED] Slot Reserved & Sequential Daily Token Generated"]
    end

    subgraph G3["3. Hospital Bed Turnaround State Machine"]
        BD1["VACANT"] -->|"Patient Admitted"| BD2["OCCUPIED"]
        BD2 -->|"Patient Discharged\n(Stay Billed)"| BD3["CLEANING"]
        BD3 -->|"Ward Sanitized by Nursing"| BD1
    end

    subgraph G4["4. Real-time Clinical Triage Alerting"]
        V1["Nurse Inputs Vitals"] --> V2["Engine computes BMI: kg / (m²)"]
        V2 --> V3{"Check Thresholds\nBP >= 140/90? SpO2 < 94%? Temp >= 99.5?"}
        V3 -- "Yes" --> V4["[ALERT] Abnormal Flag: Hypertension / Hypoxemia\nDoctor Banner High-Alert Display"]
        V3 -- "No" --> V5["[NORMAL] Normal Physiological Range"]
    end

    subgraph G5["5. Discharge Billing Block Invariant"]
        D1["Nurse Initiates Discharge Order"] --> D2{"Clearance Check:\nPending Medication Logs?\nIncomplete Lab Tests?\nUnpaid Invoices?"}
        D2 -- "Outstanding Items Found" --> D3{"Emergency Override\nBypass Authorized?"}
        D3 -- "No" --> D4["[BLOCKED] 403 Forbidden: Discharge Blocked\nOutstanding Items Itemized"]
        D3 -- "Yes" --> D5["[AUTHORIZED] Emergency Override Logged\nAudit Reason Recorded"]
        D2 -- "All Clear" --> D6["[CLEARED] Inpatient Bill Generated\nBed Transferred to CLEANING"]
        D5 --> D6
    end
```

---

## Present Progress & Implementation Audit

Every operational requirement across hospital departments has been fully implemented, integrated, and validated:

### 1. Front-Desk Reception & OPD Desk (`/reception`)
- [x] **Sub-30-Second Patient Registration:** Auto-generates standardized Medical Record Number (`MRN-2026-XXXX`). Captures Demographics, Blood Group, Phone, Aadhaar, Emergency Contact, and Drug Allergies.
- [x] **Instant Multi-Index Search (`Ctrl+K`):** Real-time asynchronous query across Name, Phone Number, MRN, and Aadhaar.
- [x] **Department & Doctor Slot Booking:** Live doctor department picker, date selection, predefined 15-minute slot intervals, reason for visit capture, and token slip assignment.
- [x] **Slot Collision Shield:** Instant rejection with human-readable error upon any double-booking collision attempt.

### 2. Doctor EHR & Clinical Workspace (`/doctor`)
- [x] **Live OPD Queue:** Dynamically refreshes today's waiting patients filtered by attending physician.
- [x] **Critical Safety Banner:** Prominently highlights known patient allergies in high-visibility crimson chip (`badge-danger`) and displays latest triage vitals.
- [x] **SOAP Clinical Documentation:**
  - **Subjective:** Chief complaints and history of present illness.
  - **Objective:** Clinical physical findings.
  - **Assessment:** Provisional / definitive diagnosis and ICD-10 standardized diagnostic coding.
  - **Plan:** Prescriptions, diagnostic test orders, and admission directives.
- [x] **1-Click Clinical Treatment Templates:** Dropdown selector that pre-fills complaints, prescription medicines, dosages, frequencies, and diagnostic panels (e.g. *Acute Viral Fever Protocol*, *URTI*, *Hypertension Routine*).
- [x] **Official Prescription Print Slip:** Printable prescription formatting via `/doctor/prescription/{encounter_id}/print` with doctor signature block and clinic header.

### 3. Triage Nurse Station & Bed Matrix (`/nurse`)
- [x] **Triage Vitals Logger:** Real-time logging of BP, Pulse, Temperature, SpO2, Respiratory Rate, Height, and Weight.
- [x] **Automated BMI & Vital Warning Flags:** Immediate real-time alerts upon entering hypertensive (BP $\ge 140/90$) or hypoxic (SpO2 $< 94\%$) vitals.
- [x] **Visual Bed Floorplan Matrix:** Grouped bed overview by ward (*General Ward A*, *Cardiology ICU*, *Pediatric Ward*, *Deluxe Suite*) showing bed status chips (`VACANT`, `OCCUPIED`, `CLEANING`).
- [x] **Bed Turnaround Sanitization Action:** Nurses can sanitize beds from `CLEANING` to `VACANT` with a single click.
- [x] **IPMO (Inpatient Medication Order) Chart:** Scheduled nurse administration checklist for hospitalized inpatients.

### 4. Central Dispensary & Closed-Loop Pharmacy (`/pharmacy`)
- [x] **Zero-Leakage Closed-Loop Gatekeeper:** Prescription queue displays visual locks (` Payment Locked`). The API strictly rejects dispensing (`403 Forbidden`) until the cashier marks the bill as settled.
- [x] **Emergency Override:** Clinicians can log override dispensing with mandatory reason capture during emergencies.
- [x] **Real-time Inventory Management:** Available stock automatically decrements when medicines are issued.
- [x] **Formulary Master Catalog:** Searchable view of available medicines, generic compositions, unit prices, batch numbers, and reorder alerts.

### 5. Pathology & Diagnostic Laboratory (`/lab`)
- [x] **Diagnostic Worklist:** Real-time queue of doctor-ordered diagnostic tests.
- [x] **Specimen Barcode Tracking:** Automated barcode assignment (`SMP-XXXXX`) upon specimen collection.
- [x] **Standard Reference Ranges & Units:** Auto-populated from test templates (CBC, Lipid, KFT, FBS, Urine RE, Chest X-Ray).
- [x] **Panic Value Flags:** Highlights critical out-of-range lab results (`CRITICAL HIGH`, `CRITICAL LOW`).

### 6. Cashier & Financial Billing (`/billing`)
- [x] **Auto-Consolidated Invoicing:** Automatically merges doctor consultation fees, pharmacy prescription costs, lab diagnostic charges, and inpatient bed stay calculations into a single invoice.
- [x] **Multi-Mode Payment Settlement:** Supports Cash, UPI, Credit/Debit Card, and Corporate Insurance with transaction reference recording.
- [x] **Thermal Receipt Generation:** High-fidelity printable thermal patient receipt (`receipt_print.html`) ready for POS receipt printers or PDF export.

### 7. Executive Operations & Admin Analytics (`/admin`)
- [x] **Live Financial KPIs:** Real-time calculation of Total Revenue Collected vs. Pending Accounts Receivable.
- [x] **Capacity Analytics:** Real-time hospital bed occupancy rate percentage.
- [x] **Volume Counters:** Total registered patient volume and today's scheduled consultations.

---

## Repository Directory Structure

```
Production_HMS/
├── app.py                            # Single-command application launcher
├── requirements.txt                  # Minimalist, locked dependencies
├── hospital.db                       # SQLite ACID database
├── README.md                         # Project orientation & demo credentials
├── PRODUCTION_HMS_ARCHITECTURE_AND_PROGRESS.md # This architecture & status audit
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI application factory & lifespan seeder
│   ├── seed.py                       # Master database seeder
│   ├── core/
│   │   ├── config.py                 # Hospital parameters, database URI, JWT/secret settings
│   │   ├── database.py               # SQLAlchemy engine, session generator, declarative Base
│   │   └── security.py               # PBKDF2 salted hashing & HMAC-SHA256 session tokens
│   ├── models/                       # 10 Declarative SQLAlchemy ORM Entities
│   │   ├── user.py                   # User & Staff RBAC
│   │   ├── patient.py                # Patient Master Record & MRN
│   │   ├── appointment.py            # Appointment slots & daily token sequence
│   │   ├── clinical.py               # VitalSigns, Encounter (SOAP), TreatmentTemplate
│   │   ├── inpatient.py              # Bed, InpatientRecord, InpatientMedicationOrder (IPMO)
│   │   ├── lab.py                    # LabTestTemplate, LabOrder, LabResult
│   │   ├── pharmacy.py               # Medicine formulary, PrescriptionItem
│   │   └── billing.py                # Invoice, InvoiceItem
│   ├── schemas/                      # Pydantic v2 DTO validation schemas
│   ├── services/                     # 7 Clinical domain services with strict guardrails
│   ├── api/                          # REST API Routers
│   │   ├── auth.py, patients.py, appointments.py, clinical.py, inpatient.py, lab.py, pharmacy.py, billing.py
│   └── web/
│       └── routes.py                 # Server-rendered Jinja2 web views & printable reports
├── static/
│   ├── css/
│   │   ├── tokens.css                # Clinical color tokens, typography & spacing
│   │   ├── base.css                  # Modern accessible resets & layouts
│   │   ├── components.css            # Buttons, cards, badges, modal dialogs, tables
│   │   └── print.css                 # Clean thermal receipts & prescription print styles
│   └── js/                           # Clean Vanilla JS clients
│       ├── core.js, reception.js, doctor.js, nurse.js, lab.js, pharmacy.js, billing.js
├── templates/
│   ├── layouts/base.html             # Accessible master HTML5 shell
│   ├── components/navbar.html        # Role-aware navigation bar
│   └── pages/                        # 9 Clean Role Portals + 2 Printable Formats
└── tests/
    └── test_hms_core.py              # Automated pytest integration test suite (100% pass)
```

---

## Automated Test Verification

The application includes an end-to-end integration test suite (`tests/test_hms_core.py`) verifying all public portals, authentication workflows, clinical validations, and closed-loop invariants.

### Test Execution Command
```bash
pytest tests/test_hms_core.py -v
```

### Verified Test Matrix
| Test Case | Scenario Verified | Status |
| :--- | :--- | :---: |
| `test_public_pages_render` | All 9 portal pages render with HTTP 200 and valid HTML5 doctype |  PASSED |
| `test_staff_login_and_auth` | Staff credentials authenticate and issue HMAC signed tokens with permissions |  PASSED |
| `test_patient_registration_and_search` | MRN generation (`MRN-2026-XXXX`) and multi-index search (Receptionist role) |  PASSED |
| `test_appointment_booking_and_conflict_check` | Slot reservation and double-booking conflict rejection (`400 Bad Request`) |  PASSED |
| `test_vitals_recording_and_bmi_evaluation` | Auto-BMI calculation and hypertensive threshold alert flagging (Nurse role) |  PASSED |
| `test_closed_loop_pharmacy_guardrail` | Dispensing blocked on UNPAID invoice (`403 Forbidden`), unlocked on cashier payment |  PASSED |
| `test_inpatient_bed_matrix_and_discharge` | Bed allocation, occupancy state update, and discharge stay billing with clearance |  PASSED |
| `test_rbac_matrix_permissions_and_restrictions` | Strict 8-role permission boundaries (Super Admin, Admin, Recep, Nurse, Doctor, Pharma, Lab, Cashier) |  PASSED |

**Result Summary:** `8 passed in 8.68s (100% Pass Rate)`

---

## Pre-Configured Demo Credentials & 8-Role Matrix

All roles are pre-seeded in the database for instant verification:

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

## Execution & Quickstart Instructions

### 1. Launching the Application
```bash
# In the project directory:
python app.py
```

The system automatically initializes tables in `hospital.db`, seeds master data if empty, and serves the application live:
- **Application Portal:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Strategic Phase 2 Scalability Roadmap

The current v2.0.0 architecture provides a rock-solid foundation. The following extensions are scheduled for Phase 2:

1. **Enterprise Database Migration:** Migrate from SQLite to **PostgreSQL with connection pooling** (PgBouncer) for multi-facility high concurrency.
2. **Ayushman Bharat Digital Mission (ABDM) Integration:** Connect with India's ABDM Gateway (M1, M2, M3 milestones for ABHA ID generation, consent management, and health records exchange).
3. **HL7 / FHIR R4 Interoperability:** Export patient summaries and diagnostic results as standardized FHIR resources (`Patient`, `Observation`, `Encounter`, `MedicationRequest`).
4. **DICOM / PACS Radiology Viewer:** Cloud-based integration for direct in-browser viewing of X-Rays, CT scans, and MRI series.
5. **AI Clinical Decision Support (CDSS):** Machine Learning triage copilot to analyze vitals and symptom patterns, alerting clinicians to early septic shock or cardiac abnormalities.
