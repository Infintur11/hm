from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.models.corporate import CustomDashboardKpi, CorporateClient
from app.models.billing import Invoice, InvoiceItem
from app.models.commission import CommissionLedgerEntry
from app.models.user import User
from app.models.patient import Patient
from typing import List, Dict, Any, Optional
import json

PREBUILT_CATALOG = {
    "CORPORATE_RECEIVABLES": {
        "title": "Corporate Unbilled Claims",
        "description": "Total pending receivables awaiting settlement from Insurance TPAs & Corporate Tie-ups",
        "category": "Corporate & Insurance",
        "sql": "SELECT COALESCE(SUM(corporate_claim_amount), 0) FROM invoices WHERE billing_type = 'CORPORATE_TIEUP' AND payment_status != 'PAID'",
        "metric_type": "CURRENCY",
        "accent_color": "rose",
        "subtitle": "Pending reimbursement claims"
    },
    "WALK_IN_VS_CORP": {
        "title": "Corporate Revenue Contribution",
        "description": "Share of hospital gross revenue originating from corporate accounts & TPAs vs walk-ins",
        "category": "Revenue Mix",
        "sql": "SELECT ROUND(COALESCE(SUM(CASE WHEN billing_type = 'CORPORATE_TIEUP' THEN net_payable ELSE 0.0 END) * 100.0 / NULLIF(SUM(net_payable), 0), 0), 1) FROM invoices",
        "metric_type": "PERCENT",
        "accent_color": "blue",
        "subtitle": "% of total hospital billing"
    },
    "CASH_VS_DIGITAL": {
        "title": "Cash Payment Ratio",
        "description": "Proportion of physical currency cash payments vs digital (UPI, card, cheque, cashless)",
        "category": "Treasury",
        "sql": "SELECT ROUND(COALESCE(SUM(CASE WHEN payment_method = 'CASH' THEN paid_amount ELSE 0.0 END) * 100.0 / NULLIF(SUM(paid_amount), 0), 0), 1) FROM invoices WHERE paid_amount > 0",
        "metric_type": "PERCENT",
        "accent_color": "amber",
        "subtitle": "Cash share of cleared revenue"
    },
    "AVG_INVOICE_VALUE": {
        "title": "Average Revenue Per Patient (ARPU)",
        "description": "Mean invoice realization ticket size across all clinical encounters and admissions",
        "category": "Clinical Operations",
        "sql": "SELECT ROUND(COALESCE(AVG(net_payable), 0), 2) FROM invoices",
        "metric_type": "CURRENCY",
        "accent_color": "emerald",
        "subtitle": "Mean net invoice ticket"
    },
    "LAB_REV_SHARE": {
        "title": "Laboratory & Diagnostic Billing",
        "description": "Gross revenue collected across all pathology tests, biochemistry profiles, and radiology",
        "category": "Diagnostics",
        "sql": "SELECT ROUND(COALESCE(SUM(total_price), 0), 2) FROM invoice_items WHERE item_type = 'LAB_TEST'",
        "metric_type": "CURRENCY",
        "accent_color": "cyan",
        "subtitle": "Clinical tests and imaging"
    },
    "PHARMACY_REV_SHARE": {
        "title": "Dispensary & Pharmacy Revenue",
        "description": "Gross pharmaceutical turnover generated from closed-loop medication dispensing",
        "category": "Pharmacy",
        "sql": "SELECT ROUND(COALESCE(SUM(total_price), 0), 2) FROM invoice_items WHERE item_type = 'PHARMACY'",
        "metric_type": "CURRENCY",
        "accent_color": "violet",
        "subtitle": "Central dispensary sales"
    },
    "DOCTOR_COMMISSION_SHARE": {
        "title": "Doctor Commission Payout Ratio",
        "description": "Doctor compensation liabilities as a percentage of hospital revenue turnover",
        "category": "Physician Compensation",
        "sql": "SELECT ROUND(COALESCE(SUM(amount) * 100.0 / (SELECT NULLIF(SUM(net_payable), 0) FROM invoices), 0), 1) FROM commission_ledger",
        "metric_type": "PERCENT",
        "accent_color": "amber",
        "subtitle": "% of total hospital turnover"
    },
    "TIEUP_CREDIT_UTILIZATION": {
        "title": "Corporate Credit Pool Drawn",
        "description": "Aggregated credit utilization percentage across all active corporate & insurance partners",
        "category": "Corporate & Insurance",
        "sql": "SELECT ROUND(COALESCE(SUM(current_utilized_credit) * 100.0 / NULLIF(SUM(monthly_credit_limit), 0), 0), 1) FROM corporate_clients WHERE is_active = 1",
        "metric_type": "PERCENT",
        "accent_color": "rose",
        "subtitle": "Overall partner credit drawn"
    },
    "DAILY_CLEARANCE_RATE": {
        "title": "Billing Clearance Efficiency",
        "description": "Percentage of all issued invoices successfully marked PAID through the cashier",
        "category": "Treasury",
        "sql": "SELECT ROUND(COALESCE(SUM(CASE WHEN payment_status = 'PAID' THEN 1.0 ELSE 0.0 END) * 100.0 / NULLIF(COUNT(*), 0), 100.0), 1) FROM invoices",
        "metric_type": "PERCENT",
        "accent_color": "emerald",
        "subtitle": "Invoices fully cleared"
    },
    "NET_COLLECTIONS_CLEARED": {
        "title": "Total Net Revenue Cleared",
        "description": "Cumulative total of all cashier receipts successfully credited across all accounts",
        "category": "Treasury",
        "sql": "SELECT ROUND(COALESCE(SUM(paid_amount), 0), 2) FROM invoices",
        "metric_type": "CURRENCY",
        "accent_color": "emerald",
        "subtitle": "Cumulative cashier receipts"
    }
}

