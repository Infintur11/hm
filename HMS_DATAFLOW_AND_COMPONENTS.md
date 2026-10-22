# City Hospital Enterprise HMS — Full Dataflow & Component Specification

> **Document Version:** 2.0.0  
> **System Name:** City Hospital Enterprise Management System (City Hospital HMS)  
> **Architecture Pattern:** Modular Layered Monolith (FastAPI + SQLAlchemy + Semantic Vanilla Web Components)  
> **Database:** SQLite (`hospital.db` with ACID `BEGIN IMMEDIATE` financial transaction serialization)  
> **Verification Status:** Operational & Production-Ready (15/15 Pytest Test Suites Passing)

---

## 1. Global System Architecture & Component Topology

The system is structured into five distinct operational tiers designed to enforce clinical safety invariants, eliminate financial revenue leakage, and deliver sub-millisecond local latency.

```mermaid
flowchart TB
    subgraph CLIENT_TIER["1. Client Tier (Role-Specific Workstations)"]
        direction TB
        C1["Reception Desk\n(/reception)"]
        C2["Nurse Station\n(/nurse)"]
        C3["Doctor Consultation\n(/doctor)"]
        C4["Pathology Lab\n(/lab)"]
        C5["Closed-Loop Pharmacy\n(/pharmacy)"]
        C6["Cashier & Billing\n(/billing)"]
        C7["Hospital Admin\n(/admin)"]
        C8["Super Admin\n(/admin)"]
    end

    subgraph GATEWAY_TIER["2. Gateway & Application Middleware"]
        direction TB
        GW1["Uvicorn ASGI Server (Port 8000)"]
        GW2["FastAPI Lifespan (DB Seeder & Engine Init)"]
        GW3["Authentication & Session Interceptor (PBKDF2 / HMAC)"]
        GW4["Role-Based Route Interceptors (RBAC Guard)"]
        GW5["Jinja2 SSR Template Engine (/templates)"]
        GW6["Static Asset Delivery (/static)"]
    end

    subgraph API_TIER["3. RESTful API Routers (/app/api)"]
        direction TB
        R_AUTH["/api/auth"]
        R_PAT["/api/patients"]
        R_APP["/api/appointments"]
        R_CLN["/api/clinical"]
        R_LAB["/api/lab"]
        R_PHR["/api/pharmacy"]
        R_INP["/api/inpatient"]
        R_BIL["/api/billing"]
        R_COM["/api/commissions"]
    end

    subgraph SERVICE_TIER["4. Clinical & Financial Service Engine (/app/services)"]
        direction TB
        S_PAT["PatientService\n(MRN Generator & Search)"]
        S_APP["AppointmentService\n(Slot Conflict Shield & Token Counter)"]
        S_CLN["ClinicalService\n(Vitals Engine & SOAP Consultation)"]
        S_LAB["LabService\n(Barcode Engine & Panic Flags)"]
        S_PHR["PharmacyService\n(Closed-Loop Payment Gatekeeper)"]
        S_INP["InpatientService\n(Bed State Machine & Discharge Block)"]
        S_BIL["BillingService\n(Invoice Aggregator & Receipts)"]
        S_COM["CommissionService\n(Reconciliation, Accrual & Payout)"]
    end

    subgraph DATA_TIER["5. Persistence & Relational Models (/app/models)"]
        direction TB
        ORM["SQLAlchemy 2.0 Declarative ORM"]
        M_CORE["Core: User, Patient, Appointment, VitalSigns, Encounter"]
        M_CLIN["Clinical: Bed, InpatientRecord, IPMO, LabOrder, LabResult, Medicine, PrescriptionItem"]
        M_FIN["Financial: Invoice, InvoiceItem, Payment, CommissionRule, CommissionLedgerEntry, SettlementRequest, Payout"]
        DB[("hospital.db (SQLite)")]
    end

    CLIENT_TIER -->|"HTTP / REST / Form Data"| GATEWAY_TIER
    GATEWAY_TIER --> API_TIER
    API_TIER --> SERVICE_TIER
    SERVICE_TIER --> ORM
    ORM --> M_CORE & M_CLIN & M_FIN
    M_CORE & M_CLIN & M_FIN --> DB
```

---

## 2. End-to-End Dataflows

