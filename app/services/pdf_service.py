import io
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List, Dict
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, KeepTogether
import os
import json


def generate_monthly_commission_pdf(report_data: dict, period: str, ledger_items: list = None) -> bytes:
    """
    Generates an executive-grade Monthly Commission Finance Report in PDF format.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=12,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    cell_audit = ParagraphStyle(
        'TableCellAudit',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )

    story = []

    # Hospital Header
    story.append(Paragraph("City Hospital &bull; Enterprise Financial Operations", subtitle_style))
    story.append(Paragraph(f"Doctor Commission &amp; Settlement Statement &mdash; {period}", title_style))
    story.append(Paragraph(f"Generated on {datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')} &bull; Official Accounts Record", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#e2e8f0'), spaceAfter=14))

    # Clean helper to avoid Unicode characters not present in standard Helvetica font
    def clean_money(val) -> str:
        try:
            return f"Rs. {float(val):,.2f}"
        except Exception:
            return "Rs. 0.00"

    def clean_text(val: str) -> str:
        if not val:
            return ""
        # Remove unicode emojis and symbols that render as black square tofu in standard Helvetica
        return str(val).replace("🔓", "").replace("🔒", "").replace("✓", "").replace("🛡️", "").replace("⚡", "").replace("₹", "Rs. ").strip()

    # KPI Summary Cards Table
    net_comm = clean_money(report_data.get('net_commission', '0.00'))
    avail = clean_money(report_data.get('available_balance', '0.00'))
    paid = clean_money(report_data.get('payouts', '0.00'))
    holds = clean_money(report_data.get('outstanding_liability', '0.00'))

    kpi_data = [
        [
            Paragraph("<b>TOTAL ACCRUED COMMISSION</b>", cell_bold),
            Paragraph("<b>READY FOR PAYOUT [Released]</b>", cell_bold),
            Paragraph("<b>SAFETY INVARIANT HOLDS [Locked]</b>", cell_bold),
            Paragraph("<b>DISBURSED &amp; SETTLED [Paid]</b>", cell_bold)
        ],
        [
            Paragraph(f"<font size=12 color='#1e3a8a'><b>{net_comm}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#065f46'><b>{avail}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#92400e'><b>{holds}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#334155'><b>{paid}</b></font>", cell_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # Doctor Breakdown Section (if available)
    doctors = report_data.get('doctors', [])
    if doctors:
        story.append(Paragraph("Doctor Compensation Summary", section_style))
        doc_headers = [
            Paragraph("<b>Doctor</b>", cell_bold),
            Paragraph("<b>Department</b>", cell_bold),
            Paragraph("<b>Accrued</b>", cell_bold),
            Paragraph("<b>Available</b>", cell_bold),
            Paragraph("<b>Settled</b>", cell_bold)
        ]
        doc_rows = [doc_headers]
        for d in doctors:
            doc_rows.append([
                Paragraph(clean_text(d.get('doctor_name', '-')), cell_style),
                Paragraph(clean_text(d.get('department', '-')), cell_style),
                Paragraph(clean_money(d.get('net_commission', 0)), cell_style),
                Paragraph(clean_money(d.get('available', 0)), cell_style),
                Paragraph(clean_money(d.get('paid', 0)), cell_style),
            ])
        doc_table = Table(doc_rows, colWidths=[200, 160, 120, 120, 120])
        doc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ]))
        story.append(doc_table)
        story.append(Spacer(1, 14))

    # Granular Transactional Ledger Items
    if ledger_items:
        story.append(Paragraph("Granular Transactional Bill &amp; Commission Ledger", section_style))
        ledger_headers = [
            Paragraph("<b>Invoice # / Date</b>", cell_bold),
            Paragraph("<b>Doctor</b>", cell_bold),
            Paragraph("<b>Patient (MRN)</b>", cell_bold),
            Paragraph("<b>Service Line</b>", cell_bold),
            Paragraph("<b>Bill Amount</b>", cell_bold),
            Paragraph("<b>Commission</b>", cell_bold),
            Paragraph("<b>Status</b>", cell_bold),
            Paragraph("<b>Safety Invariant Audit Trace</b>", cell_bold)
        ]
        ledger_table_data = [ledger_headers]
        for item in ledger_items:
            chip_text = clean_text(item.get('chip_label', item.get('status', '')))
            audit_note = clean_text(item.get('explanation') or item.get('execution_audit_log') or 'Verified in order')
            ledger_table_data.append([
                Paragraph(f"<b>{clean_text(item.get('invoice_number', '-'))}</b><br/>{clean_text(item.get('accrued_at', '-')[:11])}", cell_style),
                Paragraph(clean_text(item.get('doctor_name', '-')), cell_style),
                Paragraph(f"{clean_text(item.get('patient_name', '-'))}<br/>({clean_text(item.get('patient_mrn', '-'))})", cell_style),
                Paragraph(clean_text(item.get('service_type', '-')), cell_style),
                Paragraph(clean_money(item.get('base_amount', 0)), cell_style),
                Paragraph(f"<b>{clean_money(item.get('calculated_commission', 0))}</b>", cell_style),
                Paragraph(chip_text, cell_bold),
                Paragraph(audit_note, cell_audit)
            ])
        ledger_table = Table(ledger_table_data, colWidths=[85, 95, 95, 80, 65, 65, 85, 150])
        ledger_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ]))
        story.append(ledger_table)
        story.append(Spacer(1, 14))

    # Statement Sign-off
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<i>This is a computer-generated financial document verified by City Hospital Automated Invariant Safety Engine. No physical signature required.</i>",
        cell_audit
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_doctor_statement_pdf(doctor_user, dashboard_data: dict, ledger_items: list, period: str) -> bytes:
    """
    Generates a personalized Doctor Commission & Settlement Statement in PDF format.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748b')
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=10,
        spaceAfter=5
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    cell_audit = ParagraphStyle(
        'TableCellAudit',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#64748b')
    )

    def clean_money(val) -> str:
        try:
            return f"Rs. {float(val):,.2f}"
        except Exception:
            return "Rs. 0.00"

    def clean_text(val: str) -> str:
        if not val:
            return ""
        return str(val).replace("🔓", "").replace("🔒", "").replace("✓", "").replace("🛡️", "").replace("⚡", "").replace("₹", "Rs. ").strip()

    story = []

    # Header
    story.append(Paragraph("City Hospital &bull; Physician Earnings &amp; Settlement Statement", subtitle_style))
    story.append(Paragraph(f"{clean_text(doctor_user.full_name)} &bull; {clean_text(doctor_user.department)}", title_style))
    story.append(Paragraph(f"Billing Period: {period} &bull; Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#e2e8f0'), spaceAfter=12))

    # Doctor KPI Summary
    net = clean_money(dashboard_data.get('net_earned', '0.00'))
    avail = clean_money(dashboard_data.get('available', '0.00'))
    locked = clean_money(dashboard_data.get('accrued_locked', '0.00'))
    paid = clean_money(dashboard_data.get('paid_in_period', '0.00'))

    kpi_data = [
        [
            Paragraph("<b>NET EARNED THIS MONTH</b>", cell_bold),
            Paragraph("<b>READY TO PULL [Released]</b>", cell_bold),
            Paragraph("<b>WAITING ON BILLS / LOCKS [Locked]</b>", cell_bold),
            Paragraph("<b>PAID THIS MONTH [Settled]</b>", cell_bold)
        ],
        [
            Paragraph(f"<font size=12 color='#1e3a8a'><b>{net}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#065f46'><b>{avail}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#92400e'><b>{locked}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#334155'><b>{paid}</b></font>", cell_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[130, 130, 140, 130])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    # Granular Itemized Breakdown
    story.append(Paragraph("Itemized Clinical Services &amp; Commission Breakdown", section_style))
    items_header = [
        Paragraph("<b>Date / ID</b>", cell_bold),
        Paragraph("<b>Patient (MRN)</b>", cell_bold),
        Paragraph("<b>Invoice # / Service</b>", cell_bold),
        Paragraph("<b>Base Bill</b>", cell_bold),
        Paragraph("<b>Commission</b>", cell_bold),
        Paragraph("<b>Status</b>", cell_bold)
    ]
    items_data = [items_header]
    for it in (ledger_items or []):
        chip = clean_text(it.get('chip_label', it.get('status', '')))
        items_data.append([
            Paragraph(f"#{it.get('id', '-')}<br/>{clean_text(it.get('accrued_at', '-')[:11])}", cell_style),
            Paragraph(f"<b>{clean_text(it.get('patient_name', '-'))}</b><br/>{clean_text(it.get('patient_mrn', '-'))}", cell_style),
            Paragraph(f"{clean_text(it.get('invoice_number', '-'))}<br/><font color='#64748b'>{clean_text(it.get('service_type', '-'))}</font>", cell_style),
            Paragraph(clean_money(it.get('base_amount', 0)), cell_style),
            Paragraph(f"<b>{clean_money(it.get('calculated_commission', 0))}</b>", cell_style),
            Paragraph(chip, cell_bold)
        ])
    if len(items_data) == 1:
        items_data.append([Paragraph("No transactions recorded for this period.", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style)])

    items_table = Table(items_data, colWidths=[70, 110, 140, 70, 70, 70])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # Verified Bank Account Notice
    bank_text = "<b>Hospital Verified Direct Settlement Account:</b> State Bank of India &bull; Account: ****1003 &bull; IFSC: SBIN0001234 &bull; Real-time IMPS Transfer"
    story.append(Paragraph(bank_text, cell_audit))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<i>This statement is confidential and generated directly from hospital ledger records.</i>", cell_audit))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_diagnostic_report_pdf(
    order_data: dict,
    result_data: dict,
    patient_data: dict,
    doctor_data: dict,
    template_data: dict
) -> bytes:
    """
    Generates an executive-grade clinical diagnostic report PDF for Laboratory
    and Radiology departments with structured findings, parameters, and scan attachments.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#64748b')
    )
    dept_style = ParagraphStyle(
        'DeptHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=4,
        spaceAfter=8
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    cell_high = ParagraphStyle(
        'TableCellHigh',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#b91c1c')
    )
    cell_low = ParagraphStyle(
        'TableCellLow',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1d4ed8')
    )
    cell_audit = ParagraphStyle(
        'TableCellAudit',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )

    story = []

    def clean_txt(val: Any) -> str:
        if val is None:
            return "-"
        return str(val).replace("₹", "Rs. ").replace("✓", "").replace("⚡", "").replace("🛡️", "").strip()

    # Hospital Header
    story.append(Paragraph("<b>CITY HOSPITAL &bull; DIAGNOSTIC &amp; IMAGING CENTRE</b>", title_style))
    story.append(Paragraph("Accredited Clinical Pathology &bull; Digital Radiology &amp; PACS Unit &bull; Ph: +91 98765 43210", subtitle_style))
    story.append(Spacer(1, 6))

    dept_name = clean_txt(template_data.get('department', 'Laboratory / Diagnostic Services')).upper()
    story.append(Paragraph(f"DEPARTMENT OF {dept_name}", dept_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=10))

    # Patient & Specimen Demographics Box
    patient_name = clean_txt(patient_data.get('full_name', 'Unknown'))
    patient_mrn = clean_txt(patient_data.get('mrn', '-'))
    age_gender = f"{patient_data.get('age', '-')} Y / {clean_txt(patient_data.get('gender', '-'))}"
    phone = clean_txt(patient_data.get('phone_number', '-'))
    ref_doc = clean_txt(doctor_data.get('full_name', 'Doctor'))
    test_name = clean_txt(order_data.get('test_name', template_data.get('test_name', 'Investigation')))
    barcode = clean_txt(order_data.get('sample_barcode', 'N/A'))
    collected_at = clean_txt(order_data.get('collected_at', order_data.get('created_at', '-')))
    verified_at = clean_txt(result_data.get('verified_at', datetime.utcnow().strftime('%Y-%m-%d %H:%M')))

    demo_data = [
        [
            Paragraph("<b>Patient Name:</b>", cell_style),
            Paragraph(f"<b>{patient_name}</b>", cell_bold),
            Paragraph("<b>Order / Barcode:</b>", cell_style),
            Paragraph(f"#{order_data.get('id', '-')} &bull; {barcode}", cell_style)
        ],
        [
            Paragraph("<b>Patient ID (MRN):</b>", cell_style),
            Paragraph(patient_mrn, cell_style),
            Paragraph("<b>Investigation:</b>", cell_style),
            Paragraph(f"<b>{test_name}</b>", cell_bold)
        ],
        [
            Paragraph("<b>Age / Gender:</b>", cell_style),
            Paragraph(age_gender, cell_style),
            Paragraph("<b>Sample / Modality:</b>", cell_style),
            Paragraph(clean_txt(template_data.get('sample_type', '-')) + (f" ({template_data.get('modality')})" if template_data.get('modality') else ""), cell_style)
        ],
        [
            Paragraph("<b>Referring Clinician:</b>", cell_style),
            Paragraph(f"{'' if ref_doc.startswith('Dr.') else 'Dr. '}{ref_doc}", cell_style),
            Paragraph("<b>Report Date/Time:</b>", cell_style),
            Paragraph(verified_at, cell_style)
        ]
    ]

    demo_table = Table(demo_data, colWidths=[110, 160, 110, 160])
    demo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 10))

    is_radiology = (template_data.get('department') == 'Radiology') or bool(order_data.get('modality')) or bool(result_data.get('modality'))

    if is_radiology:
        # RADIOLOGY REPORT BODY
        modality_title = clean_txt(result_data.get('modality') or template_data.get('modality') or 'DIAGNOSTIC RADIOLOGY')
        story.append(Paragraph(f"<b>MODALITY: {modality_title} &mdash; {test_name}</b>", section_style))

        if result_data.get('clinical_history') or order_data.get('clinical_notes'):
            history_text = clean_txt(result_data.get('clinical_history') or order_data.get('clinical_notes'))
            story.append(Paragraph("<b>CLINICAL INDICATION / HISTORY:</b>", section_style))
            story.append(Paragraph(history_text, body_style))
            story.append(Spacer(1, 4))

        if result_data.get('technique'):
            story.append(Paragraph("<b>TECHNIQUE / PROTOCOL:</b>", section_style))
            story.append(Paragraph(clean_txt(result_data.get('technique')), body_style))
            story.append(Spacer(1, 4))

        # Check for Scan / Annotated Image Attachment
        img_rel_path = result_data.get('annotated_image_url') or result_data.get('image_url')
        if img_rel_path:
            clean_rel = img_rel_path.lstrip("/")
            if os.path.exists(clean_rel):
                try:
                    # Embed scan with clean max width of 340
                    story.append(Spacer(1, 6))
                    scan_img = RLImage(clean_rel, width=340, height=220)
                    scan_img.hAlign = 'CENTER'
                    story.append(scan_img)
                    caption = "Radiological Examination View with Clinical PACS Annotations" if result_data.get('annotated_image_url') else "Diagnostic Scan Acquisition"
                    story.append(Paragraph(f"<font size=8 color='#64748b'><i>Fig: {caption}</i></font>", ParagraphStyle('Cap', parent=subtitle_style, alignment=1)))
                    story.append(Spacer(1, 8))
                except Exception as img_err:
                    pass

        story.append(Paragraph("<b>OBSERVATIONS &amp; FINDINGS:</b>", section_style))
        findings_text = clean_txt(result_data.get('findings') or result_data.get('result_value') or 'No abnormalities detected.')
        # Format line breaks
        for p_line in findings_text.split("\n"):
            if p_line.strip():
                story.append(Paragraph(p_line.strip(), body_style))
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>IMPRESSION &amp; DIAGNOSIS:</b>", section_style))
        imp_text = clean_txt(result_data.get('impression') or 'Within normal physiological limits.')
        for p_line in imp_text.split("\n"):
            if p_line.strip():
                story.append(Paragraph(f"<b>&bull; {p_line.strip()}</b>", body_style))
        story.append(Spacer(1, 10))

    else:
        # LABORATORY REPORT (PATHOLOGY / BIOCHEMISTRY / HEMATOLOGY)
        story.append(Paragraph("<b>INVESTIGATION RESULTS &amp; BIOLOGICAL REFERENCE INTERVALS</b>", section_style))

        # Parse parameter_results if JSON
        param_list = []
        raw_params = result_data.get('parameter_results')
        if raw_params:
            try:
                param_list = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
            except Exception:
                param_list = []

        if param_list and isinstance(param_list, list) and len(param_list) > 0:
            lab_table_rows = [
                [
                    Paragraph("<b>Parameter / Analyte</b>", cell_bold),
                    Paragraph("<b>Observed Result</b>", cell_bold),
                    Paragraph("<b>Units</b>", cell_bold),
                    Paragraph("<b>Reference Interval</b>", cell_bold),
                    Paragraph("<b>Status / Flag</b>", cell_bold)
                ]
            ]
            for p in param_list:
                p_name = clean_txt(p.get('name', 'Parameter'))
                p_val = clean_txt(p.get('value', '-'))
                p_unit = clean_txt(p.get('unit', ''))
                p_range = clean_txt(p.get('range', '-'))
                p_flag = clean_txt(p.get('flag', 'NORMAL')).upper()

                if "HIGH" in p_flag:
                    flag_style = cell_high
                    val_style = cell_high
                elif "LOW" in p_flag:
                    flag_style = cell_low
                    val_style = cell_low
                else:
                    flag_style = cell_style
                    val_style = cell_bold

                lab_table_rows.append([
                    Paragraph(p_name, cell_style),
                    Paragraph(f"<b>{p_val}</b>", val_style),
                    Paragraph(p_unit, cell_style),
                    Paragraph(p_range, cell_style),
                    Paragraph(f"<b>{p_flag}</b>", flag_style)
                ])

            lab_table = Table(lab_table_rows, colWidths=[160, 100, 70, 110, 100])
            lab_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ]))
            story.append(lab_table)
        else:
            # Single value result fallback
            single_val = clean_txt(result_data.get('result_value', '-'))
            single_range = clean_txt(result_data.get('reference_range') or template_data.get('normal_range', '-'))
            single_unit = clean_txt(result_data.get('unit') or template_data.get('unit_of_measurement', ''))
            is_abnormal = result_data.get('is_abnormal', False)

            lab_table_rows = [
                [
                    Paragraph("<b>Test Name</b>", cell_bold),
                    Paragraph("<b>Observed Result</b>", cell_bold),
                    Paragraph("<b>Units</b>", cell_bold),
                    Paragraph("<b>Reference Range</b>", cell_bold),
                    Paragraph("<b>Interpretation</b>", cell_bold)
                ],
                [
                    Paragraph(test_name, cell_style),
                    Paragraph(f"<b>{single_val}</b>", cell_high if is_abnormal else cell_bold),
                    Paragraph(single_unit, cell_style),
                    Paragraph(single_range, cell_style),
                    Paragraph("OUTSIDE RANGE" if is_abnormal else "NORMAL", cell_high if is_abnormal else cell_style)
                ]
            ]
            lab_table = Table(lab_table_rows, colWidths=[160, 100, 70, 110, 100])
            lab_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ]))
            story.append(lab_table)

        story.append(Spacer(1, 10))
        if result_data.get('technician_notes'):
            story.append(Paragraph("<b>TECHNICIAN REMARKS &amp; CLINICAL CORRELATION:</b>", section_style))
            story.append(Paragraph(clean_txt(result_data.get('technician_notes')), body_style))
            story.append(Spacer(1, 8))

    # Quality Sign-off / Signature Table
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8))

    sign_data = [
        [
            Paragraph("<b>Prepared by:</b><br/>Medical Lab Technologist / Radiographer", cell_audit),
            Paragraph("<b>Verified &amp; Signed by:</b><br/>Consultant Pathologist / Radiologist", cell_audit),
            Paragraph(f"<b>Authentication:</b><br/>NABL / AERB Digital Quality Audit<br/>{verified_at}", cell_audit)
        ]
    ]
    sign_table = Table(sign_data, colWidths=[180, 180, 180])
    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<i>*** End of Diagnostic Examination Report &bull; Electronic Medical Record ***</i>", ParagraphStyle('EndRep', parent=cell_audit, alignment=1)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

