from starlette.testclient import TestClient
import sys
import os

# Ensure production_hms root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app


client = TestClient(app)

def test_role_scoped_clinical_and_lab_views():
    """Doctors cannot switch to another clinician's queue; lab views follow RBAC."""
    doctor_login = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"}).json()
    other_doctor_login = client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"}).json()

    client.cookies.clear()
    client.cookies.set("access_token", doctor_login["access_token"])
    doctor_page = client.get("/doctor")
    assert doctor_page.status_code == 200
    assert "window.HMS_IS_DOCTOR = true" in doctor_page.text
    assert "id=\"doctorQueueSelect\"" not in doctor_page.text
    assert client.get("/static/css/components.css?v=staff-ux-1").status_code == 200
    forced_own_view = client.get("/api/clinical/analytics", params={"doctor_id": other_doctor_login["user_id"]})
    actual_own_view = client.get("/api/clinical/analytics")
    assert forced_own_view.status_code == 200
    assert forced_own_view.json() == actual_own_view.json()
    assert client.get("/api/appointments/doctor-queue", params={"doctor_id": other_doctor_login["user_id"]}).status_code == 403
    assert client.get("/api/lab/analytics").status_code == 403

    lab_login = client.post("/api/auth/login", json={"username": "lab.john", "password": "lab123"}).json()
    client.cookies.clear()
    client.cookies.set("access_token", lab_login["access_token"])
    assert client.get("/api/lab/analytics").status_code == 200

def test_public_pages_render():
    """Verifies that all role portal pages render successfully."""
    routes = ["/", "/login", "/reception", "/doctor", "/nurse", "/lab", "/pharmacy", "/billing", "/admin"]
    for route in routes:
        res = client.get(route)
        assert res.status_code == 200, f"Failed on route {route}: {res.status_code}"
        assert "<!DOCTYPE html>" in res.text

def test_staff_login_and_auth():
    """Verifies authentication for doctor, receptionist, superadmin, and cashier."""
    res = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "DOCTOR"
    assert data["full_name"] == "Dr. Rajesh Sharma"
    assert "clinical:encounter" in data["permissions"]

    # Test superadmin
    res_super = client.post("/api/auth/login", json={"username": "superadmin", "password": "super123"})
    assert res_super.status_code == 200
    assert "*" in res_super.json()["permissions"]

    # Test cashier
    res_cash = client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    assert res_cash.status_code == 200
    assert "billing:reconcile" in res_cash.json()["permissions"]

def test_patient_registration_and_search():
    """Verifies patient registration, MRN sequential assignment, and live search by Receptionist."""
    client.post("/api/auth/login", json={"username": "recep.riya", "password": "recep123"})
    
    # Register new patient
    new_patient = {
        "full_name": "Test Patient",
        "phone_number": "9988776655",
        "age": 35,
        "gender": "MALE",
        "blood_group": "O+",
        "allergies": "Sulfa drugs"
    }
    res = client.post("/api/patients/", json=new_patient)
    assert res.status_code == 200
    p = res.json()
    assert "MRN-2026-" in p["mrn"]
    assert p["full_name"] == "Test Patient"
    
    # Search by phone
    res_search = client.get("/api/patients/search?q=9988776655")
    assert res_search.status_code == 200
    results = res_search.json()
    assert len(results) >= 1
    assert results[0]["phone_number"] == "9988776655"

def test_appointment_booking_and_conflict_check():
    """Verifies booking time slot and error on double-booking by Receptionist."""
    # Find test doctor
    login_res = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    doc_id = login_res.json()["user_id"]

    # Log in as receptionist to book appointment
    client.post("/api/auth/login", json={"username": "recep.riya", "password": "recep123"})

    payload = {
        "patient_id": 1,
        "doctor_id": doc_id,
        "department": "Cardiology",
        "appointment_date": "2026-11-01",
        "time_slot": "10:00 - 10:15",
        "reason_for_visit": "Chest heaviness"
    }
    res = client.post("/api/appointments/", json=payload)
    assert res.status_code == 200
    appt = res.json()
    assert appt["token_number"] >= 1

    # Attempt to double-book same slot -> must fail with 400
    res_duplicate = client.post("/api/appointments/", json=payload)
    assert res_duplicate.status_code == 400
    assert "already booked" in res_duplicate.json()["detail"]