### Flow 1: Patient Registration & Multi-Parameter Search
The gateway to the hospital workflow. Every patient receives a collision-proof sequential Medical Record Number (MRN).

```mermaid
sequenceDiagram
    autonumber
    actor Receptionist as Front Desk Receptionist
    participant UI as Reception Workstation (/reception)
    participant API as /api/patients
    participant Svc as PatientService
    participant DB as SQLite (hospital.db)

    Receptionist->>UI: Enter Demographics (Name, Phone, Aadhaar, Age, Gender, Allergies)
    UI->>API: POST /api/patients (PatientCreate DTO)
    API->>Svc: register_patient(db, data)
    Svc->>DB: Query current count: COUNT(Patient)
    Svc->>Svc: Generate MRN: f"MRN-{year}-{count+1:04d}"
    Svc->>DB: INSERT INTO patients (...)
    DB-->>Svc: Persisted Patient Record
    Svc-->>API: Patient ORM Entity
    API-->>UI: 200 OK + PatientOut (id, mrn, full_name, phone, ...)
    UI-->>Receptionist: Displays Green Toast + Auto-selects Patient for Appointment Booking
```

- **Desired Output:**
  - Database: New row in `patients` table with unique `mrn` (e.g. `MRN-2026-0005`).
  - Response: HTTP `200 OK` returning `{ id, mrn, full_name, phone_number, age, gender, blood_group, allergies, ... }`.
  - UI State: Clears registration form, notifies operator, populates patient lookup for instant appointment scheduling.

---

### Flow 2: Appointment Scheduling & Slot Conflict Guardrail
Guarantees zero double-booking per doctor time slot and issues sequential daily queue tokens.

```mermaid
sequenceDiagram
    autonumber
    actor Receptionist as Front Desk
    participant UI as Reception Workstation
    participant API as /api/appointments
    participant Svc as AppointmentService
    participant DB as SQLite (hospital.db)

    Receptionist->>UI: Select Doctor, Date, Time Slot, Patient ID
    UI->>API: POST /api/appointments (AppointmentCreate)
    API->>Svc: book_appointment(db, data)
    Svc->>DB: Verify Doctor exists & Patient exists
    Svc->>DB: Check slot conflict: doctor_id + appointment_date + time_slot (status != CANCELLED)
    alt Slot is already booked
        Svc-->>API: raise HTTPException(400, "Time slot is already booked")
        API-->>UI: 400 Bad Request
        UI-->>Receptionist: Alert Banner: Slot unavailable
    else Slot is free
        Svc->>DB: Count daily tokens for (doctor_id, date)
        Svc->>Svc: token_number = daily_count + 1
        Svc->>DB: INSERT INTO appointments (status='SCHEDULED', token_number=...)
        DB-->>Svc: Persisted Appointment
        Svc-->>API: Appointment Record
        API-->>UI: 200 OK + AppointmentOut
        UI-->>Receptionist: Token badge generated, added to Doctor's Live Queue
    end
```

- **Desired Output:**
  - Conflict Case: HTTP `400 Bad Request` with clear message: `"Time slot 10:00 - 10:15 is already booked for Dr. Sharma on 2026-10-21."`
  - Success Case: HTTP `200 OK` with unique `token_number` (1, 2, 3...) per doctor-day, `status="SCHEDULED"`.

---

### Flow 3: Nursing Triage & Physiological Vitals Evaluation
Computes Body Mass Index (BMI) automatically, evaluates threshold limits, and sets clinical anomaly flags.

```mermaid
sequenceDiagram
    autonumber
    actor Nurse as Triage Nurse
    participant UI as Nurse Station (/nurse)
    participant API as /api/clinical/vitals
    participant Svc as ClinicalService
    participant DB as SQLite (hospital.db)

    Nurse->>UI: Input BP (Systolic/Diastolic), Temp, Pulse, SpO2, Height, Weight
    UI->>API: POST /api/clinical/vitals (VitalsCreate)
    API->>Svc: record_vitals(db, data, nurse_id)
    Svc->>Svc: Calculate BMI: weight / (height/100)^2
    Svc->>Svc: Evaluate Clinical Rules:
    Note over Svc: Systolic >= 140 or Diastolic >= 90 -> "Hypertension"<br/>Systolic <= 90 -> "Hypotension"<br/>Temp >= 99.5F -> "Pyrexia (Fever)"<br/>Heart Rate > 100 -> "Tachycardia"<br/>SpO2 < 94% -> "Hypoxemia (Low SpO2)"
    Svc->>DB: INSERT INTO vital_signs (bmi, is_abnormal, clinical_flags, ...)
    DB-->>Svc: Persisted Vitals Record
    Svc-->>API: VitalSigns Entity
    API-->>UI: 200 OK + JSON
    UI-->>Nurse: Live Vitals Chip with Red/Amber warning badges if abnormal
```

