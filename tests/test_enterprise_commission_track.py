from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo
import calendar

from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.billing import Invoice, InvoiceItem
from app.models.clinical import Encounter
from app.models.patient import Patient
from app.models.user import User
from app.models.commission import CommissionRule, CommissionLedgerEntry, Payment
from app.services import commission_service as service

client = TestClient(app)


def _create_patient_with_referral(doctor_id: int):
    db = SessionLocal()
    try:
        token = uuid4().hex[:8].upper()
        patient = Patient(
            mrn=f"MRN-REF-{token}",
            full_name=f"Referred Patient {token}",
            phone_number=f"91234{token[:5]}",
            age=45,
            gender="FEMALE",
            referred_by_doctor_id=doctor_id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        return patient.id
    finally:
        db.close()


def _create_encounter_and_invoice(doctor_id: int, patient_id: int, net_amount=100.0, service_type="CONSULTATION"):
    db = SessionLocal()
    try:
        token = uuid4().hex[:8].upper()
        encounter = Encounter(
            patient_id=patient_id,
            doctor_id=doctor_id,
            chief_complaint="Referral consultation follow-up",
            diagnosis="Routine checkup",
            status="FINALIZED"
        )
        db.add(encounter)
        db.flush()

        invoice = Invoice(
            invoice_number=f"INV-REF-{token}",
            patient_id=patient_id,
            encounter_id=encounter.id,
            total_amount=net_amount,
            discount_amount=0.0,
            net_payable=net_amount,
            paid_amount=0.0,
            payment_status="UNPAID"
        )
        db.add(invoice)
        db.flush()

        db.add(InvoiceItem(
            invoice_id=invoice.id,
            item_type=service_type,
            description=f"Specialist {service_type}",
            quantity=1,
            unit_price=net_amount,
            total_price=net_amount
        ))
        db.commit()
        return invoice.id
    finally:
        db.close()


def test_patient_model_referred_by_doctor_and_registration():
    # Get doctor ID
    doctor_res = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    doctor_id = doctor_res.json()["user_id"]

    # Login as receptionist (has patient:create permission)
    rec_res = client.post("/api/auth/login", json={"username": "recep.riya", "password": "recep123"})
    assert rec_res.status_code == 200

    token = uuid4().hex[:6]
    # Register patient with referred_by_doctor_id
    res = client.post("/api/patients/", json={
        "full_name": f"Referred Patient {token}",
        "phone_number": f"98765{token[:5]}",
        "age": 35,
        "gender": "MALE",
        "referred_by_doctor_id": doctor_id
    })
    assert res.status_code == 200, res.text
    patient_data = res.json()
    assert patient_data["referred_by_doctor_id"] == doctor_id

    # Verify directly from DB
    db = SessionLocal()
    try:
        p = db.query(Patient).filter(Patient.id == patient_data["id"]).first()
        assert p is not None
        assert p.referred_by_doctor_id == doctor_id
    finally:
        db.close()


def _create_test_doctor():
    db = SessionLocal()
    try:
        from app.core.security import hash_password
        token = uuid4().hex[:6]
        doctor = User(
            username=f"dr.neu_{token}",
            email=f"dr.neu_{token}@aegishealth.org",
            hashed_password=hash_password("doc123"),
            full_name=f"Dr. Neurologist {token}",
            role="DOCTOR",
            department="Neurology",
            consultation_fee=600,
            is_active=True
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        return doctor.id, doctor.username
    finally:
        db.close()


def test_invariant_a_patient_unpaid_bills_locks_commission_and_release_on_payment():
    # Setup dedicated doctor and rule
    doctor_id, doctor_username = _create_test_doctor()

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    rule_res = client.post("/api/commissions/rules", json={
        "idempotency_key": f"rule-invA-{uuid4().hex}",
        "name": f"Invariant A Rule {uuid4().hex[:6]}",
        "doctor_id": doctor_id,
        "service_type": "CONSULTATION",
        "calculation_type": "PERCENTAGE",
        "rate": "15.0000",
        "require_all_patient_bills_paid": True,
        "min_settlement_threshold": 0.0,
        "effective_from": "2020-01-01"
    })
    assert rule_res.status_code == 201, rule_res.text

    # Create patient with referral
    patient_id = _create_patient_with_referral(doctor_id)

    # Patient has Invoice 1 (to be paid and generate commission)
    inv1_id = _create_encounter_and_invoice(doctor_id, patient_id, net_amount=200.0, service_type="CONSULTATION")
    
    # Patient ALSO has an outstanding second invoice (Invoice 2: UNPAID)
    inv2_id = _create_encounter_and_invoice(doctor_id, patient_id, net_amount=150.0, service_type="CONSULTATION")

    # Pay Invoice 1 in full
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    pay_res = client.post("/api/billing/collect", json={
        "invoice_id": inv1_id,
        "amount_paid": "200.00",
        "payment_method": "CASH",
        "idempotency_key": f"pay-inv1-{uuid4().hex}"
    })
    assert pay_res.status_code == 200
    payment_id = pay_res.json()["payment_id"]

    # Reconcile payment
    recon_res = client.post(f"/api/billing/payments/{payment_id}/reconcile")
    assert recon_res.status_code == 200
    assert recon_res.json()["generated_entries"] == 1

    # Verify Invariant A: Since Invoice 2 is UNPAID, ledger row MUST remain in ACCRUED (Locked)
    db = SessionLocal()
    try:
        entry = db.query(CommissionLedgerEntry).filter(
            CommissionLedgerEntry.payment_id == payment_id,
            CommissionLedgerEntry.doctor_id == doctor_id
        ).first()
        assert entry is not None
        assert entry.status == "ACCRUED"
        assert "Waiting for Patient Bill Settlement" in (entry.execution_audit_log or "")
        assert entry.released_at is None
    finally:
        db.close()

    # Doctor queries instant payout endpoint: Must fail with amber chip and blocking details
    client.post("/api/auth/login", json={"username": doctor_username, "password": "doc123"})
    payout_try = client.post("/api/commissions/instant-payout")
    assert payout_try.status_code == 200
    payout_data = payout_try.json()
    assert payout_data["success"] is False
    assert payout_data["reason"] == "PATIENT_BILLS_UNPAID"
    assert payout_data["chip_label"] == "[🔒 Waiting for Patient Bill Settlement]"
    assert len(payout_data["blocking_details"]) > 0

    # Now, pay Invoice 2 in full!
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    pay2_res = client.post("/api/billing/collect", json={
        "invoice_id": inv2_id,
        "amount_paid": "150.00",
        "payment_method": "CASH",
        "idempotency_key": f"pay-inv2-{uuid4().hex}"
    })
    assert pay2_res.status_code == 200

    # Doctor re-evaluates commissions
    client.post("/api/auth/login", json={"username": doctor_username, "password": "doc123"})
    eval_res = client.post("/api/commissions/evaluate")
    assert eval_res.status_code == 200

    # Verify Invariant A has now PASSED: ledger row is now RELEASED with released_at populated
    db = SessionLocal()
    try:
        entry = db.query(CommissionLedgerEntry).filter(
            CommissionLedgerEntry.payment_id == payment_id,
            CommissionLedgerEntry.doctor_id == doctor_id
        ).first()
        assert entry.status == "RELEASED"
        assert entry.released_at is not None
        assert "All patient bills verified settled" in entry.execution_audit_log
    finally:
        db.close()

    # Now instant payout succeeds!
    instant_res = client.post("/api/commissions/instant-payout")
    assert instant_res.status_code == 200
    instant_data = instant_res.json()
    assert instant_data["success"] is True
    assert instant_data["chip_label"] == "[🔓 Ready to Pull]"
    assert "bank_details" in instant_data
    assert instant_data["bank_details"]["bank_name"] == "State Bank of India (Hospital Verified)"
    assert instant_data["payment_reference"].startswith("UTR-")


def test_invariant_b_month_end_threshold_locks_early_month_commissions():
    doctor_res = client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    doctor_id = doctor_res.json()["user_id"]

    # Create rule with high minimum settlement threshold (e.g. ₹50,000)
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    rule_res = client.post("/api/commissions/rules", json={
        "idempotency_key": f"rule-invB-{uuid4().hex}",
        "name": f"High Threshold Rule {uuid4().hex[:6]}",
        "doctor_id": doctor_id,
        "service_type": "INPATIENT_STAY",
        "calculation_type": "PERCENTAGE",
        "rate": "10.0000",
        "require_all_patient_bills_paid": True,
        "min_settlement_threshold": 50000.0,
        "effective_from": "2020-01-01"
    })
    assert rule_res.status_code == 201, rule_res.text
    rule_id = rule_res.json()["id"]

    patient_id = _create_patient_with_referral(doctor_id)
    # Service type INPATIENT_STAY (mapped to BED_CHARGE)
    inv_id = _create_encounter_and_invoice(doctor_id, patient_id, net_amount=1000.0, service_type="BED_CHARGE")

    # Pay bill in full
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    pay_res = client.post("/api/billing/collect", json={
        "invoice_id": inv_id,
        "amount_paid": "1000.00",
        "payment_method": "UPI",
        "idempotency_key": f"pay-bed-{uuid4().hex}"
    })
    payment_id = pay_res.json()["payment_id"]
    recon_res = client.post(f"/api/billing/payments/{payment_id}/reconcile")
    assert recon_res.status_code == 200

    # Current date check
    today = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
    _, last_day = calendar.monthrange(today.year, today.month)
    month_end = date(today.year, today.month, last_day)

    db = SessionLocal()
    try:
        entry = db.query(CommissionLedgerEntry).filter(
            CommissionLedgerEntry.payment_id == payment_id,
            CommissionLedgerEntry.doctor_id == doctor_id
        ).first()
        assert entry is not None

        if today < month_end:
            # Entry must be held in ACCRUED due to Invariant B
            assert entry.status == "ACCRUED"
            assert "Early Month Threshold Lock" in (entry.execution_audit_log or "")
        else:
            # On the month-end day, threshold restriction lifts
            assert entry.status == "RELEASED"
    finally:
        db.close()


def test_granular_ledger_endpoints_and_isolation():
    # Login as Doctor Sharma
    sharma_res = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    sharma_id = sharma_res.json()["user_id"]

    # Login as Doctor Anita
    anita_res = client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    anita_id = anita_res.json()["user_id"]

    # Doctor Sharma accesses own ledger: 200 OK
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    own_ledger = client.get("/api/commissions/ledger")
    assert own_ledger.status_code == 200
    for item in own_ledger.json()["items"]:
        assert item["doctor_id"] == sharma_id

    # Doctor Sharma attempts to access Doctor Anita's ledger: 403 Forbidden Isolation
    cross_ledger = client.get(f"/api/commissions/ledger?doctor_id={anita_id}")
    assert cross_ledger.status_code == 403

    # Admin accesses ledger with filters: 200 OK
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    admin_ledger = client.get(f"/api/commissions/ledger?doctor_id={anita_id}&status=ACCRUED")
    assert admin_ledger.status_code == 200
    for item in admin_ledger.json()["items"]:
        assert item["doctor_id"] == anita_id
        assert item["status"] == "ACCRUED"
        assert item["chip_label"].startswith("[🔒")
