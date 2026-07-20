"""
Test Bhoomi scraper with user-provided details.
Auto-fills all fields; user only enters login CAPTCHA in the browser.
"""
import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Error as PlaywrightError

from scrapers.bhoomi_scraper import BhoomiScraper, ScraperException

# User-provided test data
TEST_DATA = {
    "district": "BENGALURU",
    "taluk": "Bangalore North (Additional)",
    "hobli": "YALAHANKA1",
    "village": "KRUSHNASAGARA",
    "survey_no": "2",
    "surnoc": "*",
    "hissa_no": "1",
    "expected_owner": "ಶ್ರೀನಿವಾಸ್",
    "expected_extent": "0.28.00.00",
    "expected_khata": "32",
}

SCREENSHOT_DIR = Path("logs/debug/bhoomi_live")
SCREENSHOT_PATH = SCREENSHOT_DIR / "rtc_final_user_test.png"


async def wait_for_login(page, timeout_sec: int = 300) -> bool:
    """Wait until user completes login (dashboard reached)."""
    print("\n>>> Please enter the CAPTCHA and click Login in the browser <<<")
    print(f">>> Waiting up to {timeout_sec}s for login...\n")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        url = page.url
        if "Dashboard.aspx" in url:
            print("Login successful!")
            return True
        if "citizenportal" in url and "Login" not in url and "Default" not in url:
            # May have landed on dashboard without exact URL match
            dashboard_link = await page.query_selector('a[href="App_Intermediate_IRTC.aspx"]')
            if dashboard_link:
                print("Login successful (dashboard detected)!")
                return True
        await asyncio.sleep(1)
    return False


async def select_hissa(page, hissa_no: str) -> str:
    """Select specific Hissa number by text or value."""
    hissa_options = await page.query_selector_all("#ctl00_MainContent_ddlCHissaNo option")
    for opt in hissa_options:
        val = await opt.get_attribute("value")
        text = (await opt.inner_text()).strip()
        if not val or "Select" in text:
            continue
        if text == hissa_no or val == hissa_no:
            await page.select_option("#ctl00_MainContent_ddlCHissaNo", value=val)
            print(f"Selected Hissa: {val} - {text}")
            return val
    raise ScraperException(f"Hissa No '{hissa_no}' not found")