- **Desired Output:**
  - Database: New record in `vital_signs` with `is_abnormal: bool`, `bmi: float`, `clinical_flags: "Hypertension, Hypoxemia"`.
  - UI State: Instant visual indicator on doctor's queue and triage log alerting clinical staff to patient instability.

---

### Flow 4: Doctor SOAP Consultation, Orders & Consolidated Invoice Generation
The clinical core. Simultaneously captures SOAP documentation, prescribes medications, orders lab diagnostics, updates appointment queue, and synthesizes the consolidated cashier invoice.

```mermaid
sequenceDiagram
    autonumber
    actor Doctor as Attending Doctor
    participant UI as Doctor Workstation (/doctor)
    participant API as /api/clinical/encounters
    participant Svc as ClinicalService
    participant DB as SQLite (hospital.db)

    Doctor->>UI: Fill SOAP (Subjective, Objective, Assessment, Plan, ICD-10, Prescriptions, Lab Tests)
    Doctor->>UI: Click "Finalize Consultation & Generate Rx"
    UI->>API: POST /api/clinical/encounters (EncounterCreate)
    API->>Svc: create_encounter(db, data)
    Svc->>DB: INSERT INTO encounters (status='FINALIZED')
    
    rect rgb(240, 248, 255)
        Note over Svc,DB: 1. Prescriptions & Pharmacy Line Items
        loop For each medication
            Svc->>DB: INSERT INTO prescription_items (is_dispensed=False)
            Svc->>Svc: Append to invoice_items (type='PHARMACY', rate=med.unit_price)
        end
    end

    rect rgb(255, 245, 238)
        Note over Svc,DB: 2. Laboratory Investigations & Lab Line Items
        loop For each test template
            Svc->>DB: INSERT INTO lab_orders (sample_status='ORDERED', sample_barcode='SMP-XXXXX')
            Svc->>Svc: Append to invoice_items (type='LAB_TEST', rate=template.standard_rate)
        end
    end

    rect rgb(240, 255, 240)
        Note over Svc,DB: 3. Consultation Fee & Consolidated Cashier Invoice
        Svc->>Svc: Append Consultation Line Item (rate=doctor.consultation_fee)
        Svc->>DB: INSERT INTO invoices (invoice_number, total_amount, paid_amount=0, payment_status='UNPAID')
        Svc->>DB: INSERT INTO invoice_items (...) for each line
        Svc->>DB: UPDATE appointments SET status='COMPLETED' WHERE id=appointment_id
    end

    Svc-->>API: Return { encounter_id, invoice_id, invoice_number, total_payable }
    API-->>UI: 200 OK + Summary Payload
    UI-->>Doctor: Opens Printable Rx Slip (/rx/{encounter_id}) & updates queue
```

- **Desired Output:**
  - Encounter: Finalized clinical record with diagnostic code.
  - Prescriptions: `prescription_items` created with `is_dispensed = False` (locked until billing settlement).
  - Lab Orders: `lab_orders` created with unique barcode (`SMP-XXXXX`) and status `ORDERED`.
  - Billing: Consolidated `invoices` row (`INV-2026-XXXX`) with `payment_status="UNPAID"` combining consultation, lab, and pharmacy charges.
  - Appointment: Transitioned to `COMPLETED`.

---