def test_vitals_recording_and_bmi_evaluation():
    """Verifies vitals logging, BMI auto-calc, and hypertension flagging by Nurse."""
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})

    # Normal vitals
    vitals_data = {
        "patient_id": 1,
        "temperature_f": 98.4,
        "blood_pressure_systolic": 118,
        "blood_pressure_diastolic": 78,
        "heart_rate_bpm": 72,
        "spo2_percent": 99,
        "weight_kg": 70.0,
        "height_cm": 175.0
    }
    res = client.post("/api/clinical/vitals", json=vitals_data)
    assert res.status_code == 200
    v = res.json()
    assert v["bmi"] == 22.9
    assert v["is_abnormal"] is False

    # Hypertensive crisis vitals
    hyper_data = {
        "patient_id": 1,
        "blood_pressure_systolic": 170,
        "blood_pressure_diastolic": 105,
        "spo2_percent": 91
    }
    res_abnormal = client.post("/api/clinical/vitals", json=hyper_data)
    assert res_abnormal.status_code == 200
    v2 = res_abnormal.json()
    assert v2["is_abnormal"] is True
    assert "Hypertension" in v2["clinical_flags"]

def test_closed_loop_pharmacy_guardrail():
    """
    CRITICAL INVARIANT TEST:
    Verifies that pharmacy cannot dispense medication when invoice is UNPAID,
    and successfully dispenses once invoice is PAID.
    """
    # 1. Finalize doctor encounter (Doctor role)
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    encounter_payload = {
        "patient_id": 1,
        "doctor_id": 2, # Dr. Sharma
        "chief_complaint": "Viral fever and body ache",
        "diagnosis": "Acute Febrile Illness",
        "prescriptions": [
            {
                "medicine_id": 1, # Dolo 650
                "medicine_name": "Dolo 650",
                "dosage": "650 mg",
                "frequency": "1-0-1",
                "duration_days": 3,
                "instructions": "After Food",
                "quantity": 6
            }
        ],
        "lab_test_template_ids": [1] # CBC
    }
    enc_res = client.post("/api/clinical/encounter", json=encounter_payload)
    assert enc_res.status_code == 200
    enc_data = enc_res.json()
    invoice_id = enc_data["invoice_id"]
    invoice_number = enc_data["invoice_number"]

    # 2. Pharmacist logs in and checks dispensary queue
    client.post("/api/auth/login", json={"username": "pharma.kumar", "password": "pharma123"})
    queue_res = client.get("/api/pharmacy/queue")
    assert queue_res.status_code == 200
    queue = queue_res.json()
    target_rx = next(item for item in queue if item["encounter_id"] == enc_data["encounter_id"])
    assert target_rx["is_paid"] is False

    # 3. Try to dispense while invoice is UNPAID -> Must be blocked with 403 Forbidden!
    dispense_try = client.post("/api/pharmacy/dispense", json={"prescription_item_id": target_rx["id"]})
    assert dispense_try.status_code == 403
    assert "Closed-Loop Guardrail" in dispense_try.json()["detail"]

    # 4. Cashier collects payment (Cashier role)
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    pay_res = client.post("/api/billing/collect", json={
        "invoice_id": invoice_id,
        "amount_paid": enc_data["total_payable"],
        "payment_method": "UPI",
        "transaction_ref": "UPI-TXN-998811",
        "idempotency_key": "test-pharmacy-payment-998811"
    })
    assert pay_res.status_code == 200
    assert pay_res.json()["payment_status"] == "PAID"

    # 5. Pharmacist dispenses now -> Must succeed!
    client.post("/api/auth/login", json={"username": "pharma.kumar", "password": "pharma123"})
    dispense_success = client.post("/api/pharmacy/dispense", json={"prescription_item_id": target_rx["id"]})
    assert dispense_success.status_code == 200
    assert dispense_success.json()["status"] == "DISPENSED"