def execute_catalog_query(db: Session, query_key: str) -> float:
    meta = PREBUILT_CATALOG.get(query_key)
    if not meta:
        return 0.0
    try:
        res = db.execute(text(meta["sql"])).scalar()
        return float(res) if res is not None else 0.0
    except Exception:
        return 0.0

def format_metric(value: float, metric_type: str) -> str:
    if metric_type == "CURRENCY":
        return f"₹{value:,.2f}"
    elif metric_type == "PERCENT":
        return f"{value:.1f}%"
    elif metric_type == "COUNT":
        return f"{int(value):,}"
    return str(value)

def get_active_custom_kpis(db: Session) -> List[Dict[str, Any]]:
    # If no custom KPIs defined yet, seed 3 high-impact ones
    existing_count = db.query(CustomDashboardKpi).count()
    if existing_count == 0:
        seed_kpis = [
            CustomDashboardKpi(title="Corporate Claims Pending", query_key="CORPORATE_RECEIVABLES", metric_type="CURRENCY", accent_color="rose", subtitle="Pending corporate & TPA reimbursement", display_order=1),
            CustomDashboardKpi(title="Corporate Revenue Mix", query_key="WALK_IN_VS_CORP", metric_type="PERCENT", accent_color="blue", subtitle="Share of hospital gross revenue", display_order=2),
            CustomDashboardKpi(title="Cash vs Digital Split", query_key="CASH_VS_DIGITAL", metric_type="PERCENT", accent_color="amber", subtitle="Cash % of cleared collections", display_order=3),
            CustomDashboardKpi(title="Avg Revenue Per Visit", query_key="AVG_INVOICE_VALUE", metric_type="CURRENCY", accent_color="emerald", subtitle="Average invoice ticket size", display_order=4)
        ]
        db.add_all(seed_kpis)
        db.commit()

    kpis = db.query(CustomDashboardKpi).filter(CustomDashboardKpi.is_active == True).order_by(CustomDashboardKpi.display_order.asc(), CustomDashboardKpi.id.asc()).all()
    results = []
    for k in kpis:
        val = execute_catalog_query(db, k.query_key)
        formatted = format_metric(val, k.metric_type)
        results.append({
            "id": k.id,
            "title": k.title,
            "query_key": k.query_key,
            "metric_type": k.metric_type,
            "accent_color": k.accent_color or "emerald",
            "subtitle": k.subtitle or "",
            "numeric_value": val,
            "current_value": formatted
        })
    return results

