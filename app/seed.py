import json
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models.user import User
from app.models.patient import Patient
from app.models.inpatient import Bed
from app.models.lab import LabTestTemplate
from app.models.pharmacy import Medicine
from app.models.clinical import TreatmentTemplate
from app.models.appointment import Appointment
from app.models.corporate import CorporateClient, CustomDashboardKpi
import datetime

def seed_corporate_clients(db: Session):
    if db.query(CorporateClient).count() == 0:
        clients = [
            CorporateClient(
                name="Star Health & Allied Insurance",
                code="STAR-HLTH-01",
                category="INSURANCE_TPA",
                monthly_credit_limit=500000.0,
                current_utilized_credit=62500.0,
                contact_person="Rohan Deshmukh (TPA Desk)",
                contact_phone="+91 98221 44332",
                contact_email="claims@starhealth-hospital.in",
                notes="Standard cashless TPA tie-up. Pre-auth within 2 hours.",
                is_active=True
            ),
            CorporateClient(
                name="Tata AIG General Insurance",
                code="TATA-AIG-02",
                category="INSURANCE_TPA",
                monthly_credit_limit=450000.0,
                current_utilized_credit=41200.0,
                contact_person="Sneha Pillai",
                contact_phone="+91 97112 55443",
                contact_email="provider@tataaig.com",
                notes="Direct corporate settlement. Claims submitted bi-weekly.",
                is_active=True
            ),
            CorporateClient(
                name="ICICI Lombard Health Care",
                code="ICICI-LOMB-03",
                category="INSURANCE_TPA",
                monthly_credit_limit=600000.0,
                current_utilized_credit=85000.0,
                contact_person="Amitabh Roy",
                contact_phone="+91 98334 66778",
                contact_email="claims@icicilombard.org",
                notes="Priority cashless network hospital agreement.",
                is_active=True
            ),
            CorporateClient(
                name="Tech Mahindra Corporate Account",
                code="TECH-MAH-04",
                category="CORPORATE_TIEUP",
                monthly_credit_limit=350000.0,
                current_utilized_credit=28000.0,
                contact_person="Pooja Batra (HR Wellness)",
                contact_phone="+91 98110 99887",
                contact_email="healthdesk@techmahindra.com",
                notes="Annual employee health & OPD credit benefit.",
                is_active=True
            ),
            CorporateClient(
                name="CGHS Central Govt Health Scheme",
                code="CGHS-GOVT-05",
                category="GOVERNMENT_SCHEME",
                monthly_credit_limit=1000000.0,
                current_utilized_credit=145000.0,
                contact_person="Dr. K. N. Rao (Scheme Nodal)",
                contact_phone="+91 94112 33445",
                contact_email="nodal@cghs.nic.in",
                notes="Government beneficiary scheme. Standard CGHS rate tariff.",
                is_active=True
            )
        ]
        db.add_all(clients)
        db.commit()