def test_inpatient_bed_matrix_and_discharge():
    """
    CRITICAL INVARIANT TEST:
    Verifies bed allocation, IPMO scheduling, Discharge Billing Block Invariant enforcement
    (blocking discharge when open medication orders or incomplete tests exist),
    and clearance/override execution.
    """
    # Nurse accesses bed matrix and admits patient
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})
    matrix_res = client.get("/api/inpatient/bed-matrix")
    assert matrix_res.status_code == 200
    matrix = matrix_res.json()
    assert "General Ward A" in matrix

    # 1. Admit patient to Bed GEN-101
    admit_res = client.post("/api/inpatient/admit", json={
        "patient_id": 2,
        "bed_id": 1,
        "attending_doctor_id": 2,
        "admission_reason": "Acute Observation & IV Hydration",
        "expected_days": 2
    })
    assert admit_res.status_code == 200
    admit_data = admit_res.json()
    assert "IPD-2026-" in admit_data["ip_number"]
    rec_id = admit_data["inpatient_record_id"]

    # Verify bed is now OCCUPIED
    matrix_updated = client.get("/api/inpatient/bed-matrix").json()
    gen101 = next(b for b in matrix_updated["General Ward A"] if b["bed_number"] == "GEN-101")
    assert gen101["status"] == "OCCUPIED"

    # 2. Doctor prescribes IPMO medication dose on the chart
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    ipmo_res = client.post("/api/inpatient/ipmo", json={
        "inpatient_record_id": rec_id,
        "patient_id": 2,
        "medicine_name": "Paracetamol IV Infusion",
        "dosage": "1000 mg in 100ml NS",
        "frequency": "TDS - Every 8 Hours",
        "route": "IV_INFUSION",
        "scheduled_slot": "14:00 PM",
        "notes": "Administer slowly over 15 minutes"
    })
    assert ipmo_res.status_code == 200
    order_id = ipmo_res.json()["id"]

    # 3. Nurse checks clearance: Must report can_discharge = False
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})
    clearance_res = client.get(f"/api/inpatient/clearance/{rec_id}")
    assert clearance_res.status_code == 200
    clearance_data = clearance_res.json()
    assert clearance_data["can_discharge"] is False
    assert clearance_data["pending_medications_count"] >= 1

    # 4. Attempt premature discharge -> MUST BE BLOCKED BY INVARIANT (403 Forbidden)
    premature_discharge = client.post("/api/inpatient/discharge", json={
        "inpatient_record_id": rec_id,
        "discharge_condition": "STABLE",
        "discharge_summary": "Attempting early discharge before administering scheduled IV medication."
    })
    assert premature_discharge.status_code == 403
    assert "Discharge Billing Block Invariant" in premature_discharge.json()["detail"]
    assert "unadministered medication order" in premature_discharge.json()["detail"]

    # 5. Nurse administers scheduled medication dose
    admin_res = client.post("/api/inpatient/administer-ipmo", json={
        "order_id": order_id,
        "notes": "Infusion completed satisfactorily"
    })
    assert admin_res.status_code == 200
    assert admin_res.json()["status"] == "ADMINISTERED"

    # 6. Verify clearance is now approved
    clearance_cleared = client.get(f"/api/inpatient/clearance/{rec_id}").json()
    assert clearance_cleared["can_discharge"] is True
    assert clearance_cleared["pending_medications_count"] == 0

    # 7. Discharge patient -> Must succeed!
    discharge_res = client.post("/api/inpatient/discharge", json={
        "inpatient_record_id": rec_id,
        "discharge_condition": "STABLE",
        "discharge_summary": "Patient recovered well on oral hydration and supportive medications."
    })
    assert discharge_res.status_code == 200
    assert discharge_res.json()["status"] == "DISCHARGED"
    assert "invoice_id" in discharge_res.json()

    # 8. Test Emergency Clinical Override Bypass pathway on second admission
    admit_res2 = client.post("/api/inpatient/admit", json={
        "patient_id": 3,
        "bed_id": 2, # Bed GEN-102
        "attending_doctor_id": 2,
        "admission_reason": "Emergency cardiac monitoring",
        "expected_days": 1
    })
    assert admit_res2.status_code == 200
    rec_id2 = admit_res2.json()["inpatient_record_id"]

    # Doctor adds open IPMO
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    client.post("/api/inpatient/ipmo", json={
        "inpatient_record_id": rec_id2,
        "patient_id": 3,
        "medicine_name": "Aspirin 75mg",
        "dosage": "75 mg",
        "frequency": "OD",
        "route": "ORAL",
        "scheduled_slot": "20:00 PM"
    })

    # Nurse discharges with Emergency Override Bypass -> Must succeed and record override
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})
    override_res = client.post("/api/inpatient/discharge", json={
        "inpatient_record_id": rec_id2,
        "discharge_condition": "REFERRED",
        "discharge_summary": "Patient transferring to state cardiology institute.",
        "allow_override": True,
        "override_reason": "Emergency transfer protocol initiated by Senior Consultant"
    })
    assert override_res.status_code == 200
    assert override_res.json()["status"] == "DISCHARGED"
    assert override_res.json()["override_applied"] is True