### Flow 5: Closed-Loop Pharmacy Dispensing Guardrail
Strict invariant preventing unauthorized drug delivery without prior cashier settlement.

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient
    actor Pharmacist as Dispensary Pharmacist
    actor Cashier as Cashier Desk
    participant UI as Pharmacy Workstation (/pharmacy)
    participant API as /api/pharmacy/dispense
    participant Svc as PharmacyService
    participant DB as SQLite (hospital.db)

    Note over UI: Prescription appears in Dispensary Queue with Red Badge: [LOCKED] Payment Locked
    alt Attempting to dispense before payment
        Pharmacist->>UI: Click "Dispense Medicine" (override_reason is null)
        UI->>API: POST /api/pharmacy/dispense (prescription_item_id)
        API->>Svc: dispense_prescription_item(db, data, pharmacist_id)
        Svc->>DB: Look up Invoice for linked encounter
        Svc->>Svc: invoice.payment_status != 'PAID'
        Svc-->>API: raise HTTPException(403, "Closed-Loop Guardrail: Cannot dispense. Invoice is UNPAID.")
        API-->>UI: 403 Forbidden
        UI-->>Pharmacist: Error Modal: "Direct patient to Cashier desk."
    else Cashier settles bill first
        Patient->>Cashier: Settle bill at cashier desk
        Cashier->>DB: Invoice payment_status updated to 'PAID'
        UI->>UI: Queue auto-refreshes -> Badge turns Green: [PAID] Bill Paid
        Pharmacist->>UI: Click "Dispense Medicine"
        UI->>API: POST /api/pharmacy/dispense
        API->>Svc: dispense_prescription_item(...)
        Svc->>DB: Verify stock >= quantity_prescribed
        Svc->>DB: UPDATE medicines SET stock_quantity = stock_quantity - qty
        Svc->>DB: UPDATE prescription_items SET is_dispensed=True, dispensed_at=NOW()
        DB-->>Svc: Updated Item
        Svc-->>API: PrescriptionItem Entity
        API-->>UI: 200 OK
        UI-->>Pharmacist: Success Alert + Inventory Count Decremented Live
    end
```

- **Desired Output:**
  - Unpaid Attempt: HTTP `403 Forbidden` with detailed rejection explanation.
  - Paid Execution:
    - `prescription_items.is_dispensed = True`, `dispensed_at = TIMESTAMP`, `dispensed_by_id = PHARMACIST_ID`.
    - `medicines.stock_quantity` decremented by prescribed count.
    - Real-time inventory run-out forecasts updated in Pharmacy Analytics.

---

### Flow 6: Pathology Laboratory Diagnostic Pipeline
End-to-end specimen collection, technician result entry, and automated reference-boundary/panic-threshold flagging.

```mermaid
sequenceDiagram
    autonumber
    actor Tech as Lab Technician
    participant UI as Lab Workstation (/lab)
    participant API as /api/lab
    participant Svc as LabService
    participant DB as SQLite (hospital.db)

    Note over UI: Order appears as status 'ORDERED' with generated barcode
    Tech->>UI: Collects blood/tissue specimen & clicks "Collect Sample"
    UI->>API: POST /api/lab/orders/{id}/collect
    API->>Svc: update_sample_collected(db, order_id)
    Svc->>DB: UPDATE lab_orders SET sample_status='SAMPLE_COLLECTED', collected_at=NOW()
    DB-->>UI: Status changes to SAMPLE_COLLECTED (In Analysis)

    Tech->>UI: Enters Result Value (e.g. "18.2"), selects Panic Flag ("CRITICAL_HIGH"), notes
    UI->>API: POST /api/lab/results (LabResultEntry)
    API->>Svc: enter_lab_result(db, data, tech_id)
    Svc->>DB: INSERT INTO lab_results (order_id, result_value, reference_range, is_abnormal, panic_flag, ...)
    Svc->>DB: UPDATE lab_orders SET sample_status='COMPLETED'
    DB-->>UI: Result logged with panic alert
    UI-->>Tech: 200 OK + Diagnostic report marked completed