def get_available_query_catalog(db: Session) -> List[Dict[str, Any]]:
    # List all prebuilt queries with their current live calculated value
    active_keys = {k.query_key for k in db.query(CustomDashboardKpi).filter(CustomDashboardKpi.is_active == True).all()}
    catalog = []
    for key, item in PREBUILT_CATALOG.items():
        val = execute_catalog_query(db, key)
        catalog.append({
            "query_key": key,
            "title": item["title"],
            "description": item["description"],
            "category": item["category"],
            "metric_type": item["metric_type"],
            "accent_color": item["accent_color"],
            "subtitle": item["subtitle"],
            "sql_snippet": item["sql"],
            "preview_value": format_metric(val, item["metric_type"]),
            "is_pinned": key in active_keys
        })
    return catalog

def add_custom_kpi(db: Session, query_key: str, title: Optional[str] = None, accent_color: Optional[str] = None) -> Dict[str, Any]:
    meta = PREBUILT_CATALOG.get(query_key)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Invalid query key '{query_key}'")
    
    final_title = title.strip() if title and title.strip() else meta["title"]
    final_color = accent_color or meta["accent_color"]
    
    new_kpi = CustomDashboardKpi(
        title=final_title,
        query_key=query_key,
        metric_type=meta["metric_type"],
        accent_color=final_color,
        subtitle=meta["subtitle"],
        is_active=True
    )
    db.add(new_kpi)
    db.commit()
    db.refresh(new_kpi)
    return {"status": "SUCCESS", "id": new_kpi.id, "title": new_kpi.title}

def delete_custom_kpi(db: Session, kpi_id: int) -> Dict[str, Any]:
    k = db.query(CustomDashboardKpi).filter(CustomDashboardKpi.id == kpi_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="KPI card not found")
    db.delete(k)
    db.commit()
    return {"status": "SUCCESS"}