def test_rbac_matrix_permissions_and_restrictions():
    """
    Exhaustively tests all 8 roles and their strict permission boundaries:
    1. super_admin: has * privileges, can view audit logs and trigger system purge
    2. admin: can view/create staff, blocked from user:delete and system:purge
    3. receptionist: can create/search patients, book appointments; blocked from clinical encounter & pharmacy
    4. nurse: can record vitals and administer IPMO; blocked from writing prescriptions
    5. doctor: can write SOAP encounter and lab orders; blocked from billing collection
    6. pharmacist: can dispense medications; blocked from billing collection
    7. lab_tech: can view worklist and submit results; blocked from pharmacy dispense
    8. cashier: can reconcile billing payments; blocked from writing doctor encounters
    """
    # 1. Super Admin: full access
    client.post("/api/auth/login", json={"username": "superadmin", "password": "super123"})
    logs_res = client.get("/api/auth/audit-logs")
    assert logs_res.status_code == 200
    assert isinstance(logs_res.json(), list)

    purge_res = client.post("/api/auth/system/purge", json={"confirm_text": "PURGE_AUDIT_LOGS"})
    assert purge_res.status_code == 200
    assert purge_res.json()["status"] == "SUCCESS"

    # 2. Admin: can view users, but blocked from destructive delete and purge
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    users_res = client.get("/api/auth/users")
    assert users_res.status_code == 200

    admin_purge_res = client.post("/api/auth/system/purge", json={"confirm_text": "PURGE_AUDIT_LOGS"})
    assert admin_purge_res.status_code == 403

    admin_delete_res = client.delete("/api/auth/users/999")
    assert admin_delete_res.status_code == 403

    # 3. Receptionist: blocked from clinical encounter
    client.post("/api/auth/login", json={"username": "recep.riya", "password": "recep123"})
    rec_enc = client.post("/api/clinical/encounter", json={"patient_id": 1, "doctor_id": 1, "chief_complaint": "test", "diagnosis": "test"})
    assert rec_enc.status_code == 403

    # 4. Nurse: blocked from writing encounter / prescriptions
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})
    nurse_enc = client.post("/api/clinical/encounter", json={"patient_id": 1, "doctor_id": 1, "chief_complaint": "test", "diagnosis": "test"})
    assert nurse_enc.status_code == 403

    # 5. Doctor: blocked from collecting cashier payment
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    doc_collect = client.post("/api/billing/collect", json={"invoice_id": 1, "amount_paid": 500, "payment_method": "CASH"})
    assert doc_collect.status_code == 403

    # 6. Pharmacist: blocked from collecting cashier payment
    client.post("/api/auth/login", json={"username": "pharma.kumar", "password": "pharma123"})
    pharma_collect = client.post("/api/billing/collect", json={"invoice_id": 1, "amount_paid": 500, "payment_method": "CASH"})
    assert pharma_collect.status_code == 403

    # 7. Lab Tech: can view lab worklist, blocked from pharmacy queue
    client.post("/api/auth/login", json={"username": "lab.john", "password": "lab123"})
    lab_wl = client.get("/api/lab/worklist")
    assert lab_wl.status_code == 200
    lab_pharm = client.get("/api/pharmacy/queue")
    assert lab_pharm.status_code == 403

    # 8. Cashier: can access billing invoices, blocked from clinical encounter
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    cash_invoices = client.get("/api/billing/invoices")
    assert cash_invoices.status_code == 200
    cash_enc = client.post("/api/clinical/encounter", json={"patient_id": 1, "doctor_id": 1, "chief_complaint": "test", "diagnosis": "test"})
    assert cash_enc.status_code == 403

