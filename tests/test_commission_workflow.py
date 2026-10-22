from datetime import datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from starlette.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.billing import Invoice, InvoiceItem
from app.models.clinical import Encounter
from app.models.patient import Patient
from app.models.user import User
from app.models.commission import CommissionLedgerEntry, SettlementRequest
from app.services.commission_service import create_settlement_request
from fastapi import HTTPException

client = TestClient(app)


def _commission_invoice(doctor_id: int, net=90.00, patient_id=None):
    db = SessionLocal()
    try:
        token = uuid4().hex[:10].upper()
        if patient_id:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
        else:
            patient = Patient(mrn=f"MRN-{token}", full_name=f"Test Patient-{token}",
                              phone_number=f"98765{token[:5]}", age=30, gender="OTHER")
            db.add(patient)
            db.flush()
        encounter = Encounter(patient_id=patient.id, doctor_id=doctor_id,
                              chief_complaint="Synthetic test encounter", diagnosis="Synthetic test diagnosis",
                              status="FINALIZED")
        db.add(encounter)
        db.flush()
        invoice = Invoice(invoice_number=f"TST-C-{token}", patient_id=patient.id, encounter_id=encounter.id,
                          total_amount=100.00, discount_amount=10.00, net_payable=net,
                          paid_amount=0.00, payment_status="UNPAID")
        db.add(invoice)
        db.flush()
        db.add(InvoiceItem(invoice_id=invoice.id, item_type="CONSULTATION", description="Synthetic consultation",
                           quantity=1, unit_price=100.00, total_price=100.00))
        db.commit()
        return invoice.id
    finally:
        db.close()


def test_reconciliation_commission_refund_settlement_and_isolation():
    doctor_login = client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    assert doctor_login.status_code == 200
    doctor_id = doctor_login.json()["user_id"]
    other_login = client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    assert other_login.status_code == 200
    other_doctor_id = other_login.json()["user_id"]

    invoice_id = _commission_invoice(doctor_id)
    period = datetime.utcnow().strftime("%Y-%m")

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    rule = client.post("/api/commissions/rules", json={
        "idempotency_key": f"rule-{uuid4().hex}", "name": f"Synthetic 10 percent {uuid4().hex[:6]}", "doctor_id": doctor_id,
        "service_type": "CONSULTATION", "calculation_type": "PERCENTAGE", "rate": "10.0000",
        "effective_from": "2020-01-01"
    })
    assert rule.status_code == 201, rule.text

    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    payment_payload = {"invoice_id": invoice_id, "amount_paid": "45.00", "payment_method": "UPI",
                       "transaction_ref": f"TST-{uuid4().hex[:12]}", "idempotency_key": f"pay-{uuid4().hex}"}
    receipt = client.post("/api/billing/collect", json=payment_payload)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["payment_status"] == "PARTIAL"
    duplicate = client.post("/api/billing/collect", json=payment_payload)
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True

    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    before = client.get(f"/api/commissions/dashboard?period={period}")
    assert before.status_code == 200, before.text
    assert before.json()["pending_eligibility_estimate"] == "4.50"
    assert before.json()["earned"] == "0.00"
    isolated = client.get(f"/api/commissions/dashboard?period={period}&doctor_id={other_doctor_id}")
    assert isolated.status_code == 403

    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    payment_id = receipt.json()["payment_id"]
    reconciled = client.post(f"/api/billing/payments/{payment_id}/reconcile")
    assert reconciled.status_code == 200 and reconciled.json()["generated_entries"] == 1
    duplicate_reconcile = client.post(f"/api/billing/payments/{payment_id}/reconcile")
    assert duplicate_reconcile.status_code == 200 and duplicate_reconcile.json()["generated_entries"] == 0

    second_payload = {"invoice_id": invoice_id, "amount_paid": "45.00", "payment_method": "UPI",
                      "transaction_ref": f"TST-{uuid4().hex[:12]}", "idempotency_key": f"pay-{uuid4().hex}"}
    second = client.post("/api/billing/collect", json=second_payload)
    assert second.status_code == 200 and second.json()["payment_status"] == "PAID"
    second_payment_id = second.json()["payment_id"]
    assert client.post(f"/api/billing/payments/{second_payment_id}/reconcile").status_code == 200

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    refund = client.post(f"/api/billing/payments/{second_payment_id}/refund", json={
        "amount": "45.00", "reason": "Synthetic test refund", "reference": "TEST-REFUND",
        "idempotency_key": f"refund-{uuid4().hex}"
    })
    assert refund.status_code == 200, refund.text

    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    balance = client.get(f"/api/commissions/dashboard?period={period}").json()
    assert balance["earned"] == "9.00"
    assert balance["reversed"] == "4.50"
    assert balance["available"] == "4.50"
    too_much = client.post("/api/commissions/settlements", json={
        "period": period, "amount": "4.51", "idempotency_key": f"settle-{uuid4().hex}"
    })
    assert too_much.status_code == 409
    request = client.post("/api/commissions/settlements", json={
        "period": period, "amount": "4.50", "idempotency_key": f"settle-{uuid4().hex}"
    })
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    approved = client.post(f"/api/commissions/settlements/{request_id}/approve", json={"note": "Verified synthetic request"})
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    rows = client.get("/api/commissions/settlements?status=APPROVED").json()
    approved_row = next(row for row in rows if row["id"] == request_id)
    assert approved_row["payout"] is None
    payout = client.post(f"/api/commissions/settlements/{request_id}/payout", json={
        "payment_method": "BANK_TRANSFER", "payment_reference": f"TEST-PAYOUT-{uuid4().hex[:8]}",
        "idempotency_key": f"payout-{uuid4().hex}", "evidence_note": "Synthetic voucher verified"
    })
    assert payout.status_code == 200, payout.text
    assert client.post(f"/api/commissions/settlements/{request_id}/payout", json={
        "payment_method": "BANK_TRANSFER", "payment_reference": f"OTHER-{uuid4().hex[:8]}",
        "idempotency_key": f"payout-{uuid4().hex}", "evidence_note": "Retry must not duplicate"
    }).status_code == 409

    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    final_balance = client.get(f"/api/commissions/dashboard?period={period}").json()
    assert final_balance["available"] == "0.00"
    duplicate_settlement = client.post("/api/commissions/settlements", json={
        "period": period, "amount": "0.01", "idempotency_key": f"settle-{uuid4().hex}"
    })
    assert duplicate_settlement.status_code == 409