def get_granular_financial_breakdown(db: Session, period: Optional[str] = None) -> Dict[str, Any]:
    """
    Produces minute, granular outputs breaking down hospital financial data
    across Service Lines, Payment Modes (cash notes, UPI UTRs, cheques),
    Billing Segments (Walk-in vs Corporate), and Physician Commissions.
    """
    invoices = db.query(Invoice).all()
    invoice_items = db.query(InvoiceItem).all()
    
    # 1. Department / Service Line Breakdown
    dept_map = {
        "CONSULTATION": {"name": "Doctor Consultations", "count": 0, "total": 0.0},
        "LAB_TEST": {"name": "Pathology & Diagnostics", "count": 0, "total": 0.0},
        "BED_CHARGE": {"name": "Inpatient Bed Charges", "count": 0, "total": 0.0},
        "PHARMACY": {"name": "Dispensary Medications", "count": 0, "total": 0.0},
        "PROCEDURE": {"name": "Clinical Procedures", "count": 0, "total": 0.0}
    }
    gross_items_total = 0.0
    for itm in invoice_items:
        t = itm.item_type if itm.item_type in dept_map else "PROCEDURE"
        dept_map[t]["count"] += itm.quantity or 1
        dept_map[t]["total"] += itm.total_price or 0.0
        gross_items_total += itm.total_price or 0.0
        
    departments = []
    for k, v in dept_map.items():
        pct = round((v["total"] / gross_items_total * 100), 1) if gross_items_total > 0 else 0.0
        departments.append({
            "type": k,
            "name": v["name"],
            "orders_count": v["count"],
            "revenue": v["total"],
            "percentage": pct
        })
    departments.sort(key=lambda x: x["revenue"], reverse=True)

    # 2. Payment Tender & Denominations Breakdown
    mode_map = {
        "CASH": {"label": "Cash (Physical Currency)", "count": 0, "amount": 0.0},
        "UPI": {"label": "UPI / QR Digital", "count": 0, "amount": 0.0},
        "CHEQUE": {"label": "Bank Cheque", "count": 0, "amount": 0.0},
        "CARD": {"label": "Debit / Credit Card", "count": 0, "amount": 0.0},
        "INSURANCE": {"label": "Corporate / Insurance Credit", "count": 0, "amount": 0.0},
        "SPLIT": {"label": "Multi-Tender Split", "count": 0, "amount": 0.0}
    }
    
    total_collected = 0.0
    denom_totals = {"500": 0, "200": 0, "100": 0, "50": 0, "20": 0, "10": 0, "5": 0, "2": 0, "1": 0}
    cheque_details = []
    upi_details = []

    for inv in invoices:
        paid = float(inv.paid_amount or 0.0)
        total_collected += paid
        m = (inv.payment_method or "CASH").upper()
        if m in mode_map:
            mode_map[m]["count"] += 1
            mode_map[m]["amount"] += paid
        else:
            mode_map["CASH"]["count"] += 1
            mode_map["CASH"]["amount"] += paid
            
        # Parse cash denominations if stored
        if inv.cash_denominations_json:
            try:
                counts = json.loads(inv.cash_denominations_json)
                for d_key, c_val in counts.items():
                    if str(d_key) in denom_totals:
                        denom_totals[str(d_key)] += int(c_val)
            except Exception:
                pass
                
        if inv.cheque_number:
            cheque_details.append({
                "invoice_number": inv.invoice_number,
                "cheque_number": inv.cheque_number,
                "bank_name": inv.bank_name or "Scheduled Bank",
                "amount": paid
            })
            
        if inv.upi_id:
            upi_details.append({
                "invoice_number": inv.invoice_number,
                "upi_id": inv.upi_id,
                "amount": paid
            })

    payment_modes = []
    for k, v in mode_map.items():
        pct = round((v["amount"] / total_collected * 100), 1) if total_collected > 0 else 0.0
        payment_modes.append({
            "mode": k,
            "label": v["label"],
            "transactions_count": v["count"],
            "amount": v["amount"],
            "percentage": pct
        })
    payment_modes.sort(key=lambda x: x["amount"], reverse=True)

    # 3. Billing Segment Breakdown: Walk-in vs Corporate Tie-up
    walkin_count = 0
    walkin_revenue = 0.0
    corp_count = 0
    corp_revenue = 0.0

    for inv in invoices:
        b_type = getattr(inv, "billing_type", "WALK_IN") or "WALK_IN"
        amt = float(inv.net_payable or 0.0)
        if b_type == "CORPORATE_TIEUP":
            corp_count += 1
            corp_revenue += amt
        else:
            walkin_count += 1
            walkin_revenue += amt

    total_invoiced = walkin_revenue + corp_revenue
    segments = [
        {
            "segment": "WALK_IN",
            "label": "Walk-in / Private Patients",
            "invoice_count": walkin_count,
            "revenue": walkin_revenue,
            "percentage": round((walkin_revenue / total_invoiced * 100), 1) if total_invoiced > 0 else 0.0,
            "avg_ticket": round((walkin_revenue / walkin_count), 2) if walkin_count > 0 else 0.0
        },
        {
            "segment": "CORPORATE_TIEUP",
            "label": "Corporate & Insurance Tie-ups",
            "invoice_count": corp_count,
            "revenue": corp_revenue,
            "percentage": round((corp_revenue / total_invoiced * 100), 1) if total_invoiced > 0 else 0.0,
            "avg_ticket": round((corp_revenue / corp_count), 2) if corp_count > 0 else 0.0
        }
    ]

    # 4. Doctor Commissions & Referrals Granularity
    docs = db.query(User).filter(User.role == "DOCTOR").all()
    doctor_breakdown = []
    for d in docs:
        comm_entries = db.query(CommissionLedgerEntry).filter(CommissionLedgerEntry.doctor_id == d.id).all()
        comm_earned = sum(c.amount for c in comm_entries)
        ref_patients = db.query(Patient).filter(Patient.referred_by_doctor_id == d.id).count()
        doctor_breakdown.append({
            "doctor_id": d.id,
            "doctor_name": d.full_name,
            "department": d.department or "Clinical OPD",
            "referred_patients": ref_patients,
            "commission_entries_count": len(comm_entries),
            "total_commission_accrued": comm_earned
        })
    doctor_breakdown.sort(key=lambda x: x["total_commission_accrued"], reverse=True)

    return {
        "summary": {
            "total_gross_invoiced": total_invoiced,
            "total_cleared_collections": total_collected,
            "accounts_receivable": max(0.0, total_invoiced - total_collected),
            "total_invoices_count": len(invoices)
        },
        "departments": departments,
        "payment_modes": payment_modes,
        "cash_denominations_tally": denom_totals,
        "cheque_audit_trail": cheque_details[:10],
        "upi_audit_trail": upi_details[:10],
        "segments": segments,
        "doctor_breakdown": doctor_breakdown
    }
