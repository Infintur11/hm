import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import calendar

# Ensure current folder is in Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.billing import Invoice, InvoiceItem
from app.models.clinical import Encounter
from app.models.patient import Patient
from app.models.user import User
from app.models.commission import (
    CommissionRule, CommissionLedgerEntry, Payment, PaymentAllocation,
    SettlementRequest, SettlementAllocation, SettlementPayout, CommissionAuditEvent
)
from app.services import commission_service as service


def seed_demo_data():
    db = SessionLocal()
    try:
        print("[DEMO_SEED] Initializing rich enterprise commission scenario data...")

        # 1. Fetch Doctors
        dr_sharma = db.query(User).filter(User.username == "dr.sharma").first()
        dr_anita = db.query(User).filter(User.username == "dr.anita").first()
        admin = db.query(User).filter(User.username == "admin").first()
        cashier = db.query(User).filter(User.username == "cashier.karan").first()

        if not dr_sharma or not dr_anita:
            print("[ERROR] Seed doctors not found. Ensure app seed has run.")
            return

        # 0. Clean prior demo data if exists to guarantee idempotency
        inv_numbers = ["INV-2026-5001", "INV-2026-5002", "INV-2026-5003", "INV-2026-5004", "INV-2026-5005", "INV-2026-4990"]
        existing_invs = db.query(Invoice).filter(Invoice.invoice_number.in_(inv_numbers)).all()
        existing_inv_ids = [inv.id for inv in existing_invs]
        # Delete prior settlement payouts, allocations, and requests for Dr. Sharma & Dr. Anita in current period
        curr_req_ids = [r.id for r in db.query(SettlementRequest).filter(
            SettlementRequest.doctor_id.in_([dr_sharma.id, dr_anita.id]),
            SettlementRequest.period == service.current_period()
        ).all()]
        if curr_req_ids:
            db.query(SettlementPayout).filter(SettlementPayout.request_id.in_(curr_req_ids)).delete(synchronize_session=False)
            db.query(SettlementAllocation).filter(SettlementAllocation.request_id.in_(curr_req_ids)).delete(synchronize_session=False)
            db.query(SettlementRequest).filter(SettlementRequest.id.in_(curr_req_ids)).delete(synchronize_session=False)
            db.commit()

        if existing_inv_ids:
            db.query(SettlementPayout).filter(SettlementPayout.idempotency_key == "demo-payout-deepak-300").delete(synchronize_session=False)
            db.query(SettlementAllocation).filter(SettlementAllocation.request_id.in_(
                db.query(SettlementRequest.id).filter(SettlementRequest.request_number == "SET-20261015-9988")
            )).delete(synchronize_session=False)
            db.query(SettlementRequest).filter(SettlementRequest.request_number == "SET-20261015-9988").delete(synchronize_session=False)
            db.query(CommissionLedgerEntry).filter(CommissionLedgerEntry.invoice_id.in_(existing_inv_ids)).delete(synchronize_session=False)
            db.query(PaymentAllocation).filter(PaymentAllocation.payment_id.in_(
                db.query(Payment.id).filter(Payment.invoice_id.in_(existing_inv_ids))
            )).delete(synchronize_session=False)
            db.query(Payment).filter(Payment.invoice_id.in_(existing_inv_ids)).delete(synchronize_session=False)
            db.query(InvoiceItem).filter(InvoiceItem.invoice_id.in_(existing_inv_ids)).delete(synchronize_session=False)
            enc_ids = [inv.encounter_id for inv in existing_invs if inv.encounter_id]
            db.query(Invoice).filter(Invoice.id.in_(existing_inv_ids)).delete(synchronize_session=False)
            if enc_ids:
                db.query(Encounter).filter(Encounter.id.in_(enc_ids)).delete(synchronize_session=False)
            db.commit()

        db.query(CommissionRule).filter(
            CommissionRule.idempotency_key.in_([
                "rule-sharma-consult-15", "rule-sharma-inpatient-500", "rule-anita-threshold-12"
            ])
        ).delete(synchronize_session=False)
        db.commit()

        db.query(Patient).filter(Patient.mrn.in_([
            "MRN-2026-0101", "MRN-2026-0102", "MRN-2026-0103", "MRN-2026-0104", "MRN-2026-0105"
        ])).delete(synchronize_session=False)
        db.commit()

        # 2. Setup Clean Rules for Dr. Sharma and Dr. Anita
        # Deactivate old demo rules
        db.query(CommissionRule).filter(
            CommissionRule.doctor_id.in_([dr_sharma.id, dr_anita.id])
        ).update({CommissionRule.active: False, CommissionRule.is_active: False}, synchronize_session=False)
        db.commit()

        # Rule 1: Dr. Sharma - Consultation 15%
        rule_sharma_consult = CommissionRule(
            idempotency_key="rule-sharma-consult-15",
            name="Cardiology Specialist Consultation (15%)",
            doctor_id=dr_sharma.id,
            department="Cardiology",
            service_type="CONSULTATION",
            calculation_type="PERCENTAGE",
            rate=Decimal("15.0000"),
            fixed_amount=None,
            require_all_patient_bills_paid=True,
            min_settlement_threshold=0.0,
            is_active=True,
            active=True,
            effective_from=date(2025, 1, 1),
            created_by_id=admin.id
        )

        # Rule 2: Dr. Sharma - Inpatient Stay Fixed ₹500
        rule_sharma_inpatient = CommissionRule(
            idempotency_key="rule-sharma-inpatient-500",
            name="Cardiology Inpatient Stay Rounding (₹500 Fixed/day)",
            doctor_id=dr_sharma.id,
            department="Cardiology",
            service_type="INPATIENT_STAY",
            calculation_type="FIXED",
            rate=Decimal("500.0000"),
            fixed_amount=Decimal("500.00"),
            require_all_patient_bills_paid=True,
            min_settlement_threshold=0.0,
            is_active=True,
            active=True,
            effective_from=date(2025, 1, 1),
            created_by_id=admin.id
        )

        # Rule 3: Dr. Anita - General Medicine with ₹8,000 Min Settlement Threshold
        rule_anita_consult = CommissionRule(
            idempotency_key="rule-anita-threshold-12",
            name="General Medicine Referral Program (12% - ₹8,000 Mo-End Target)",
            doctor_id=dr_anita.id,
            department="General Medicine",
            service_type="CONSULTATION",
            calculation_type="PERCENTAGE",
            rate=Decimal("12.0000"),
            fixed_amount=None,
            require_all_patient_bills_paid=True,
            min_settlement_threshold=8000.0,
            is_active=True,
            active=True,
            effective_from=date(2025, 1, 1),
            created_by_id=admin.id
        )

        db.add_all([rule_sharma_consult, rule_sharma_inpatient, rule_anita_consult])
        db.commit()
        db.refresh(rule_sharma_consult)
        db.refresh(rule_sharma_inpatient)
        db.refresh(rule_anita_consult)
        print("[DEMO_SEED] Created rules with invariant constraints.")

        # 3. Create Patients
        # Patient A: Ananya Gupta (Referred by Dr. Sharma -> Scenario: Ready to Pull)
        p_ananya = Patient(
            mrn="MRN-2026-0101",
            full_name="Ananya Gupta",
            phone_number="9811002233",
            age=34,
            gender="FEMALE",
            blood_group="O+",
            referred_by_doctor_id=dr_sharma.id
        )

        # Patient B: Vikram Malhotra (Referred by Dr. Sharma -> Scenario: Inpatient Stay Ready to Pull)
        p_vikram = Patient(
            mrn="MRN-2026-0102",
            full_name="Vikram Malhotra",
            phone_number="9822334455",
            age=52,
            gender="MALE",
            blood_group="A+",
            referred_by_doctor_id=dr_sharma.id
        )

        # Patient C: Ramesh Verma (Referred by Dr. Sharma -> Scenario: Locked due to unpaid bill)
        p_ramesh = Patient(
            mrn="MRN-2026-0103",
            full_name="Ramesh Verma",
            phone_number="9833445566",
            age=61,
            gender="MALE",
            blood_group="B+",
            referred_by_doctor_id=dr_sharma.id
        )

        # Patient D: Meera Kapoor (Referred by Dr. Anita -> Scenario: Early Month Threshold Lock)
        p_meera = Patient(
            mrn="MRN-2026-0104",
            full_name="Meera Kapoor",
            phone_number="9844556677",
            age=29,
            gender="FEMALE",
            blood_group="AB+",
            referred_by_doctor_id=dr_anita.id
        )

        # Patient E: Deepak Chopra (Referred by Dr. Sharma -> Scenario: Settled / Paid out)
        p_deepak = Patient(
            mrn="MRN-2026-0105",
            full_name="Deepak Chopra",
            phone_number="9855667788",
            age=47,
            gender="MALE",
            blood_group="O-",
            referred_by_doctor_id=dr_sharma.id
        )

        db.add_all([p_ananya, p_vikram, p_ramesh, p_meera, p_deepak])
        db.commit()
        for p in [p_ananya, p_vikram, p_ramesh, p_meera, p_deepak]:
            db.refresh(p)
        print("[DEMO_SEED] Created 5 clinical patients with verified doctor referrals.")

        period_current = service.current_period()

        # =========================================================================
        # Scenario 1: Ananya Gupta - Consultation Bill Paid in Full -> RELEASED [🔓 Ready to Pull]
        # =========================================================================
        enc_a = Encounter(patient_id=p_ananya.id, doctor_id=dr_sharma.id, chief_complaint="Cardiology follow-up", diagnosis="Atypical Chest Tightness", status="FINALIZED")
        db.add(enc_a)
        db.flush()
        inv_a = Invoice(invoice_number="INV-2026-5001", patient_id=p_ananya.id, encounter_id=enc_a.id,
                        total_amount=1200.0, discount_amount=0.0, net_payable=1200.0, paid_amount=1200.0, payment_status="PAID")
        db.add(inv_a)
        db.flush()
        item_a = InvoiceItem(invoice_id=inv_a.id, item_type="CONSULTATION", description="Senior Cardiologist OPD Consultation", quantity=1, unit_price=1200.0, total_price=1200.0)
        db.add(item_a)
        db.flush()

        pay_a = Payment(invoice_id=inv_a.id, amount=Decimal("1200.00"), payment_method="UPI", transaction_ref="UPI-AXIS-99210",
                        received_at=datetime.utcnow() - timedelta(hours=2), received_period=period_current,
                        received_by_id=cashier.id, idempotency_key=f"demo-pay-{inv_a.invoice_number}",
                        status="RECONCILED", reconciled_by_id=admin.id, reconciled_at=datetime.utcnow() - timedelta(hours=1),
                        reconciled_period=period_current)
        db.add(pay_a)
        db.flush()
        alloc_a = PaymentAllocation(payment_id=pay_a.id, invoice_item_id=item_a.id, amount=Decimal("1200.00"))
        db.add(alloc_a)
        db.flush()

        # Generate commission: 15% of 1200 = 180
        entry_a = CommissionLedgerEntry(
            doctor_id=dr_sharma.id, patient_id=p_ananya.id, invoice_id=inv_a.id, invoice_item_id=item_a.id,
            department="Cardiology", payment_id=pay_a.id, payment_allocation_id=alloc_a.id,
            rule_id=rule_sharma_consult.id, governing_rule_id=rule_sharma_consult.id,
            source_item_type="CONSULTATION", source_description="Senior Cardiologist OPD Consultation",
            invoice_number=inv_a.invoice_number, period=period_current, entry_type="COMMISSION",
            base_amount=1200.0, calculated_commission=180.0, calculation_base=Decimal("1200.00"),
            calculation_type="PERCENTAGE", rate=Decimal("15.0000"), amount=Decimal("180.00"),
            status="RELEASED", accrued_at=datetime.utcnow() - timedelta(hours=1), released_at=datetime.utcnow() - timedelta(minutes=50),
            generation_key=f"demo-entry-{inv_a.invoice_number}",
            execution_audit_log="All patient bills verified settled and monthly settlement threshold satisfied. Released for payout."
        )
        db.add(entry_a)
        print("[DEMO_SEED] Scenario 1 created: Ananya Gupta -> ₹180.00 RELEASED [🔓 Ready to Pull]")

        # =========================================================================
        # Scenario 2: Vikram Malhotra - Inpatient Stay Paid in Full -> RELEASED [🔓 Ready to Pull]
        # =========================================================================
        enc_b = Encounter(patient_id=p_vikram.id, doctor_id=dr_sharma.id, chief_complaint="Chest pain observation", diagnosis="Acute Coronary Observation", status="FINALIZED")
        db.add(enc_b)
        db.flush()
        inv_b = Invoice(invoice_number="INV-2026-5002", patient_id=p_vikram.id, encounter_id=enc_b.id,
                        total_amount=5000.0, discount_amount=0.0, net_payable=5000.0, paid_amount=5000.0, payment_status="PAID")
        db.add(inv_b)
        db.flush()
        item_b = InvoiceItem(invoice_id=inv_b.id, item_type="BED_CHARGE", description="Cardiology ICU Stay (Day 1)", quantity=1, unit_price=5000.0, total_price=5000.0)
        db.add(item_b)
        db.flush()

        pay_b = Payment(invoice_id=inv_b.id, amount=Decimal("5000.00"), payment_method="NETBANKING", transaction_ref="HDFC-NET-44810",
                        received_at=datetime.utcnow() - timedelta(hours=3), received_period=period_current,
                        received_by_id=cashier.id, idempotency_key=f"demo-pay-{inv_b.invoice_number}",
                        status="RECONCILED", reconciled_by_id=admin.id, reconciled_at=datetime.utcnow() - timedelta(hours=2),
                        reconciled_period=period_current)
        db.add(pay_b)
        db.flush()
        alloc_b = PaymentAllocation(payment_id=pay_b.id, invoice_item_id=item_b.id, amount=Decimal("5000.00"))
        db.add(alloc_b)
        db.flush()

        # Fixed commission: ₹500
        entry_b = CommissionLedgerEntry(
            doctor_id=dr_sharma.id, patient_id=p_vikram.id, invoice_id=inv_b.id, invoice_item_id=item_b.id,
            department="Cardiology", payment_id=pay_b.id, payment_allocation_id=alloc_b.id,
            rule_id=rule_sharma_inpatient.id, governing_rule_id=rule_sharma_inpatient.id,
            source_item_type="INPATIENT_STAY", source_description="Cardiology ICU Stay (Day 1)",
            invoice_number=inv_b.invoice_number, period=period_current, entry_type="COMMISSION",
            base_amount=5000.0, calculated_commission=500.0, calculation_base=Decimal("5000.00"),
            calculation_type="FIXED", rate=Decimal("500.0000"), amount=Decimal("500.00"),
            status="RELEASED", accrued_at=datetime.utcnow() - timedelta(hours=2), released_at=datetime.utcnow() - timedelta(minutes=45),
            generation_key=f"demo-entry-{inv_b.invoice_number}",
            execution_audit_log="All patient bills verified settled and monthly settlement threshold satisfied. Released for payout."
        )
        db.add(entry_b)
        print("[DEMO_SEED] Scenario 2 created: Vikram Malhotra -> ₹500.00 RELEASED [🔓 Ready to Pull]")

        # =========================================================================
        # Scenario 3: Ramesh Verma - Has Paid Invoice 1, but has UNPAID Invoice 2 -> ACCRUED [🔒 Waiting for Patient Bill Settlement]
        # =========================================================================
        enc_c1 = Encounter(patient_id=p_ramesh.id, doctor_id=dr_sharma.id, chief_complaint="Chest pain OPD", diagnosis="Hypertensive Evaluation", status="FINALIZED")
        db.add(enc_c1)
        db.flush()
        inv_c1 = Invoice(invoice_number="INV-2026-5003", patient_id=p_ramesh.id, encounter_id=enc_c1.id,
                         total_amount=800.0, discount_amount=0.0, net_payable=800.0, paid_amount=800.0, payment_status="PAID")
        db.add(inv_c1)
        db.flush()
        item_c1 = InvoiceItem(invoice_id=inv_c1.id, item_type="CONSULTATION", description="Consultation OPD Review", quantity=1, unit_price=800.0, total_price=800.0)
        db.add(item_c1)
        db.flush()

        pay_c1 = Payment(invoice_id=inv_c1.id, amount=Decimal("800.00"), payment_method="CASH", transaction_ref="CASH-REC-108",
                         received_at=datetime.utcnow() - timedelta(hours=4), received_period=period_current,
                         received_by_id=cashier.id, idempotency_key=f"demo-pay-{inv_c1.invoice_number}",
                         status="RECONCILED", reconciled_by_id=admin.id, reconciled_at=datetime.utcnow() - timedelta(hours=3),
                         reconciled_period=period_current)
        db.add(pay_c1)
        db.flush()
        alloc_c1 = PaymentAllocation(payment_id=pay_c1.id, invoice_item_id=item_c1.id, amount=Decimal("800.00"))
        db.add(alloc_c1)
        db.flush()

        # Ramesh Verma also has Invoice 2: Uncompleted / PARTIAL Bill of ₹2,500 (₹500 paid, ₹2,000 pending)
        enc_c2 = Encounter(patient_id=p_ramesh.id, doctor_id=dr_sharma.id, chief_complaint="Diagnostic cardiac workup", diagnosis="Suspected Angina", status="FINALIZED")
        db.add(enc_c2)
        db.flush()
        inv_c2 = Invoice(invoice_number="INV-2026-5004", patient_id=p_ramesh.id, encounter_id=enc_c2.id,
                         total_amount=2500.0, discount_amount=0.0, net_payable=2500.0, paid_amount=500.0, payment_status="PARTIAL")
        db.add(inv_c2)
        db.flush()
        item_c2 = InvoiceItem(invoice_id=inv_c2.id, item_type="PROCEDURE", description="Cardiac Stress Test (TMT)", quantity=1, unit_price=2500.0, total_price=2500.0)
        db.add(item_c2)
        db.flush()

        # Commission for Inv 1: 15% of 800 = 120. But because Inv 2 is PARTIAL, Invariant A holds it in ACCRUED!
        entry_c = CommissionLedgerEntry(
            doctor_id=dr_sharma.id, patient_id=p_ramesh.id, invoice_id=inv_c1.id, invoice_item_id=item_c1.id,
            department="Cardiology", payment_id=pay_c1.id, payment_allocation_id=alloc_c1.id,
            rule_id=rule_sharma_consult.id, governing_rule_id=rule_sharma_consult.id,
            source_item_type="CONSULTATION", source_description="Consultation OPD Review",
            invoice_number=inv_c1.invoice_number, period=period_current, entry_type="COMMISSION",
            base_amount=800.0, calculated_commission=120.0, calculation_base=Decimal("800.00"),
            calculation_type="PERCENTAGE", rate=Decimal("15.0000"), amount=Decimal("120.00"),
            status="ACCRUED", accrued_at=datetime.utcnow() - timedelta(hours=3), released_at=None,
            generation_key=f"demo-entry-{inv_c1.invoice_number}",
            execution_audit_log=f"Waiting for Patient Bill Settlement: Patient #{p_ramesh.id} ({p_ramesh.full_name}) has 1 unpaid bill(s) (INV-2026-5004: ₹2,000.00 unpaid). All patient bills must be settled before commission release."
        )
        db.add(entry_c)
        print("[DEMO_SEED] Scenario 3 created: Ramesh Verma -> ₹120.00 LOCKED [🔒 Waiting for Patient Bill Settlement]")

        # =========================================================================
        # Scenario 4: Meera Kapoor - All Bills Paid, but Below Month-End Threshold -> ACCRUED [🔒 Early Month Threshold Lock]
        # =========================================================================
        enc_d = Encounter(patient_id=p_meera.id, doctor_id=dr_anita.id, chief_complaint="Generalized fatigue", diagnosis="Vitamin D Deficiency & Malaise", status="FINALIZED")
        db.add(enc_d)
        db.flush()
        inv_d = Invoice(invoice_number="INV-2026-5005", patient_id=p_meera.id, encounter_id=enc_d.id,
                        total_amount=1500.0, discount_amount=0.0, net_payable=1500.0, paid_amount=1500.0, payment_status="PAID")
        db.add(inv_d)
        db.flush()
        item_d = InvoiceItem(invoice_id=inv_d.id, item_type="CONSULTATION", description="General Medicine Comprehensive Health Review", quantity=1, unit_price=1500.0, total_price=1500.0)
        db.add(item_d)
        db.flush()

        pay_d = Payment(invoice_id=inv_d.id, amount=Decimal("1500.00"), payment_method="UPI", transaction_ref="UPI-GPay-55910",
                        received_at=datetime.utcnow() - timedelta(hours=5), received_period=period_current,
                        received_by_id=cashier.id, idempotency_key=f"demo-pay-{inv_d.invoice_number}",
                        status="RECONCILED", reconciled_by_id=admin.id, reconciled_at=datetime.utcnow() - timedelta(hours=4),
                        reconciled_period=period_current)
        db.add(pay_d)
        db.flush()
        alloc_d = PaymentAllocation(payment_id=pay_d.id, invoice_item_id=item_d.id, amount=Decimal("1500.00"))
        db.add(alloc_d)
        db.flush()

        today = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
        _, last_day = calendar.monthrange(today.year, today.month)
        month_end = date(today.year, today.month, last_day)

        # 12% of 1500 = 180. But Dr. Anita's threshold is ₹8,000! Before month-end, Invariant B holds it in ACCRUED!
        entry_d = CommissionLedgerEntry(
            doctor_id=dr_anita.id, patient_id=p_meera.id, invoice_id=inv_d.id, invoice_item_id=item_d.id,
            department="General Medicine", payment_id=pay_d.id, payment_allocation_id=alloc_d.id,
            rule_id=rule_anita_consult.id, governing_rule_id=rule_anita_consult.id,
            source_item_type="CONSULTATION", source_description="General Medicine Comprehensive Health Review",
            invoice_number=inv_d.invoice_number, period=period_current, entry_type="COMMISSION",
            base_amount=1500.0, calculated_commission=180.0, calculation_base=Decimal("1500.00"),
            calculation_type="PERCENTAGE", rate=Decimal("12.0000"), amount=Decimal("180.00"),
            status="ACCRUED", accrued_at=datetime.utcnow() - timedelta(hours=4), released_at=None,
            generation_key=f"demo-entry-{inv_d.invoice_number}",
            execution_audit_log=f"Early Month Threshold Lock: Current date ({today.strftime('%d %b %Y')}) is before month-end ({month_end.strftime('%d %b %Y')}) and doctor's monthly accrued commission (₹180.00) is below the required minimum threshold of ₹8,000.00."
        )
        db.add(entry_d)
        print("[DEMO_SEED] Scenario 4 created: Meera Kapoor -> ₹180.00 LOCKED [🔒 Early Month Threshold Lock]")

        # =========================================================================
        # Scenario 5: Deepak Chopra - Settled Prior Month Commission -> SETTLED [✓ Settled]
        # =========================================================================
        enc_e = Encounter(patient_id=p_deepak.id, doctor_id=dr_sharma.id, chief_complaint="Post-procedure checkup", diagnosis="Cardiovascular Clearance", status="FINALIZED")
        db.add(enc_e)
        db.flush()
        inv_e = Invoice(invoice_number="INV-2026-4990", patient_id=p_deepak.id, encounter_id=enc_e.id,
                        total_amount=2000.0, discount_amount=0.0, net_payable=2000.0, paid_amount=2000.0, payment_status="PAID")
        db.add(inv_e)
        db.flush()
        item_e = InvoiceItem(invoice_id=inv_e.id, item_type="CONSULTATION", description="Senior Cardiologist Detailed Review", quantity=1, unit_price=2000.0, total_price=2000.0)
        db.add(item_e)
        db.flush()

        prev_period = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        pay_e = Payment(invoice_id=inv_e.id, amount=Decimal("2000.00"), payment_method="CARD", transaction_ref="POS-VISA-88120",
                        received_at=datetime.utcnow() - timedelta(days=20), received_period=prev_period,
                        received_by_id=cashier.id, idempotency_key=f"demo-pay-{inv_e.invoice_number}",
                        status="RECONCILED", reconciled_by_id=admin.id, reconciled_at=datetime.utcnow() - timedelta(days=19),
                        reconciled_period=prev_period)
        db.add(pay_e)
        db.flush()
        alloc_e = PaymentAllocation(payment_id=pay_e.id, invoice_item_id=item_e.id, amount=Decimal("2000.00"))
        db.add(alloc_e)
        db.flush()

        # 15% of 2000 = 300
        entry_e = CommissionLedgerEntry(
            doctor_id=dr_sharma.id, patient_id=p_deepak.id, invoice_id=inv_e.id, invoice_item_id=item_e.id,
            department="Cardiology", payment_id=pay_e.id, payment_allocation_id=alloc_e.id,
            rule_id=rule_sharma_consult.id, governing_rule_id=rule_sharma_consult.id,
            source_item_type="CONSULTATION", source_description="Senior Cardiologist Detailed Review",
            invoice_number=inv_e.invoice_number, period=prev_period, entry_type="COMMISSION",
            base_amount=2000.0, calculated_commission=300.0, calculation_base=Decimal("2000.00"),
            calculation_type="PERCENTAGE", rate=Decimal("15.0000"), amount=Decimal("300.00"),
            status="SETTLED", accrued_at=datetime.utcnow() - timedelta(days=19), released_at=datetime.utcnow() - timedelta(days=18),
            generation_key=f"demo-entry-{inv_e.invoice_number}",
            execution_audit_log="Commission disbursed and settled via IMPS / UTR-20261015123000-AXIS99."
        )
        db.add(entry_e)
        db.flush()

        # Settlement Request and Payout
        settle_req = SettlementRequest(
            request_number="SET-20261015-9988",
            doctor_id=dr_sharma.id,
            period=prev_period,
            amount=Decimal("300.00"),
            status="PAID",
            idempotency_key="demo-settle-deepak-300",
            requested_at=datetime.utcnow() - timedelta(days=17),
            decided_at=datetime.utcnow() - timedelta(days=16),
            decided_by_id=admin.id,
            decision_note="Approved by Chief Finance Officer"
        )
        db.add(settle_req)
        db.flush()

        db.add(SettlementAllocation(request_id=settle_req.id, ledger_entry_id=entry_e.id, amount=Decimal("300.00"), status="PAID"))

        payout = SettlementPayout(
            request_id=settle_req.id,
            amount=Decimal("300.00"),
            payment_method="BANK_TRANSFER",
            payment_reference="UTR-20261015123000-AXIS99",
            idempotency_key="demo-payout-deepak-300",
            paid_at=datetime.utcnow() - timedelta(days=15),
            paid_period=prev_period,
            recorded_by_id=admin.id,
            evidence_note="Hospital SBI corporate settlement verified"
        )
        db.add(payout)
        print("[DEMO_SEED] Scenario 5 created: Deepak Chopra -> ₹300.00 SETTLED [✓ Settled] (UTR: UTR-20261015123000-AXIS99)")

        db.commit()
        print("\n============================================================")
        print("[SUCCESS] All rich enterprise commission scenarios populated!")
        print("  - Dr. Sharma Ready to Pull: ₹680.00 (Ananya ₹180 + Vikram ₹500)")
        print("  - Dr. Sharma Locked on Bill: ₹120.00 (Ramesh Verma pending INV-2026-5004)")
        print("  - Dr. Anita Early Month Lock: ₹180.00 (Meera Kapoor pending ₹8,000 threshold)")
        print("  - Dr. Sharma Historical Settled: ₹300.00 (Deepak Chopra, UTR verified)")
        print("============================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