```

- **Desired Output:**
  - Database: `lab_orders.sample_status = "COMPLETED"`; `lab_results` record storing tested numerical/text value, reference range, abnormal flag, and technician notes.
  - Doctor EHR UI: Patient's clinical chart immediately reflects the lab findings with colored panic indicators.

---

### Flow 7: Inpatient (IPD) Admission, Bed Turnaround State Machine & Discharge Clearance Block
Enforces the 3-state bed progression (`VACANT` $\rightarrow$ `OCCUPIED` $\rightarrow$ `CLEANING` $\rightarrow$ `VACANT`) and prevents discharge with unbilled stay charges, pending medication orders (IPMO), or open lab tests.

```mermaid
sequenceDiagram
    autonumber
    actor Doctor as Doctor / Nurse
    participant UI as Inpatient / Nurse Workstation
    participant API as /api/inpatient
    participant Svc as InpatientService
    participant DB as SQLite (hospital.db)

    Doctor->>UI: Select Patient & Available Bed
    UI->>API: POST /api/inpatient/admissions (AdmissionCreate)
    API->>Svc: admit_patient(db, data)
    Svc->>DB: Verify bed.status == 'VACANT'
    Svc->>DB: INSERT INTO inpatient_records (ip_number, status='ADMITTED', ...)
    Svc->>DB: UPDATE beds SET status='OCCUPIED', current_patient_id=patient_id
    DB-->>UI: 200 OK + Bed turns RED (Occupied)

    Note over Doctor,UI: Patient receives care; nurse administers scheduled IPMO medications

    Doctor->>UI: Request Discharge Clearance
    UI->>API: GET /api/inpatient/records/{id}/clearance
    API->>Svc: check_discharge_clearance(db, record_id)
    Svc->>DB: Check 1: Any unadministered IPMO on nurse chart?
    Svc->>DB: Check 2: Any open/incomplete lab orders for this patient?
    Svc->>DB: Check 3: Any unpaid or partial patient invoices?
    
    alt Outstanding Items Exist & No Override Provided
        Svc-->>API: can_discharge = False, blocking_reasons = [...]
        API-->>UI: 200 OK (Discharge Block Active)
        Doctor->>UI: Attempt POST /api/inpatient/discharge (allow_override=False)
        UI->>API: POST /api/inpatient/discharge
        API->>Svc: discharge_patient(...)
        Svc-->>API: raise HTTPException(403, "Discharge Billing Block Invariant...")
        API-->>UI: 403 Forbidden
    else Clearance Succeeded (or Emergency Override Provided)
        UI->>API: POST /api/inpatient/discharge (discharge_summary, condition)
        API->>Svc: discharge_patient(...)
        Svc->>Svc: Calculate Bed Stay Days * Bed Daily Rate
        Svc->>DB: INSERT INTO invoices (item_type='BED_CHARGE', status='UNPAID')
        Svc->>DB: UPDATE inpatient_records SET status='DISCHARGED'
        Svc->>DB: UPDATE beds SET status='CLEANING', current_patient_id=NULL
        DB-->>UI: 200 OK + Bed turns AMBER (Cleaning)
    end

    Note over UI: Once sanitized, Nurse toggles Bed status to VACANT (Green)
```

- **Desired Output:**
  - Admission: Bed status = `OCCUPIED`, `inpatient_records` entry created.
  - Discharge Block: HTTP `403 Forbidden` if any medication remains unadministered, lab tests are incomplete, or bills are unpaid.
  - Discharge Cleared:
    - Inpatient Record: `status = "DISCHARGED"`.
    - Bed Status: `CLEANING` (patient unlinked).
    - Inpatient Stay Invoice: Auto-generated with line item for bed days $\times$ daily rate.

---

### Flow 8: Consolidated Cashier Billing & Payment Receipt Allocation
Captures patient payment receipts across Cash, Card, or UPI, handles partial payments and discounts pro-rata across invoice lines, and records an auditable payment event.

```mermaid
sequenceDiagram
    autonumber
    actor Cashier as Cashier
    participant UI as Cashier Desk (/billing)
    participant API as /api/billing/collect-payment
    participant Svc as CommissionService (via BillingService)
    participant DB as SQLite (hospital.db)

    Cashier->>UI: Open Invoice, enter amount_paid, payment_method, transaction_ref, idempotency_key
    UI->>API: POST /api/billing/collect-payment (PaymentCollectRequest)
    API->>Svc: collect_payment(db, data, cashier_id)
    Svc->>DB: Lock writes: BEGIN IMMEDIATE
    Svc->>DB: Check duplicate idempotency_key or transaction_ref
    Svc->>Svc: Pro-rata distribute discounts across InvoiceItems
    Svc->>Svc: Pro-rata allocate receipt amount across outstanding item balances
    Svc->>DB: INSERT INTO payments (status='RECEIVED', amount=..., received_at=NOW())
    Svc->>DB: INSERT INTO payment_allocations (payment_id, invoice_item_id, amount)
    Svc->>DB: UPDATE invoices SET paid_amount = paid_amount + payment.amount
    Svc->>Svc: invoice.payment_status = 'PAID' if paid_amount >= net_payable else 'PARTIAL'
    Svc->>DB: INSERT INTO commission_audit_events (action='PAYMENT_RECEIVED')
    DB-->>Svc: Commit Transaction
    Svc-->>API: Return { status: 'SUCCESS', payment_id, invoice_number, payment_status, settlement_status }
    API-->>UI: 200 OK
    UI-->>Cashier: Opens Printable Receipt (/receipt/{id}) & Unlocks Pharmacy Dispense