async def run_test():
    load_dotenv()
    if not os.getenv("BHOOMI_USERNAME"):
        load_dotenv(".env.example")

    username = os.getenv("BHOOMI_USERNAME")
    password = os.getenv("BHOOMI_PASSWORD")
    if not username or not password:
        raise ScraperException("BHOOMI_USERNAME and BHOOMI_PASSWORD must be set in .env")

    scraper = BhoomiScraper(username=username, password=password)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BHOOMI SCRAPER TEST - User Details")
    print("=" * 60)
    for k, v in TEST_DATA.items():
        if not k.startswith("expected_"):
            print(f"  {k.replace('_', ' ').title():14} = {v}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
        )
        page = await context.new_page()

        # Step 1: Login page - auto-fill credentials, user enters captcha
        await page.goto("https://landrecords.karnataka.gov.in/citizenportal/")
        await page.wait_for_load_state("networkidle")

        username_input = await page.wait_for_selector("#txtUname", timeout=15000)
        await username_input.fill(username)
        await page.wait_for_timeout(500)

        print("\n>>> Username filled automatically.")
        print(">>> Please enter the CAPTCHA in the browser.")
        print(">>> Password will be filled automatically once CAPTCHA is solved.\n")

        password_input = page.locator("#Password2")
        await password_input.wait_for(state="attached", timeout=15000)
        deadline = time.time() + 300
        while time.time() < deadline:
            if await password_input.is_enabled():
                await password_input.fill(password)
                print("Password filled automatically. Please click Login.")
                break
            await asyncio.sleep(1)
        else:
            await browser.close()
            raise ScraperException("Password field never enabled - please solve CAPTCHA first")

        await page.screenshot(path=str(SCREENSHOT_DIR / "01_login_ready.png"))

        if not await wait_for_login(page):
            await browser.close()
            raise ScraperException("Login timed out - please enter CAPTCHA and click Login")

        await page.screenshot(path=str(SCREENSHOT_DIR / "02_dashboard.png"))

        # Step 2: Open i-RTC in new tab
        async with context.expect_page() as new_page_info:
            await page.click('a[href="App_Intermediate_IRTC.aspx"]')
        irtc_page = await new_page_info.value
        await irtc_page.wait_for_load_state("networkidle")
        page = irtc_page

        # Step 3: Fill location dropdowns
        district_value = await scraper._match_dropdown_option(
            page, "#ctl00_MainContent_ddlCDistrict", TEST_DATA["district"]
        )
        if not district_value:
            raise ScraperException(f"District not found: {TEST_DATA['district']}")
        await page.select_option("#ctl00_MainContent_ddlCDistrict", value=district_value)

        if not await scraper._wait_for_dropdown_options(page, "#ctl00_MainContent_ddlCTaluk"):
            raise ScraperException("Taluk dropdown failed to load")
        taluk_value = await scraper._match_dropdown_option(
            page, "#ctl00_MainContent_ddlCTaluk", TEST_DATA["taluk"]
        )
        if not taluk_value:
            raise ScraperException(f"Taluk not found: {TEST_DATA['taluk']}")
        await page.select_option("#ctl00_MainContent_ddlCTaluk", value=taluk_value)

        if not await scraper._wait_for_dropdown_options(page, "#ctl00_MainContent_ddlCHobli"):
            raise ScraperException("Hobli dropdown failed to load")
        hobli_value = await scraper._match_dropdown_option(
            page, "#ctl00_MainContent_ddlCHobli", TEST_DATA["hobli"]
        )
        if not hobli_value:
            raise ScraperException(f"Hobli not found: {TEST_DATA['hobli']}")
        await page.select_option("#ctl00_MainContent_ddlCHobli", value=hobli_value)

        if not await scraper._wait_for_dropdown_options(page, "#ctl00_MainContent_ddlCVillage"):
            raise ScraperException("Village dropdown failed to load")
        village_value = await scraper._match_dropdown_option(
            page, "#ctl00_MainContent_ddlCVillage", TEST_DATA["village"]
        )
        if not village_value:
            raise ScraperException(f"Village not found: {TEST_DATA['village']}")
        await page.select_option("#ctl00_MainContent_ddlCVillage", value=village_value)

        await page.fill("#ctl00_MainContent_txtCSurveyNo", TEST_DATA["survey_no"])
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_form_filled.png"))

        # Step 4: Search and select Surnoc / Hissa
        await page.click("#ctl00_MainContent_btnCSearch")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        if not await scraper._wait_for_dropdown_options(page, "#ctl00_MainContent_ddlCSurnocNo"):
            raise ScraperException("Surnoc dropdown failed to load after search")

        await page.select_option("#ctl00_MainContent_ddlCSurnocNo", value=TEST_DATA["surnoc"])
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        if not await scraper._wait_for_dropdown_options(page, "#ctl00_MainContent_ddlCHissaNo"):
            raise ScraperException("Hissa dropdown failed to load after Surnoc selection")

        hissa_value = await select_hissa(page, TEST_DATA["hissa_no"])
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_before_fetch.png"))

        # Step 5: Fetch Details - may open new tab with RTC preview
        preview_page = None

        async def on_new_page(new_page):
            nonlocal preview_page
            preview_page = new_page

        context.on("page", on_new_page)

        is_disabled = await page.get_attribute("#ctl00_MainContent_btnCFetchDetails", "disabled")
        if is_disabled is not None:
            raise ScraperException("Fetch Details button is disabled")

        await page.click("#ctl00_MainContent_btnCFetchDetails")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(5000)

        # Screenshot the result page (preview tab or current page)
        target = preview_page if preview_page else page
        if preview_page:
            await preview_page.wait_for_load_state("networkidle")
            await preview_page.wait_for_timeout(3000)

        await target.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        print(f"\nFinal screenshot saved: {SCREENSHOT_PATH}")

        # Also screenshot current form page
        await page.screenshot(path=str(SCREENSHOT_DIR / "05_after_fetch.png"), full_page=True)

        content = await target.content()
        owner_found = TEST_DATA["expected_owner"] in content
        extent_found = TEST_DATA["expected_extent"] in content
        khata_found = TEST_DATA["expected_khata"] in content

        print("\n=== Verification ===")
        print(f"  Owner '{TEST_DATA['expected_owner']}': {'FOUND' if owner_found else 'NOT FOUND'}")
        print(f"  Extent '{TEST_DATA['expected_extent']}': {'FOUND' if extent_found else 'NOT FOUND'}")
        print(f"  Khata '{TEST_DATA['expected_khata']}': {'FOUND' if khata_found else 'NOT FOUND'}")
        print(f"  Hissa selected: {hissa_value}")

        if owner_found and extent_found and khata_found:
            print("\n✓ Bhoomi scraper test PASSED")
        else:
            print("\n⚠ Bhoomi scraper ran but expected data not fully matched on page")

        print("\nBrowser will stay open for 30s so you can review...")
        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except ScraperException as e:
        print(f"\n✗ Scraper error: {e}")
    except PlaywrightError as e:
        print(f"\n✗ Playwright error: {e}")
