#!/usr/bin/env python3
"""Quickly explore the Existing Khata form page"""
import asyncio
from playwright.async_api import async_playwright

EXISTING_KHATA_URL = "https://eswathu.karnataka.gov.in/eCitizen/Citizen/frm_CitizenPropertyList.aspx"
OUT_DIR = "/Users/smrithis/Desktop/landrecords/logs/debug/eswathu_ekatha"
import os
os.makedirs(OUT_DIR, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print(f"Navigating to: {EXISTING_KHATA_URL}")
        await page.goto(EXISTING_KHATA_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Take screenshot
        ss_path = os.path.join(OUT_DIR, "_EXPLORE_FORM_PAGE.png")
        await page.screenshot(path=ss_path, full_page=True)
        print(f"Screenshot saved: {ss_path}")
        
        # Dump all forms and inputs
        content = await page.content()
        html_path = os.path.join(OUT_DIR, "_EXPLORE_FORM_PAGE.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"HTML saved: {html_path}")
        
        # Find all select elements
        selects = await page.query_selector_all('select')
        print(f"\nFound {len(selects)} select elements:")
        for i, sel in enumerate(selects):
            try:
                sname = await sel.get_attribute('name')
                sid = await sel.get_attribute('id')
                options = await sel.query_selector_all('option')
                opts_text = []
                for opt in options[:15]:
                    t = (await opt.inner_text()).strip()
                    if t:
                        opts_text.append(t)
                print(f"  [{i}] name={sname}, id={sid}, options (first 15): {opts_text}")
            except Exception as e:
                print(f"  [{i}] ERROR: {e}")
        
        # Find all input elements
        inputs = await page.query_selector_all('input')
        print(f"\nFound {len(inputs)} input elements:")
        for i, inp in enumerate(inputs):
            try:
                itype = await inp.get_attribute('type')
                iname = await inp.get_attribute('name')
                iid = await inp.get_attribute('id')
                iplaceholder = await inp.get_attribute('placeholder')
                print(f"  [{i}] type={itype}, name={iname}, id={iid}, placeholder={iplaceholder}")
            except Exception as e:
                print(f"  [{i}] ERROR: {e}")
        
        # Find all buttons
        buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"]')
        print(f"\nFound {len(buttons)} buttons:")
        for i, btn in enumerate(buttons):
            try:
                btype = await btn.get_attribute('type')
                bname = await btn.get_attribute('name')
                bid = await btn.get_attribute('id')
                btext = (await btn.inner_text()).strip()
                bvalue = await btn.get_attribute('value')
                print(f"  [{i}] type={btype}, name={bname}, id={bid}, text='{btext[:80]}', value={bvalue}")
            except Exception as e:
                print(f"  [{i}] ERROR: {e}")
        
        print("\n✅ Page explored. Browser will stay open for 60 seconds. Look at it!")
        await page.wait_for_timeout(60000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
