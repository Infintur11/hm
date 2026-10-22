import io
from app.services.pdf_service import generate_monthly_commission_pdf, generate_doctor_statement_pdf
from app.core.database import SessionLocal
from app.models.user import User
from app.services import commission_service as service

db = SessionLocal()
report = service.finance_report(db, "2026-10")
ledger_entries = service.list_ledger_entries(db, period="2026-10", page=1, page_size=100).get("items", [])
pdf_bytes = generate_monthly_commission_pdf(report, "2026-10", ledger_entries)

with open("/Users/gauravsingh/.gemini/antigravity-ide/brain/e8942725-cc88-42e0-b783-d613dd94cf87/clean_monthly_report.pdf", "wb") as f:
    f.write(pdf_bytes)

print(f"[SUCCESS] Monthly PDF generated: {len(pdf_bytes)} bytes. No errors.")

dr_sharma = db.query(User).filter(User.username == "dr.sharma").first()
dashboard = service.doctor_dashboard(db, dr_sharma.id, "2026-10")
doc_ledger = service.list_ledger_entries(db, doctor_id=dr_sharma.id, period="2026-10", page=1, page_size=100).get("items", [])
doc_pdf = generate_doctor_statement_pdf(dr_sharma, dashboard, doc_ledger, "2026-10")

with open("/Users/gauravsingh/.gemini/antigravity-ide/brain/e8942725-cc88-42e0-b783-d613dd94cf87/clean_doctor_statement.pdf", "wb") as f:
    f.write(doc_pdf)

print(f"[SUCCESS] Doctor Statement PDF generated: {len(doc_pdf)} bytes. No errors.")