```

- **Desired Output:**
  - Database:
    - New `payments` row (`status = "RECEIVED"`).
    - New `payment_allocations` rows mapping the receipt to specific line items.
    - Updated `invoices.paid_amount` and `payment_status` (`PAID` or `PARTIAL`).
    - New `commission_audit_events` audit record.
  - Downstream Effect: Instantly unlocks the Closed-Loop Pharmacy gatekeeper for any medications linked to this invoice.

---

### Flow 9: Doctor Commission Accrual, Reconciliation, Settlement & Payout Engine
Provides an enterprise, auditable clinician compensation pipeline with effective-dated rules, reconciliation gating, doctor statement isolation, and finance disbursement tracking.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Finance Admin
    actor Doctor as Doctor
    participant UI_ADM as Admin Console (/admin)
    participant UI_DOC as Doctor Portal (/doctor)
    participant API as /api/commissions
    participant Svc as CommissionService
    participant DB as SQLite (hospital.db)

    Note over UI_ADM: 1. Commission Rule Configuration
    Admin->>UI_ADM: Create Effective-Dated Rule (Doctor/Dept, Service Type, Percentage or Fixed)
    UI_ADM->>API: POST /api/commissions/rules
    API->>DB: INSERT INTO commission_rules (effective_from, calculation_type, rate, active=True)

    Note over UI_ADM: 2. Receipt Reconciliation
    Admin->>UI_ADM: Review Cashier Receipts awaiting reconciliation
    Admin->>UI_ADM: Click "Reconcile Receipt"
    UI_ADM->>API: POST /api/commissions/payments/{id}/reconcile
    API->>Svc: reconcile_payment(db, payment_id, actor_id)
    Svc->>DB: BEGIN IMMEDIATE
    Svc->>DB: Identify linked Doctor for invoice
    Svc->>DB: Find highest-specificity active rule matching (doctor, dept, service_type, date)
    Svc->>Svc: Calculate commission on collected line net: base * rate% (or fixed pro-rata)
    Svc->>DB: INSERT INTO commission_ledger_entries (status='AVAILABLE', generation_key=...)
    Svc->>DB: UPDATE payments SET status='RECONCILED'
    DB-->>UI_ADM: Payment Reconciled, Ledger Generated

    Note over UI_DOC: 3. Doctor Payout Request
    Doctor->>UI_DOC: View Available Balance on Statement
    Doctor->>UI_DOC: Submit Settlement Request (amount, period, idempotency_key)
    UI_DOC->>API: POST /api/commissions/settlements/requests
    API->>Svc: create_settlement_request(db, doctor_id, period, amount, key)
    Svc->>DB: Verify requested <= available_balance
    Svc->>DB: INSERT INTO settlement_requests (status='PENDING', request_number='SET-YYYYMMDD-XXXX')
    Svc->>DB: INSERT INTO settlement_allocations (status='RESERVED')
    DB-->>UI_DOC: Request submitted (Funds reserved)

    Note over UI_ADM: 4. Finance Approval & Payout Recording
    Admin->>UI_ADM: Review Pending Settlement Requests
    Admin->>UI_ADM: Approve Request
    UI_ADM->>API: POST /api/commissions/settlements/requests/{id}/decision (approve=True)
    API->>DB: UPDATE settlement_requests SET status='APPROVED'
    
    Admin->>UI_ADM: Record Bank Payout (method='BANK_TRANSFER', reference='UTR-998877', evidence)
    UI_ADM->>API: POST /api/commissions/settlements/requests/{id}/payout
    API->>Svc: record_payout(db, request_id, payload, actor_id)
    Svc->>DB: INSERT INTO settlement_payouts (...)
    Svc->>DB: UPDATE settlement_requests SET status='PAID'
    Svc->>DB: UPDATE settlement_allocations SET status='PAID'
    DB-->>UI_ADM: Payout Recorded, Audited & Archived
```

