import os
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = "/Users/gauravsingh/.gemini/antigravity-ide/brain/e8942725-cc88-42e0-b783-d613dd94cf87"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1050})
    
    # 1. Doctor Earnings Chart
    page.goto("http://127.0.0.1:8000/login")
    page.fill("#username", "dr.sharma")
    page.fill("#password", "doc123")
    page.click('button[type="submit"]')
    page.wait_for_url("**/doctor")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    page.evaluate("document.getElementById('doctorCommissionChart').closest('.grid-2').scrollIntoView({behavior: 'instant', block: 'center'})")
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(ARTIFACT_DIR, "doctor_charts_playwright.png"))

    # 2. Admin Charts Full View
    page.context.clear_cookies()
    page.goto("http://127.0.0.1:8000/login")
    page.fill("#username", "admin")
    page.fill("#password", "admin123")
    page.click('button[type="submit"]')
    page.wait_for_url("**/admin")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    page.evaluate("document.getElementById('financeDoctorChart').closest('.grid-2').scrollIntoView({behavior: 'instant', block: 'center'})")
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(ARTIFACT_DIR, "admin_charts_centered_playwright.png"))
    
    print("[SUCCESS] Centered charts captured.")
    browser.close()
