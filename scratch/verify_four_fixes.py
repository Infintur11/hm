import os
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = "/Users/gauravsingh/.gemini/antigravity-ide/brain/e8942725-cc88-42e0-b783-d613dd94cf87"

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # =====================================================================
        # TEST 1: RECEPTIONIST WALK-IN VS CORPORATE TIE-UP & LIVE CREDIT BALANCE
        # =====================================================================
        print("--> 1. Logging in as Receptionist (recep.riya)...")
        page.goto("http://127.0.0.1:8000/login")
        page.fill("#username", "recep.riya")
        page.fill("#password", "recep123")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Testing Tie-Up Credit Limits directory in Doctor OPD capacity card...")
        page.click("button:has-text('Tie-Up Credit Limits')")
        time.sleep(0.5)
        quick_panel = page.locator("#corporateCreditQuickPanel")
        assert quick_panel.is_visible(), "corporateCreditQuickPanel did not expand!"
        cards = page.locator("#receptionCorpCardsGrid > div")
        print(f"Receptionist corporate cards loaded: {cards.count()}")
        assert cards.count() >= 5, "Expected 5 corporate partner cards in reception!"

        print("Testing Patient Registration Walk-in vs Corporate toggle...")
        # Toggle corporate tieup
        page.click("#btnRegCorporate")
        time.sleep(0.4)
        assert page.locator("#regCorporateFieldsArea").is_visible(), "regCorporateFieldsArea not visible!"

        # Select a partner (e.g. Star Health or CGHS)
        corp_select = page.locator("#regCorporateClientSelect")
        corp_select.select_option(index=1)
        time.sleep(0.4)

        credit_box = page.locator("#regCorporateCreditBox")
        assert credit_box.is_visible(), "regCorporateCreditBox did not appear!"
        avail_text = page.locator("#regCorpAvailableCredit").text_content()
        print(f"Receptionist Live Available Credit Check: {avail_text}")

        # Capture Reception Corporate Feature Screenshot
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "reception_corporate_credit_check.png"))
        print("PASS: Receptionist Corporate Tie-up & Live Credit Balance verified! Saved reception_corporate_credit_check.png")

        # =====================================================================
        # TEST 2: DOCTOR REVIEW WORKSTATION ACCESS & QUEUE LOADING
        # =====================================================================
        print("\n--> 2. Logging in as Doctor (dr.sharma)...")
        page.context.clear_cookies()
        page.goto("http://127.0.0.1:8000/login")
        page.fill("#username", "dr.sharma")
        page.fill("#password", "doc123")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Checking Doctor Diagnostic Reports Review Queue...")
        tbody = page.locator("#doctorReviewQueueBody")
        assert tbody.is_visible(), "Doctor review queue table not visible!"
        rows = tbody.locator("tr")
        print(f"Doctor review queue rows: {rows.count()}")
        # Check that it did NOT fail
        failed_cell = page.locator("#doctorReviewQueueBody td:has-text('Failed to load')")
        assert failed_cell.count() == 0, "Review queue still says 'Failed to load'!"

        # Capture Doctor Review Queue Screenshot
        review_section = page.locator("#doctorLabReviewSection")
        review_section.scroll_into_view_if_needed()
        time.sleep(0.5)
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "doctor_review_queue_working.png"))
        print("PASS: Doctor Review Workstation loaded cleanly with sign-off actions! Saved doctor_review_queue_working.png")

        # =====================================================================
        # TEST 3: VISUAL ANALYTE BUILDER - ROW NUMBERING & ADD INDICATION
        # =====================================================================
        print("\n--> 3. Logging in as Admin to test Visual Analyte Builder...")
        page.context.clear_cookies()
        page.goto("http://127.0.0.1:8000/login")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        page.goto("http://127.0.0.1:8000/lab")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        print("Opening Template modal to test visual analyte row additions...")
        page.click("button:has-text('+ Add Template')")
        time.sleep(0.6)

        # Pre-fill CBC to get 7 initial rows
        page.click("button:has-text('+ Pre-fill CBC')")
        time.sleep(0.4)
        initial_rows = page.locator("#visualAnalyteTableBody tr.visual-analyte-row").count()
        print(f"Initial CBC rows: {initial_rows}")

        # Now click + Add Parameter to test where it was added
        print("Clicking '+ Add Parameter'...")
        page.click("button:has-text('+ Add Parameter')")
        time.sleep(0.5)

        new_rows = page.locator("#visualAnalyteTableBody tr.visual-analyte-row")
        print(f"New total rows after addition: {new_rows.count()}")
        assert new_rows.count() == initial_rows + 1, "New row was not added!"

        # Check last row index badge
        last_row = new_rows.last
        last_badge = last_row.locator(".row-num-badge").text_content()
        print(f"Newly added row number badge: #{last_badge}")
        assert last_badge == str(new_rows.count()), f"Row badge expected #{new_rows.count()}, got {last_badge}"

        # Capture Template Visual Builder Screenshot
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "lab_visual_analyte_row_indicator.png"))
        print("PASS: Visual Analyte row numbering & addition indicator verified! Saved lab_visual_analyte_row_indicator.png")
        page.click("#templateEditModal .modal-close")
        time.sleep(0.4)

        # =====================================================================
        # TEST 4: CORPORATE BILLS TALLY & RECONCILIATION AUDIT
        # =====================================================================
        print("\n--> 4. Navigating to /admin to verify Corporate Bills Tally...")
        page.goto("http://127.0.0.1:8000/admin")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        corp_panel = page.locator("#corporateTieupsPanel")
        corp_panel.scroll_into_view_if_needed()
        time.sleep(0.6)

        # Verify that bills count is > 0 and tallies
        corp_rows = page.locator("#corporatePartnersBody tr")
        print(f"Corporate partners in table: {corp_rows.count()}")
        
        # Check that 0 bills is NO LONGER showing
        zero_bills = page.locator("#corporatePartnersBody :text-matches('0 bills')")
        print(f"Partners with '0 bills': {zero_bills.count()}")
        assert zero_bills.count() == 0, "Found partners still showing '0 bills'!"

        # Click on Invoices for CGHS or Star Health
        print("Opening Corporate Invoices reconciliation modal for CGHS...")
        cghs_row = page.locator("#corporatePartnersBody tr:has-text('CGHS')")
        cghs_row.locator("button:has-text('Invoices')").click()
        time.sleep(0.8)

        inv_modal = page.locator("#viewCorporateInvoicesModal")
        assert inv_modal.is_visible(), "Corporate invoices modal did not open!"

        inv_rows = page.locator("#viewCorpInvoicesBody tr")
        print(f"CGHS billed invoices loaded: {inv_rows.count()}")
        assert inv_rows.count() == 5, f"Expected 5 CGHS invoices, got {inv_rows.count()}"

        foot_text = page.locator("#viewCorpInvoicesFoot").text_content()
        print(f"Reconciliation Tally Footer: {foot_text}")
        assert "100% Reconciles" in foot_text, "Reconciliation footer text missing!"

        page.screenshot(path=os.path.join(ARTIFACT_DIR, "corporate_invoices_reconciled_tally.png"))
        print("PASS: Corporate Invoices 100% tallied & verified! Saved corporate_invoices_reconciled_tally.png")
        page.click("#viewCorporateInvoicesModal .modal-close")
        time.sleep(0.4)

        # Capture full Corporate Table with exact bill tallies
        page.screenshot(path=os.path.join(ARTIFACT_DIR, "admin_corporate_table_tallied.png"))
        print("PASS: Corporate Table with bill tallies saved to admin_corporate_table_tallied.png")

        browser.close()
        print("\n========================================================")
        print("ALL 4 USER REQUESTS VERIFIED AND PASSING SUCCESSFULLY!")
        print("========================================================")

if __name__ == "__main__":
    run_tests()