- **Desired Output:**
  - Reconciliation: `payments.status = "RECONCILED"`; immutable `commission_ledger_entries` created with `status = "AVAILABLE"`.
  - Settlement Request: `settlement_requests` created with `status = "PENDING"`; allocations reserved so funds cannot be double-requested.
  - Approval: `settlement_requests.status = "APPROVED"`.
  - Payout: `settlement_payouts` recorded with banking transaction reference and evidence; `settlement_requests.status = "PAID"`. Doctor statement updates in real time.

---

## 3. Comprehensive Component Catalog & Desired Outputs

| Domain | Component / File | Trigger / Input | Internal Processing & Logic | Invariants & Guardrails | Desired Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Auth** | [app/api/auth.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/auth.py)<br/>[app/core/security.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/core/security.py) | Form/JSON credentials (`username`, `password`) | PBKDF2-HMAC-SHA256 salted password verification; signed HMAC-SHA256 token creation. Sets `access_token` HTTP-only cookie. | Inactive account rejection; invalid signature drop; 12-hour session expiration. | HTTP `200 OK` + `{ access_token, token_type, role, user_id }` + redirect to role workstation. |
| **Patients** | [app/api/patients.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/patients.py)<br/>[app/services/patient_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/patient_service.py) | `POST /api/patients` with demographic details | Sequential MRN generator (`MRN-YYYY-XXXX`); multi-parameter lookup indexing Name, Phone, Aadhaar, MRN, and ID. | Unique MRN; sanitized strings; non-empty full name. | HTTP `200 OK` with persisted `PatientOut` object; real-time reception search results. |
| **Appointments** | [app/api/appointments.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/appointments.py)<br/>[app/services/appointment_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/appointment_service.py) | `POST /api/appointments` (`doctor_id`, `patient_id`, `date`, `slot`) | Double-booking verification; daily sequential token calculation; queue aggregation. | **Double-Booking Shield:** Single patient per doctor time slot. Excludes cancelled slots. | HTTP `200 OK` with `token_number` and `status="SCHEDULED"`, or `400 Bad Request` if occupied. |
| **Triage & Vitals** | [app/api/clinical.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/clinical.py)<br/>[app/services/clinical_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/clinical_service.py) | `POST /api/clinical/vitals` (BP, Temp, HR, SpO2, Ht, Wt) | Automated BMI calculation (`kg/m²`); rule-based evaluation against systolic, diastolic, fever, and hypoxemia limits. | Range checks; mandatory nurse identity logging. | HTTP `200 OK` with `is_abnormal: bool`, `bmi`, and comma-separated `clinical_flags`. |
| **Consultation** | [app/api/clinical.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/clinical.py)<br/>[app/services/clinical_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/clinical_service.py) | `POST /api/clinical/encounters` (SOAP, Rx list, Lab IDs) | Creates `Encounter`, unpacks `PrescriptionItem` rows, generates `LabOrder` rows with barcodes, generates consolidated `Invoice`. | Appointment completed automatically; doctor fee attached; items tagged for payment lock. | HTTP `200 OK` with `{ encounter_id, invoice_id, invoice_number, total_payable }`. |
| **Pharmacy** | [app/api/pharmacy.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/pharmacy.py)<br/>[app/services/pharmacy_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/pharmacy_service.py) | `POST /api/pharmacy/dispense` (`prescription_item_id`) | Checks invoice payment status; verifies stock availability; decrements formulary count. | **Closed-Loop Guardrail:** Rejects unpaid prescriptions with `403 Forbidden` unless override reason given. | HTTP `200 OK` with `is_dispensed=True`; formulary stock reduced in real time. |
| **Lab Diagnostics** | [app/api/lab.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/lab.py)<br/>[app/services/lab_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/lab_service.py) | `POST /api/lab/results` (`order_id`, `result_value`, `panic_flag`) | Links order to test template; records technician notes; marks sample status as `COMPLETED`. | Technician authentication required; panic thresholds highlighted in doctor queue. | HTTP `200 OK` with `LabResult` entity; doctor workstation alerted to abnormal findings. |
| **Inpatient (IPD)** | [app/api/inpatient.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/inpatient.py)<br/>[app/services/inpatient_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/inpatient_service.py) | `POST /api/inpatient/admissions`<br/>`POST /api/inpatient/discharge` | Bed allocation; IPMO schedule administration; discharge clearance evaluation; bed charge calculation. | **Discharge Block:** 403 Forbidden if unadministered IPMO, open labs, or unpaid bills exist without override. Bed state: `VACANT` $\rightarrow$ `OCCUPIED` $\rightarrow$ `CLEANING` $\rightarrow$ `VACANT`. | HTTP `200 OK`; Bed matrix turns from red to amber (`CLEANING`); inpatient stay invoice created. |
| **Billing & Cashier** | [app/api/billing.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/billing.py)<br/>[app/services/billing_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/billing_service.py) | `POST /api/billing/collect-payment` (Amount, Method, Ref, Key) | Idempotent receipt creation; pro-rata line item allocation; invoice balance calculation; payment status update. | Idempotency key protection; duplicate transaction reference rejection; over-payment lock. | HTTP `200 OK` with `{ status: 'SUCCESS', payment_id, invoice_number, payment_status }`; Printable thermal receipt ready. |
| **Commissions & Payouts** | [app/api/commissions.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/api/commissions.py)<br/>[app/services/commission_service.py](file:///Users/gauravsingh/Downloads/Production_HMS/Production_HMS/app/services/commission_service.py) | Reconcile receipt; Request settlement; Approve/Reject; Record payout | Specificity-based rule matching; ledger entry accrual; available balance reservation; payout evidence recording. | `BEGIN IMMEDIATE` financial locks; doctor role data isolation; no commission without reconciliation. | HTTP `200 OK`; immutable ledger entries; audited settlement requests; CSV statement exports. |

---

## 4. System Invariants & Enforcement Matrix

```
+---------------------------------------------------------------------------------------------------+
| INVARIANT 1: CLOSED-LOOP PHARMACY DISPENSING                                                      |
| Condition: PrescriptionItem cannot be dispensed if linked Invoice is UNPAID                       |
| Enforcement: PharmacyService.dispense_prescription_item checks invoice.payment_status == 'PAID'    |
| Rejection: HTTP 403 Forbidden ("Direct patient to Cashier desk")                                  |
+---------------------------------------------------------------------------------------------------+
| INVARIANT 2: DOUBLE-BOOKING SLOT SHIELD                                                           |
| Condition: Doctor cannot have 2 scheduled appointments in the same time slot                      |
| Enforcement: AppointmentService.book_appointment checks (doctor_id, date, slot, status!=CANCELLED) |
| Rejection: HTTP 400 Bad Request ("Time slot already booked for Dr. ...")                          |
+---------------------------------------------------------------------------------------------------+
| INVARIANT 3: BED TURNAROUND STATE MACHINE                                                         |
| Condition: Beds must strictly progress VACANT -> OCCUPIED -> CLEANING -> VACANT                   |
| Enforcement: InpatientService validates vacancy before admission, forces CLEANING on discharge    |
| Rejection: HTTP 400 Bad Request ("Bed is currently OCCUPIED / CLEANING")                          |
+---------------------------------------------------------------------------------------------------+
| INVARIANT 4: DISCHARGE BILLING & CLINICAL CLEARANCE BLOCK                                         |
| Condition: Inpatient cannot be discharged with open medication logs, open labs, or unpaid bills  |
| Enforcement: InpatientService.discharge_patient validates 3-point clearance checklist             |
| Rejection: HTTP 403 Forbidden (Audited Emergency Clinical Override available)                    |
+---------------------------------------------------------------------------------------------------+
| INVARIANT 5: RECONCILED-ONLY COMMISSION ACCRUAL                                                   |
| Condition: Doctor commission never accrues on unverified receipts or aggregate legacy balances    |
| Enforcement: CommissionService calculates ledger entries ONLY upon authorized reconciliation      |
| Serialization: BEGIN IMMEDIATE on SQLite ensures concurrency-safe reservations and payouts        |
+---------------------------------------------------------------------------------------------------+
```

---

## 5. Verification & Live Serving Instructions

### Automated Regression Verification
The entire test suite is located in `tests/test_hms_core.py` and `tests/test_commission_workflow.py`.  
Execute the suite with:
```bash
pytest -v
```
**Current Result:** `15 passed, 178 warnings in 2.87s` (100% Passing).

### Launching the Application
Execute from the project workspace root:
```bash
python app.py
```
- **Web Portal:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive OpenAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