def test_effective_dated_rules_and_pending_receipts_are_not_eligible():
    second_doctor = client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"}).json()["user_id"]
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    future_rule = client.post("/api/commissions/rules", json={
        "idempotency_key": f"rule-{uuid4().hex}", "name": f"Future effective rule {uuid4().hex[:6]}", "doctor_id": second_doctor,
        "service_type": "CONSULTATION", "calculation_type": "PERCENTAGE", "rate": "50.0000",
        "effective_from": "2099-01-01"
    })
    assert future_rule.status_code == 201
    invoice_id = _commission_invoice(second_doctor)
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    receipt = client.post("/api/billing/collect", json={
        "invoice_id": invoice_id, "amount_paid": "90.00", "payment_method": "CASH",
        "idempotency_key": f"future-{uuid4().hex}"
    })
    assert receipt.status_code == 200
    pending_id = receipt.json()["payment_id"]
    assert client.post(f"/api/billing/payments/{pending_id}/reconcile").json()["generated_entries"] == 0

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    active_rule = client.post("/api/commissions/rules", json={
        "idempotency_key": f"rule-{uuid4().hex}", "name": f"Current effective rule {uuid4().hex[:6]}", "doctor_id": second_doctor,
        "service_type": "CONSULTATION", "calculation_type": "PERCENTAGE", "rate": "20.0000",
        "effective_from": "2020-01-01"
    })
    assert active_rule.status_code == 201
    invoice_id = _commission_invoice(second_doctor)
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    receipt = client.post("/api/billing/collect", json={
        "invoice_id": invoice_id, "amount_paid": "90.00", "payment_method": "CASH",
        "idempotency_key": f"active-{uuid4().hex}"
    })
    assert receipt.status_code == 200
    active_payment_id = receipt.json()["payment_id"]
    assert client.post(f"/api/billing/payments/{active_payment_id}/reconcile").json()["generated_entries"] == 1
    period = datetime.utcnow().strftime("%Y-%m")
    client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    dashboard = client.get(f"/api/commissions/dashboard?period={period}").json()
    assert dashboard["earned"] == "18.00"
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    adjustment = client.post("/api/commissions/adjustments", json={
        "doctor_id": second_doctor, "period": period, "amount": "2.50",
        "reason": "Synthetic approved correction fixture", "idempotency_key": f"adjust-{uuid4().hex}"
    })
    assert adjustment.status_code == 201, adjustment.text
    report = client.get(f"/api/commissions/reports/monthly?period={period}")
    assert report.status_code == 200 and report.json()["net_commission"] != "0.00"
    export = client.get(f"/api/commissions/reports/monthly.csv?period={period}")
    assert export.status_code == 200 and "Monthly Commission Finance Report" in export.text

    client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    request = client.post("/api/commissions/settlements", json={
        "period": period, "amount": "10.00", "idempotency_key": f"pre-refund-settlement-{uuid4().hex}"
    })
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert client.post(f"/api/commissions/settlements/{request_id}/approve", json={"note": "Synthetic approval"}).status_code == 200
    refund = client.post(f"/api/billing/payments/{active_payment_id}/refund", json={
        "amount": "90.00", "reason": "Synthetic refund after approval", "reference": "TEST-LATE-REFUND",
        "idempotency_key": f"late-refund-{uuid4().hex}"
    })
    assert refund.status_code == 200
    blocked_payout = client.post(f"/api/commissions/settlements/{request_id}/payout", json={
        "payment_method": "BANK_TRANSFER", "payment_reference": f"BLOCKED-{uuid4().hex[:8]}",
        "idempotency_key": f"blocked-payout-{uuid4().hex}", "evidence_note": "Must be blocked after reversal"
    })
    assert blocked_payout.status_code == 409
    cancelled = client.post(f"/api/commissions/settlements/{request_id}/cancel", json={"note": "Refund reduced the balance"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    client.post("/api/auth/login", json={"username": "dr.anita", "password": "doc123"})
    assert client.get(f"/api/commissions/dashboard?period={period}").json()["available"] == "2.50"


def test_settlement_reservations_are_concurrent_safe_and_rejections_release_funds():
    db = SessionLocal()
    doctor = db.query(User).filter(User.username == "dr.sharma").first()
    doctor_id = doctor.id
    period = datetime.utcnow().strftime("%Y-%m")
    token = uuid4().hex
    db.add(CommissionLedgerEntry(doctor_id=doctor_id, department=doctor.department,
        source_item_type="ADJUSTMENT", source_description="Concurrency fixture",
        invoice_number=f"TST-ADJ-{token[:10]}", period=period, entry_type="ADJUSTMENT",
        calculation_base=Decimal("10.00"), calculation_type="ADJUSTMENT", amount=Decimal("10.00"),
        status="AVAILABLE", generation_key=f"test-adjustment:{token}"))
    db.commit()
    db.close()

    def reserve(index):
        session = SessionLocal()
        try:
            request = create_settlement_request(session, doctor_id, period, Decimal("8.00"), f"thread-{token}-{index}")
            return ("created", request.id)
        except HTTPException as error:
            return ("rejected", error.status_code)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [1, 2]))
    assert sorted(result[0] for result in results) == ["created", "rejected"]
    request_id = next(result[1] for result in results if result[0] == "created")

    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    early_payout = client.post(f"/api/commissions/settlements/{request_id}/payout", json={
        "payment_method": "BANK_TRANSFER", "payment_reference": f"PENDING-{token[:8]}",
        "idempotency_key": f"payout-pending-{token}", "evidence_note": "Must not execute before approval"
    })
    assert early_payout.status_code == 409
    rejection = client.post(f"/api/commissions/settlements/{request_id}/reject", json={"note": "Synthetic test rejection"})
    assert rejection.status_code == 200 and rejection.json()["status"] == "REJECTED"

    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    replacement = client.post("/api/commissions/settlements", json={
        "period": period, "amount": "8.00", "idempotency_key": f"replacement-{token}"
    })
    assert replacement.status_code == 201, replacement.text


def test_doctor_cashier_and_finance_pages_render_commission_controls():
    client.post("/api/auth/login", json={"username": "dr.sharma", "password": "doc123"})
    doctor = client.get("/doctor")
    assert doctor.status_code == 200 and "doctorCommissionPanel" in doctor.text
    client.post("/api/auth/login", json={"username": "cashier.karan", "password": "cash123"})
    cashier = client.get("/billing")
    assert cashier.status_code == 200 and "cashierPaymentReconBody" in cashier.text
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    finance = client.get("/admin")
    assert finance.status_code == 200 and "financeCommissionPanel" in finance.text
