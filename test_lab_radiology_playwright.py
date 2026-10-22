import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 950})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))

        print("[TEST] 1. Logging in as lab.john...")
        await page.goto("http://127.0.0.1:8000/login", wait_until="networkidle")
        await page.fill("#username", "lab.john")
        await page.fill("#password", "lab123")
        await page.click("button[type='submit']")
        await page.wait_for_url("**/lab", timeout=5000)
        print("[TEST] Logged in to /lab successfully!")

        await page.wait_for_selector("#labWorklistBody tr", timeout=5000)
        await page.screenshot(path="diagnostic_worklist_playwright.png")
        print("[TEST] Captured diagnostic_worklist_playwright.png")

        # 2. Test Tab Switching: Radiology Tab
        print("[TEST] 2. Testing Radiology Tab...")
        await page.click("#tabBtnRad")
        await asyncio.sleep(0.5)
        rad_count = await page.locator("#labWorklistBody tr").count()
        print(f"[TEST] Radiology tab loaded with {rad_count} orders")
        await page.screenshot(path="radiology_tab_playwright.png")

        # 3. Test Templates Studio Tab
        print("[TEST] 3. Testing Templates Tab...")
        await page.click("#tabBtnTmpl")
        await asyncio.sleep(0.5)
        await page.wait_for_selector("#templateTableBody tr", timeout=5000)
        tmpl_count = await page.locator("#templateTableBody tr").count()
        print(f"[TEST] Template studio loaded with {tmpl_count} templates")
        await page.screenshot(path="templates_studio_playwright.png")

        # 4. Switch back to All Investigations
        await page.click("#tabBtnAll")
        await asyncio.sleep(0.5)

        # 5. Open Radiology PACS Workstation for Order 2 (Chest X-Ray) or Order 3 (Brain CT)
        print("[TEST] 4. Opening Radiology PACS Workstation...")
        pacs_btn = page.locator("#labWorklistBody button[onclick*='openRadiologyStudio']").first
        await pacs_btn.click()
        await page.wait_for_selector("#radiologyStudioModal.active", timeout=5000)
        await asyncio.sleep(1.0) # wait for canvas image to load
        print("[TEST] Radiology PACS modal active and scan loaded!")
        await page.screenshot(path="radiology_pacs_modal_playwright.png")

        # 6. Test PACS Tool: Invert radiograph (negative/positive)
        print("[TEST] 5. Toggling Invert (Negative/Positive)...")
        await page.click("#btnInvertScan")
        await asyncio.sleep(0.3)

        # 7. Test PACS Tool: Draw Arrow Annotation
        print("[TEST] 6. Drawing PACS annotations on scan canvas...")
        await page.click("#toolArrow")
        canvas = page.locator("#pacsCanvas")
        box = await canvas.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            await page.mouse.move(cx - 50, cy - 50)
            await page.mouse.down()
            await page.mouse.move(cx + 40, cy + 30)
            await page.mouse.up()
            await asyncio.sleep(0.3)

        # 8. Test Caliper Ruler measurement
        await page.click("#toolMeasure")
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            await page.mouse.move(cx - 70, cy + 60)
            await page.mouse.down()
            await page.mouse.move(cx + 60, cy + 60)
            await page.mouse.up()
            await asyncio.sleep(0.3)

        await page.screenshot(path="radiology_annotated_canvas_playwright.png")
        print("[TEST] Captured radiology_annotated_canvas_playwright.png")

        # 9. Test Attach Annotated Scan
        print("[TEST] 7. Attaching annotated scan to report...")
        await page.click("button:has-text('Attach Annotated Scan')")
        await asyncio.sleep(1.0)

        # 10. Close PACS modal
        await page.click("#radiologyStudioModal .modal-close")
        await asyncio.sleep(0.5)

        # 11. Test Lab Multi-Parameter Entry for Order 1 (CBC)
        print("[TEST] 8. Testing Lab Report Entry / Editing for CBC...")
        cbc_btn = page.locator("#labWorklistBody button[onclick*='openLabResultModal']").first
        await cbc_btn.click()
        await page.wait_for_selector("#labResultModal.active", timeout=5000)
        await asyncio.sleep(0.5)
        print("[TEST] Lab report modal active with multi-parameter breakdown!")
        await page.screenshot(path="lab_multi_param_modal_playwright.png")

        # Close lab modal
        await page.click("#labResultModal .modal-close")
        await asyncio.sleep(0.5)

        # 12. Test Quick Order Investigation Modal
        print("[TEST] 9. Opening Order Investigation modal...")
        await page.click("button:has-text('+ Order Investigation')")
        await page.wait_for_selector("#orderInvestigationModal.active", timeout=5000)
        await asyncio.sleep(0.5)
        await page.screenshot(path="order_investigation_modal_playwright.png")
        await page.click("#orderInvestigationModal .modal-close")

        print("[TEST] ALL PLAYWRIGHT VERIFICATION TESTS PASSED SUCCESSFULLY!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