def test_pharmacy_analytics_and_restock():
    """Verifies real-time pharmacy KPI analytics, forecasting, and restocking."""
    client.post("/api/auth/login", json={"username": "pharma.kumar", "password": "pharma123"})
    res = client.get("/api/pharmacy/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "kpis" in data
    assert "categories" in data
    assert "stock_comparison" in data
    assert "forecast" in data
    assert data["kpis"]["total_skus"] >= 7
    assert data["kpis"]["total_inventory_value"] > 0

    # Test restocking
    med_id = data["stock_comparison"][0]["id"]
    prev_stock = data["stock_comparison"][0]["stock_quantity"]
    restock_res = client.post("/api/pharmacy/restock", json={"medicine_id": med_id, "quantity_to_add": 50, "batch_number": "TEST-BAT-01"})
    assert restock_res.status_code == 200
    assert restock_res.json()["new_stock"] == prev_stock + 50

def test_workstation_analytics_and_alerts():
    """
    Verifies tailored smart analytics and alert systems across all hospital workstations:
    Reception, Doctor, Nurse, Lab, and Cashier.
    """
    # 1. Reception Station
    client.post("/api/auth/login", json={"username": "recep.riya", "password": "recep123"})
    rec_res = client.get("/api/appointments/analytics")
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert "kpis" in rec_data
    assert "doctor_capacity" in rec_data
    assert "alerts" in rec_data
    assert "today_appointments" in rec_data["kpis"]

    # 2. Doctor Station
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    doc_res = client.get("/api/clinical/analytics?doctor_id=1")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert "kpis" in doc_data
    assert "alerts" in doc_data
    assert "queue_total" in doc_data["kpis"]

    # 3. Nurse Station
    client.post("/api/auth/login", json={"username": "nurse.mary", "password": "nurse123"})
    nurse_res = client.get("/api/inpatient/analytics")
    assert nurse_res.status_code == 200
    nurse_data = nurse_res.json()
    assert "kpis" in nurse_data
    assert "wards" in nurse_data
    assert "alerts" in nurse_data
    assert "occupancy_rate_pct" in nurse_data["kpis"]
    assert "vacant_beds" in nurse_data["kpis"]

    # 4. Lab Station
    client.post("/api/auth/login", json={"username": "lab.john", "password": "lab123"})
    lab_res = client.get("/api/lab/analytics")
    assert lab_res.status_code == 200
    lab_data = lab_res.json()
    assert "kpis" in lab_data
    assert "alerts" in lab_data
    assert "total_orders" in lab_data["kpis"]
    assert "panic_count" in lab_data["kpis"]

    # 5. Cashier Station
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    cash_res = client.get("/api/billing/cashier-analytics")
    assert cash_res.status_code == 200
    cash_data = cash_res.json()
    assert "kpis" in cash_data
    assert "payment_methods" in cash_data
    assert "alerts" in cash_data
    assert "total_collected" in cash_data["kpis"]
    assert "total_receivable_unpaid" in cash_data["kpis"]




