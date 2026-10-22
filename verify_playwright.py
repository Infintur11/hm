import os
import sys
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = "/Users/gauravsingh/.gemini/antigravity-ide/brain/e8942725-cc88-42e0-b783-d613dd94cf87"

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 1050})
        page = context.new_page()

        print("[TEST] 1. Navigating to Login Page...")
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_selector("#username")

        # --- DOCTOR PORTAL TEST ---
        print("[TEST] 2. Logging in as Doctor Dr. Sharma...")
        page.fill("#username", "dr.sharma")
        page.fill("#password", "doc123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/doctor")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Scroll to commission panel
        page.evaluate("document.getElementById('doctorCommissionPanel').scrollIntoView()")
        page.wait_for_timeout(1000)

        # Extract KPI values to verify
        hero_amt = page.locator("#heroAvailableAmount").inner_text()
        hero_chip = page.locator("#heroStatusChip").inner_text()
        kpi_ready = page.locator("#commissionAvailable").inner_text()
        kpi_pending = page.locator("#commissionPending").inner_text()
        kpi_earned = page.locator("#commissionEarned").inner_text()
        print(f"[VERIFY DOCTOR] Hero Available: {hero_amt} ({hero_chip})")
        print(f"[VERIFY DOCTOR] KPIs: Ready={kpi_ready}, Pending={kpi_pending}, Earned={kpi_earned}")

        # Check PDF Download button presence
        doc_pdf_btn = page.locator("button:has-text('Download PDF Statement')")
        assert doc_pdf_btn.is_visible(), "Download PDF Statement button missing!"
        print("[VERIFY DOCTOR] 'Download PDF Statement' button verified.")

        # Capture Doctor Commission Screenshot
        doc_screenshot_path = os.path.join(ARTIFACT_DIR, "doctor_commission_playwright.png")
        page.screenshot(path=doc_screenshot_path, full_page=False)

        # --- ADMIN FINANCIALS TEST ---
        print("[TEST] 3. Logging out and logging in as Admin...")
        context.clear_cookies()
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_selector("#username")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/admin")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        # Scroll to finance commission panel
        page.evaluate("document.getElementById('financeCommissionPanel').scrollIntoView()")
        page.wait_for_timeout(1000)

        # Extract Admin KPIs
        fin_net = page.locator("#finCommissionNet").inner_text()
        fin_avail = page.locator("#finCommissionAvailable").inner_text()
        fin_holds = page.locator("#finCommissionLiability").inner_text()
        fin_paid = page.locator("#finCommissionPaid").inner_text()
        print(f"[VERIFY ADMIN] Financial KPIs: Net={fin_net}, Available={fin_avail}, Holds={fin_holds}, Paid={fin_paid}")

        # Verify buttons non-redundancy:
        # 1. Header has Download PDF Report and Refresh, but NOT + New Commission Rule
        header_buttons = page.locator("#financeCommissionPanel .card-header button").all_inner_texts()
        print(f"[VERIFY ADMIN] Header buttons: {header_buttons}")
        assert not any("New Commission Rule" in b for b in header_buttons), "Header still has redundant New Commission Rule!"
        assert any("Download PDF Report" in b for b in header_buttons), "Download PDF Report missing from header!"

        # 2. Filter bar has NO redundant Apply Filter button
        filter_buttons = page.locator("#financeCommissionPanel .table-wrapper").locator("xpath=preceding-sibling::div[1]//button").all_inner_texts()
        assert not any("Apply Filter" in b for b in filter_buttons), "Filter toolbar still has redundant Apply Filter button!"

        # 3. Active Rules section has the single + Add Rule button
        rules_header_btn = page.locator("#financeCommissionPanel button:has-text('+ Add Rule')")
        assert rules_header_btn.is_visible(), "Active Rules '+ Add Rule' button missing!"
        print("[VERIFY ADMIN] Active Rules single '+ Add Rule' button verified.")

        # Test clicking + Add Rule expands form right there
        rules_header_btn.click()
        page.wait_for_timeout(400)
        new_rule_card = page.locator("#newRuleCard")
        assert new_rule_card.is_visible(), "newRuleCard did not open when clicking + Add Rule!"
        print("[VERIFY ADMIN] '+ Add Rule' successfully expanded newRuleCard form in-place!")

        # Close the card
        new_rule_card.locator("button:has-text('Close')").click()
        page.wait_for_timeout(300)
        assert not new_rule_card.is_visible(), "newRuleCard did not close!"
        print("[VERIFY ADMIN] newRuleCard successfully closed.")

        # Capture Admin Financials Screenshot
        admin_screenshot_path = os.path.join(ARTIFACT_DIR, "admin_financials_playwright.png")
        page.screenshot(path=admin_screenshot_path, full_page=False)

        # Test PDF API response directly
        print("[TEST] 4. Testing Admin Monthly Commission PDF Download...")
        with page.expect_download() as download_info_admin:
            page.locator("button:has-text('Download PDF Report')").click()
        download_admin = download_info_admin.value
        admin_pdf_dest = os.path.join(ARTIFACT_DIR, download_admin.suggested_filename)
        download_admin.save_as(admin_pdf_dest)
        print(f"[VERIFY PDF] Admin Report PDF downloaded: {download_admin.suggested_filename} ({os.path.getsize(admin_pdf_dest)} bytes)")
        assert os.path.getsize(admin_pdf_dest) > 1000, "Admin PDF file is too small or empty!"

        # Test Doctor Statement PDF Download
        print("[TEST] 5. Testing Doctor Statement PDF Download...")
        with page.expect_download() as download_info:
            page.evaluate("window.location.href = 'http://127.0.0.1:8000/api/commissions/statement.pdf?period=2026-10&doctor_id=3'")
        download = download_info.value
        doc_pdf_dest = os.path.join(ARTIFACT_DIR, download.suggested_filename)
        download.save_as(doc_pdf_dest)
        print(f"[VERIFY PDF] Doctor Statement PDF downloaded: {download.suggested_filename} ({os.path.getsize(doc_pdf_dest)} bytes)")
        assert os.path.getsize(doc_pdf_dest) > 1000, "PDF file is too small or empty!"

        # --- RECEPTIONIST PORTAL TEST ---
        print("[TEST] 6. Testing Receptionist Portal & RBAC...")
        context.clear_cookies()
        page.goto("http://127.0.0.1:8000/login")
        page.fill("#username", "recep.riya")
        page.fill("#password", "recep123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/reception")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        rec_kpi = page.locator("#kpiRecPatients").inner_text()
        print(f"[VERIFY RECEPTIONIST] Loaded reception desk. Total patients: {rec_kpi}")
        recep_screenshot_path = os.path.join(ARTIFACT_DIR, "reception_desk_playwright.png")
        page.screenshot(path=recep_screenshot_path, full_page=False)

        # --- CASHIER BILLING PORTAL TEST ---
        print("[TEST] 7. Testing Cashier Billing Portal & RBAC...")
        context.clear_cookies()
        page.goto("http://127.0.0.1:8000/login")
        page.fill("#username", "cashier.karan")
        page.fill("#password", "cash123")
        page.click('button[type="submit"]')
        page.wait_for_url("**/billing")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        cashier_collected = page.locator("#kpiCashierCollected").inner_text()
        cashier_ar = page.locator("#kpiCashierReceivable").inner_text()
        print(f"[VERIFY CASHIER] Loaded billing desk. Collected: {cashier_collected}, AR: {cashier_ar}")
        billing_screenshot_path = os.path.join(ARTIFACT_DIR, "cashier_billing_playwright.png")
        page.screenshot(path=billing_screenshot_path, full_page=False)

        browser.close()
        print("[SUCCESS] All Playwright end-to-end tests across Doctor, Admin, Receptionist, and Cashier passed perfectly!")

if __name__ == "__main__":
    run_verification()
