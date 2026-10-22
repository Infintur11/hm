import datetime
from app.core.database import SessionLocal
from app.models.corporate import CorporateClient
from app.models.billing import Invoice, InvoiceItem
from app.models.patient import Patient

def seed_invoices():
    db = SessionLocal()
    try:
        corps = {c.code: c for c in db.query(CorporateClient).all()}
        if not corps:
            print("No corporate clients found!")
            return

        patients = db.query(Patient).all()
        if not patients:
            print("No patients found!")
            return

        p_map = {p.id: p for p in patients}
        # Fallback patient id if needed
        p1 = patients[0].id
        p2 = patients[1].id if len(patients) > 1 else p1
        p3 = patients[2].id if len(patients) > 2 else p1
        p5 = patients[4].id if len(patients) > 4 else p1
        p6 = patients[5].id if len(patients) > 5 else p1
        p7 = patients[6].id if len(patients) > 6 else p1
        p8 = patients[7].id if len(patients) > 7 else p1
        p9 = patients[8].id if len(patients) > 8 else p1

        # Check existing corporate invoices
        existing_corp_invs = db.query(Invoice).filter(Invoice.billing_type == "CORPORATE_TIEUP").count()
        if existing_corp_invs > 0:
            print(f"Already have {existing_corp_invs} corporate invoices.")
            return

        print("Seeding 15 reconciled corporate billed invoices...")

        corp_bills_spec = [
            # 1. CGHS (Total = 145,000)
            {
                "corp_code": "CGHS-GOVT-05",
                "inv_num": "INV-2026-6001",
                "patient_id": p9,
                "amount": 65000.0,
                "policy_id": "CGHS-DEL-89912",
                "items": [
                    ("PROCEDURE", "Major Cardiac Intervention & Stenting", 1, 45000.0),
                    ("BED_CHARGE", "Cardiac ICU Bed Charges (4 Days)", 4, 5000.0)
                ]
            },
            {
                "corp_code": "CGHS-GOVT-05",
                "inv_num": "INV-2026-6002",
                "patient_id": p8,
                "amount": 38000.0,
                "policy_id": "CGHS-DEL-44120",
                "items": [
                    ("BED_CHARGE", "Semi-Private Ward Multi-Day Recovery (10 Days)", 10, 2200.0),
                    ("PHARMACY", "Injectable Ceftriaxone & IV Infusions", 1, 16000.0)
                ]
            },
            {
                "corp_code": "CGHS-GOVT-05",
                "inv_num": "INV-2026-6003",
                "patient_id": p6,
                "amount": 22000.0,
                "policy_id": "CGHS-DEL-98110",
                "items": [
                    ("LAB_TEST", "Comprehensive Oncology Panel & Tumor Markers", 1, 14000.0),
                    ("LAB_TEST", "Contrast CT Scan Thorax & Abdomen", 1, 8000.0)
                ]
            },
            {
                "corp_code": "CGHS-GOVT-05",
                "inv_num": "INV-2026-6004",
                "patient_id": p7,
                "amount": 12000.0,
                "policy_id": "CGHS-DEL-33215",
                "items": [
                    ("PROCEDURE", "Hemodialysis Session & Vascular Access", 2, 4500.0),
                    ("CONSULTATION", "Super-Specialty Nephrology Consultation", 3, 1000.0)
                ]
            },
            {
                "corp_code": "CGHS-GOVT-05",
                "inv_num": "INV-2026-6005",
                "patient_id": p5,
                "amount": 8000.0,
                "policy_id": "CGHS-DEL-11209",
                "items": [
                    ("PROCEDURE", "Emergency Observation & IV Hydration Support", 1, 5500.0),
                    ("PHARMACY", "Emergency Formulary Medications", 1, 2500.0)
                ]
            },

            # 2. ICICI Lombard (Total = 85,000)
            {
                "corp_code": "ICICI-LOMB-03",
                "inv_num": "INV-2026-6006",
                "patient_id": p1,
                "amount": 48000.0,
                "policy_id": "ICICI-MED-55011",
                "items": [
                    ("PROCEDURE", "Laparoscopic Cholecystectomy Surgery", 1, 36000.0),
                    ("BED_CHARGE", "Private Deluxe Room Post-Op (3 Days)", 3, 4000.0)
                ]
            },
            {
                "corp_code": "ICICI-LOMB-03",
                "inv_num": "INV-2026-6007",
                "patient_id": p2,
                "amount": 25000.0,
                "policy_id": "ICICI-MED-33902",
                "items": [
                    ("PROCEDURE", "Elective Coronary Angiography", 1, 20000.0),
                    ("BED_CHARGE", "Day-Care Observation Bed", 1, 5000.0)
                ]
            },
            {
                "corp_code": "ICICI-LOMB-03",
                "inv_num": "INV-2026-6008",
                "patient_id": p3,
                "amount": 12000.0,
                "policy_id": "ICICI-MED-77114",
                "items": [
                    ("LAB_TEST", "HRCT Chest & Pulmonary Function Panel", 1, 8500.0),
                    ("PHARMACY", "Pulmonary Bronchodilators & Nebulizers", 1, 3500.0)
                ]
            },

            # 3. Star Health (Total = 62,500)
            {
                "corp_code": "STAR-HLTH-01",
                "inv_num": "INV-2026-6009",
                "patient_id": p9,
                "amount": 35000.0,
                "policy_id": "STAR-POL-2026-9912",
                "items": [
                    ("PROCEDURE", "Orthopedic Arthroscopy & Ligament Reconstruction", 1, 25000.0),
                    ("BED_CHARGE", "Semi-Private Ward (4 Days)", 4, 2500.0)
                ]
            },
            {
                "corp_code": "STAR-HLTH-01",
                "inv_num": "INV-2026-6010",
                "patient_id": p5,
                "amount": 18500.0,
                "policy_id": "STAR-POL-2026-4411",
                "items": [
                    ("BED_CHARGE", "Pediatric Ward Inpatient Care (5 Days)", 5, 2200.0),
                    ("PHARMACY", "Pediatric Antibiotics & Inhalers", 1, 7500.0)
                ]
            },
            {
                "corp_code": "STAR-HLTH-01",
                "inv_num": "INV-2026-6011",
                "patient_id": p8,
                "amount": 9000.0,
                "policy_id": "STAR-POL-2026-2209",
                "items": [
                    ("BED_CHARGE", "Emergency Gastro Ward Admission", 2, 2200.0),
                    ("PHARMACY", "Antiemetics & Proton Pump Inhibitors", 1, 4600.0)
                ]
            },

            # 4. Tata AIG (Total = 41,200)
            {
                "corp_code": "TATA-AIG-02",
                "inv_num": "INV-2026-6012",
                "patient_id": p6,
                "amount": 28200.0,
                "policy_id": "TATA-CORP-8812",
                "items": [
                    ("BED_CHARGE", "General Ward Dengue Monitoring (6 Days)", 6, 1200.0),
                    ("PHARMACY", "Platelet Transfusions & Electrolytes", 1, 21000.0)
                ]
            },
            {
                "corp_code": "TATA-AIG-02",
                "inv_num": "INV-2026-6013",
                "patient_id": p7,
                "amount": 13000.0,
                "policy_id": "TATA-CORP-4401",
                "items": [
                    ("LAB_TEST", "Neurology MRI Brain & Cervical Spine", 1, 10500.0),
                    ("CONSULTATION", "Senior Neurologist Consultation", 1, 2500.0)
                ]
            },

            # 5. Tech Mahindra (Total = 28,000)
            {
                "corp_code": "TECH-MAH-04",
                "inv_num": "INV-2026-6014",
                "patient_id": p2,
                "amount": 16000.0,
                "policy_id": "TECHM-EMP-4091",
                "items": [
                    ("LAB_TEST", "Executive Health Checkup Package", 1, 12000.0),
                    ("LAB_TEST", "Cardiovascular Treadmill Stress Test (TMT)", 1, 4000.0)
                ]
            },
            {
                "corp_code": "TECH-MAH-04",
                "inv_num": "INV-2026-6015",
                "patient_id": p1,
                "amount": 12000.0,
                "policy_id": "TECHM-EMP-8822",
                "items": [
                    ("PROCEDURE", "Orthopedic Fracture Immobilization & POP Cast", 1, 9500.0),
                    ("LAB_TEST", "Digital Orthopedic X-Ray Extremity", 1, 2500.0)
                ]
            }
        ]

        total_seeded = 0.0
        for spec in corp_bills_spec:
            corp = corps.get(spec["corp_code"])
            if not corp:
                continue

            inv = Invoice(
                invoice_number=spec["inv_num"],
                patient_id=spec["patient_id"],
                total_amount=spec["amount"],
                discount_amount=0.0,
                net_payable=spec["amount"],
                paid_amount=spec["amount"],
                payment_status="PAID",
                payment_method="INSURANCE",
                transaction_ref=f"CORP-CLAIM-{spec['inv_num'][-4:]}",
                billing_type="CORPORATE_TIEUP",
                corporate_client_id=corp.id,
                corporate_policy_id=spec["policy_id"],
                corporate_claim_amount=spec["amount"],
                corporate_claim_status="APPROVED",
                created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
            )
            db.add(inv)
            db.flush()

            for item_type, desc, qty, price in spec["items"]:
                inv_item = InvoiceItem(
                    invoice_id=inv.id,
                    item_type=item_type,
                    description=desc,
                    quantity=qty,
                    unit_price=price,
                    total_price=qty * price
                )
                db.add(inv_item)

            total_seeded += spec["amount"]

        db.commit()
        print(f"Successfully seeded {len(corp_bills_spec)} corporate invoices totaling Rs.{total_seeded:,.2f}!")

    finally:
        db.close()

if __name__ == "__main__":
    seed_invoices()