def seed_database():
    init_db()
    db: Session = SessionLocal()
    try:
        seed_corporate_clients(db)
        # Check if users already seeded
        if db.query(User).count() > 0:
            return

        print("[SEED] Seeding City Hospital Enterprise Master Data...")

        # 1. Staff Users
        users = [
            User(username="superadmin", email="superadmin@aegishealth.org", hashed_password=hash_password("super123"), full_name="Master Super Administrator", role="SUPER_ADMIN", department="Executive System Management", consultation_fee=0),
            User(username="admin", email="admin@aegishealth.org", hashed_password=hash_password("admin123"), full_name="Dr. Vikram Roy", role="ADMIN", department="Hospital Administration", consultation_fee=0),
            User(username="dr.sharma", email="dr.sharma@aegishealth.org", hashed_password=hash_password("doc123"), full_name="Dr. Rajesh Sharma", role="DOCTOR", department="Cardiology", consultation_fee=800),
            User(username="dr.anita", email="dr.anita@aegishealth.org", hashed_password=hash_password("doc123"), full_name="Dr. Anita Desai", role="DOCTOR", department="General Medicine", consultation_fee=500),
            User(username="nurse.mary", email="nurse.mary@aegishealth.org", hashed_password=hash_password("nurse123"), full_name="Nurse Mary Joseph", role="NURSE", department="Inpatient Wards", consultation_fee=0),
            User(username="pharma.kumar", email="pharma.kumar@aegishealth.org", hashed_password=hash_password("pharma123"), full_name="Sunil Kumar", role="PHARMACIST", department="Central Dispensary", consultation_fee=0),
            User(username="lab.john", email="lab.john@aegishealth.org", hashed_password=hash_password("lab123"), full_name="John Doe", role="LAB_TECH", department="Pathology & Diagnostics", consultation_fee=0),
            User(username="recep.riya", email="recep.riya@aegishealth.org", hashed_password=hash_password("recep123"), full_name="Riya Sen", role="RECEPTIONIST", department="Front-Desk & OPD Registration", consultation_fee=0),
            User(username="cashier.karan", email="cashier.karan@aegishealth.org", hashed_password=hash_password("cash123"), full_name="Karan Cashier", role="CASHIER", department="Billing & Cashier Settlements", consultation_fee=0),
        ]
        db.add_all(users)
        db.commit()

        # 2. Hospital Beds
        beds = [
            Bed(bed_number="GEN-101", ward_name="General Ward A", bed_type="GENERAL", daily_rate=1200, status="VACANT"),
            Bed(bed_number="GEN-102", ward_name="General Ward A", bed_type="GENERAL", daily_rate=1200, status="VACANT"),
            Bed(bed_number="GEN-103", ward_name="General Ward A", bed_type="GENERAL", daily_rate=1200, status="CLEANING"),
            Bed(bed_number="GEN-104", ward_name="General Ward A", bed_type="GENERAL", daily_rate=1200, status="VACANT"),
            Bed(bed_number="ICU-01", ward_name="Cardiology ICU", bed_type="ICU", daily_rate=5000, status="VACANT"),
            Bed(bed_number="ICU-02", ward_name="Cardiology ICU", bed_type="ICU", daily_rate=5000, status="VACANT"),
            Bed(bed_number="PED-201", ward_name="Pediatric Ward", bed_type="SEMI_PRIVATE", daily_rate=2200, status="VACANT"),
            Bed(bed_number="PED-202", ward_name="Pediatric Ward", bed_type="SEMI_PRIVATE", daily_rate=2200, status="VACANT"),
            Bed(bed_number="PVT-301", ward_name="Deluxe Suite", bed_type="PRIVATE", daily_rate=4000, status="VACANT"),
            Bed(bed_number="PVT-302", ward_name="Deluxe Suite", bed_type="PRIVATE", daily_rate=4000, status="VACANT"),
        ]
        db.add_all(beds)
        db.commit()

        # 3. Lab Test Templates
        lab_templates = [
            LabTestTemplate(test_code="CBC", test_name="Complete Blood Count (CBC)", department="Hematology", sample_type="Whole Blood (EDTA)", standard_rate=350, normal_range="13.5 - 17.5", unit_of_measurement="g/dL"),
            LabTestTemplate(test_code="LIPID", test_name="Lipid Profile", department="Biochemistry", sample_type="Serum", standard_rate=750, normal_range="< 200", unit_of_measurement="mg/dL"),
            LabTestTemplate(test_code="KFT", test_name="Kidney Function Test (KFT)", department="Biochemistry", sample_type="Serum", standard_rate=600, normal_range="0.7 - 1.3", unit_of_measurement="mg/dL"),
            LabTestTemplate(test_code="XRAY_CHEST", test_name="Chest X-Ray (PA View)", department="Radiology", sample_type="Radiology Image", standard_rate=500, normal_range="Normal lung fields", unit_of_measurement="Scan"),
            LabTestTemplate(test_code="FBS", test_name="Fasting Blood Sugar", department="Biochemistry", sample_type="Fluoride Blood", standard_rate=150, normal_range="70 - 99", unit_of_measurement="mg/dL"),
            LabTestTemplate(test_code="URINE_RE", test_name="Urine Routine Examination", department="Pathology", sample_type="Urine Sample", standard_rate=200, normal_range="Nil protein / sugar", unit_of_measurement="Microscopic"),
        ]
        db.add_all(lab_templates)
        db.commit()

        # 4. Medicines Formulary
        medicines = [
            Medicine(brand_name="Dolo 650", generic_name="Paracetamol", category="Antipyretic / Analgesic", dosage_form="Tablet", strength="650 mg", stock_quantity=500, reorder_level=50, unit_price=4.5, batch_number="BAT-DOLO-89", expiry_date="2027-12"),
            Medicine(brand_name="Augmentin 625", generic_name="Amoxicillin + Clavulanic Acid", category="Antibiotic", dosage_form="Tablet", strength="625 mg", stock_quantity=180, reorder_level=30, unit_price=22.0, batch_number="BAT-AUG-11", expiry_date="2027-08"),
            Medicine(brand_name="Pantocid 40", generic_name="Pantoprazole", category="Antacid / PPI", dosage_form="Tablet", strength="40 mg", stock_quantity=400, reorder_level=40, unit_price=12.0, batch_number="BAT-PAN-05", expiry_date="2028-01"),
            Medicine(brand_name="Azithral 500", generic_name="Azithromycin", category="Antibiotic", dosage_form="Tablet", strength="500 mg", stock_quantity=150, reorder_level=25, unit_price=25.0, batch_number="BAT-AZI-99", expiry_date="2027-10"),
            Medicine(brand_name="Telma 40", generic_name="Telmisartan", category="Cardiovascular / Antihypertensive", dosage_form="Tablet", strength="40 mg", stock_quantity=300, reorder_level=30, unit_price=14.0, batch_number="BAT-TEL-44", expiry_date="2028-04"),
            Medicine(brand_name="Metformin 500", generic_name="Metformin Hydrochloride", category="Antidiabetic", dosage_form="Tablet", strength="500 mg", stock_quantity=450, reorder_level=50, unit_price=6.0, batch_number="BAT-MET-77", expiry_date="2028-02"),
            Medicine(brand_name="Ascoril-D", generic_name="Dextromethorphan + Phenylephrine", category="Cough Syrup", dosage_form="Syrup", strength="100 ml", stock_quantity=90, reorder_level=15, unit_price=110.0, batch_number="BAT-ASC-22", expiry_date="2027-05"),
            Medicine(brand_name="Adrenaline 1mg", generic_name="Epinephrine", category="Emergency / Critical Care", dosage_form="Injection", strength="1 mg/ml", stock_quantity=8, reorder_level=20, unit_price=45.0, batch_number="BAT-ADR-01", expiry_date="2027-04"),
            Medicine(brand_name="Insulin Glargine", generic_name="Insulin Glargine (rDNA)", category="Antidiabetic / Injectable", dosage_form="Cartridge", strength="100 IU/ml", stock_quantity=14, reorder_level=25, unit_price=480.0, batch_number="BAT-INS-12", expiry_date="2027-09"),
            Medicine(brand_name="Ceftriaxone 1g", generic_name="Ceftriaxone Sodium", category="Antibiotic", dosage_form="Injection", strength="1000 mg", stock_quantity=24, reorder_level=30, unit_price=85.0, batch_number="BAT-CEF-91", expiry_date="2027-11"),
            Medicine(brand_name="Normal Saline 500ml", generic_name="Sodium Chloride 0.9%", category="IV Fluids", dosage_form="Infusion Bottle", strength="500 ml", stock_quantity=85, reorder_level=30, unit_price=55.0, batch_number="BAT-NS-33", expiry_date="2028-06"),
            Medicine(brand_name="Salbutamol Inhaler", generic_name="Salbutamol Sulfate", category="Respiratory", dosage_form="Inhaler", strength="100 mcg/dose", stock_quantity=35, reorder_level=15, unit_price=160.0, batch_number="BAT-SAL-55", expiry_date="2027-12"),
        ]
        db.add_all(medicines)
        db.commit()

        # 5. Treatment Plan Templates (SOAP 1-Click presets)
        templates = [
            TreatmentTemplate(
                name="Acute Viral Fever Protocol",
                department="General Medicine",
                diagnosis="Acute Febrile Illness / Viral Fever",
                icd10_code="A99",
                default_complaint="High fever with chills, body ache, and generalized weakness for 3 days.",
                default_rx_json=json.dumps([
                    {"medicine_name": "Dolo 650", "dosage": "650 mg", "frequency": "1-0-1", "duration_days": 3, "instructions": "After Food", "quantity": 6},
                    {"medicine_name": "Pantocid 40", "dosage": "40 mg", "frequency": "1-0-0", "duration_days": 3, "instructions": "Before Breakfast", "quantity": 3}
                ]),
                default_labs_json=json.dumps([1]) # CBC template ID
            ),
            TreatmentTemplate(
                name="Upper Respiratory Tract Infection (URTI)",
                department="General Medicine",
                diagnosis="Acute Upper Respiratory Tract Infection",
                icd10_code="J06.9",
                default_complaint="Persistent dry cough, sore throat, and nasal congestion for 4 days.",
                default_rx_json=json.dumps([
                    {"medicine_name": "Azithral 500", "dosage": "500 mg", "frequency": "1-0-0", "duration_days": 3, "instructions": "After Food", "quantity": 3},
                    {"medicine_name": "Ascoril-D", "dosage": "10 ml", "frequency": "0-0-1", "duration_days": 5, "instructions": "At Bedtime", "quantity": 1}
                ]),
                default_labs_json=json.dumps([1, 4]) # CBC and Chest X-ray
            ),
            TreatmentTemplate(
                name="Hypertension Routine Assessment",
                department="Cardiology",
                diagnosis="Essential Primary Hypertension",
                icd10_code="I10",
                default_complaint="Occasional morning headache, palpitation, and routine BP check.",
                default_rx_json=json.dumps([
                    {"medicine_name": "Telma 40", "dosage": "40 mg", "frequency": "1-0-0", "duration_days": 30, "instructions": "Morning after breakfast", "quantity": 30}
                ]),
                default_labs_json=json.dumps([2, 3]) # Lipid Profile & KFT
            )
        ]
        db.add_all(templates)
        db.commit()

        # 6. Demo Patients
        patients = [
            Patient(mrn="MRN-2026-0001", full_name="Blake Smith", phone_number="9811223344", aadhar_card_no="123456789012", age=42, gender="MALE", blood_group="O+", allergies="Penicillin (Rash)", chronic_conditions="Mild Hypertension", emergency_contact_name="Sarah Smith (Wife)", emergency_contact_phone="9811223345", address="Apartment 4B, Pinecrest Towers, New Delhi"),
            Patient(mrn="MRN-2026-0002", full_name="Priya Nair", phone_number="9876543210", aadhar_card_no="234567890123", age=28, gender="FEMALE", blood_group="B+", allergies="None reported", chronic_conditions="None", emergency_contact_name="Karthik Nair (Brother)", emergency_contact_phone="9876543211", address="Villa 12, Green Glen Layout, Bangalore"),
            Patient(mrn="MRN-2026-0003", full_name="Ramesh Verma", phone_number="9123456789", aadhar_card_no="345678901234", age=58, gender="MALE", blood_group="A+", allergies="Sulfa drugs", chronic_conditions="Type 2 Diabetes Mellitus, Hyperlipidemia", emergency_contact_name="Anita Verma (Wife)", emergency_contact_phone="9123456780", address="House 88, Sector 14, Gurgaon"),
        ]
        db.add_all(patients)
        db.commit()

        # 7. Today's Sample Appointments
        today_str = datetime.date.today().isoformat()
        doctor_sharma = db.query(User).filter(User.username == "dr.sharma").first()
        doctor_anita = db.query(User).filter(User.username == "dr.anita").first()
        p1 = db.query(Patient).filter(Patient.mrn == "MRN-2026-0001").first()
        p2 = db.query(Patient).filter(Patient.mrn == "MRN-2026-0002").first()

        appts = [
            Appointment(patient_id=p1.id, doctor_id=doctor_sharma.id, department="Cardiology", appointment_date=today_str, time_slot="09:00 - 09:15", token_number=101, status="CHECKED_IN", reason_for_visit="Routine Chest Tightness & BP Review"),
            Appointment(patient_id=p2.id, doctor_id=doctor_anita.id, department="General Medicine", appointment_date=today_str, time_slot="09:30 - 09:45", token_number=102, status="SCHEDULED", reason_for_visit="Acute High Fever and Sore Throat"),
        ]
        db.add_all(appts)
        db.commit()

        print("[SEED] Master Data & Clinical Prototypes Seeded Successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
