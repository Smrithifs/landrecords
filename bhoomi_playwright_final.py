import asyncio
import requests
import hashlib
import os
import json
import subprocess
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
if not os.getenv("BHOOMI_USERNAME"):
    load_dotenv(".env.example")
username = os.getenv("BHOOMI_USERNAME")
password = os.getenv("BHOOMI_PASSWORD")

def md5(t): return hashlib.md5(t.encode()).hexdigest()

def get_vs(html):
    soup = BeautifulSoup(html, 'html.parser')
    vs = soup.find('input', {'id': '__VIEWSTATE'})
    ev = soup.find('input', {'id': '__EVENTVALIDATION'})
    vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
    return (vs['value'] if vs and vs.get('value') else '',
            ev['value'] if ev and ev.get('value') else '',
            vsg['value'] if vsg and vsg.get('value') else '')

# === STEP 1: Full HTTP login + navigation (already working) ===
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"})

r = session.get("https://landrecords.karnataka.gov.in/citizenportal/")
vs, ev, vsg = get_vs(r.text)
captcha_r = session.get("https://landrecords.karnataka.gov.in/citizenportal/GenerateCaptcha.aspx")
os.makedirs("logs/debug", exist_ok=True)
with open("logs/debug/captcha.png", "wb") as f: f.write(captcha_r.content)
subprocess.Popen(["open", "logs/debug/captcha.png"])
captcha = input("Enter CAPTCHA: ").strip()

session.post("https://landrecords.karnataka.gov.in/citizenportal/", data={
    "ScriptManager1": "updpanl|btnLogin", "txtUname": username,
    "txtCapctha": captcha, "HDusername": md5(username), "HDPassword": md5(password),
    "__ASYNCPOST": "true", "btnLogin": "Login",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"X-Requested-With": "XMLHttpRequest"})

session.get("https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx")
r_int = session.get("https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
    headers={"Referer": "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"})
soup_int = BeautifulSoup(r_int.text, 'html.parser')
form = soup_int.find('form')
form_data = {inp.get('name'): inp.get('value','') for inp in form.find_all('input')}
r_s37 = session.post(form.get('action'), data=form_data, headers={
    "Referer": "https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
    "Origin": "https://landrecords.karnataka.gov.in"
})
print(f"HTTP session ready. Cookies: {list(session.cookies.keys())}")

# === STEP 2: Inject cookies into Playwright and finish with browser ===
cookies_for_playwright = []
for c in session.cookies:
    cookie = {
        "name": c.name,
        "value": c.value,
        "domain": "landrecords.karnataka.gov.in",
        "path": "/",
        "secure": True,
        "httpOnly": c.name in ["ASP.NET_SessionId", "Id"]
    }
    cookies_for_playwright.append(cookie)
print(f"Cookies for Playwright: {cookies_for_playwright}")

async def get_rtc():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Inject cookies
        await context.add_cookies(cookies_for_playwright)
        page = await context.new_page()
        
        # First go to citizenportal dashboard to establish context
        await page.goto(
            "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"
        )
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="logs/debug/pw_dashboard.png")
        print(f"Dashboard URL: {page.url}")
        
        # Check if logged in
        if "Login" in page.url:
            print("Not logged in - cookies not working")
            return
        
        # Click i-RTC link (same as user clicking it)
        await page.click('a[href="App_Intermediate_IRTC.aspx"]')
        
        # This opens a new tab - switch to it
        async with context.expect_page() as new_page_info:
            await page.click('a[href="App_Intermediate_IRTC.aspx"]')
        new_page = await new_page_info.value
        await new_page.wait_for_load_state("networkidle")
        print(f"New tab URL: {new_page.url}")
        await new_page.screenshot(path="logs/debug/pw_service37.png")
        
        # Now work with new_page for all dropdowns
        page = new_page
        
        # Select District
        await page.select_option(
            '#ctl00_MainContent_ddlCDistrict', value='20'
        )
        await page.wait_for_load_state("networkidle")
        
        # Select Taluk  
        await page.select_option(
            '#ctl00_MainContent_ddlCTaluk', value='5'
        )
        await page.wait_for_load_state("networkidle")
        
        # Select Hobli
        await page.select_option(
            '#ctl00_MainContent_ddlCHobli', value='1'
        )
        await page.wait_for_load_state("networkidle")
        
        # Select Village
        await page.select_option(
            '#ctl00_MainContent_ddlCVillage', value='15'
        )
        await page.wait_for_load_state("networkidle")
        
        # Survey number
        await page.fill('#ctl00_MainContent_txtCSurveyNo', '2')
        
        # Click GO
        await page.click('#ctl00_MainContent_btnCSearch')
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Take screenshot after GO to see what populated
        await page.screenshot(path="logs/debug/after_go.png")
        subprocess.Popen(["open", "logs/debug/after_go.png"])

        # Print all Surnoc options after GO click
        surnoc_options = await page.query_selector_all('#ctl00_MainContent_ddlCSurnocNo option')
        print(f"Surnoc options count: {len(surnoc_options)}")
        for opt in surnoc_options:
            value = await opt.get_attribute('value')
            text = await opt.text_content()
            print(f"  Surnoc option: value='{value}' text='{text}'")

        # Print all Hissa options
        hissa_options = await page.query_selector_all('#ctl00_MainContent_ddlCHissaNo option')
        print(f"Hissa options count: {len(hissa_options)}")
        for opt in hissa_options:
            value = await opt.get_attribute('value')
            text = await opt.text_content()
            print(f"  Hissa option: value='{value}' text='{text}'")

        # Select Surnoc *
        await page.select_option(
            '#ctl00_MainContent_ddlCSurnocNo', value='*'
        )
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Get available Hissa options and select first real one
        hissa_options = await page.query_selector_all(
            '#ctl00_MainContent_ddlCHissaNo option'
        )
        hissa_value = None
        for opt in hissa_options:
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            print(f"Hissa option: value='{val}' text='{text}'")
            if val and val != '' and 'Select' not in text:
                hissa_value = val
                break

        if hissa_value:
            await page.select_option(
                '#ctl00_MainContent_ddlCHissaNo', value=hissa_value
            )
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
            print(f"Selected Hissa: {hissa_value}")
        else:
            print("No valid Hissa option found")

        # Now check if Fetch Details is enabled
        is_disabled = await page.get_attribute(
            '#ctl00_MainContent_btnCFetchDetails', 'disabled'
        )
        print(f"Button disabled: {is_disabled}")

        if is_disabled is None:
            # Set up listener for new page BEFORE clicking
            async def handle_new_page(new_page):
                print(f"New page opening: {new_page.url}")
                await new_page.wait_for_load_state("networkidle")
                await new_page.wait_for_timeout(3000)
                print(f"New page loaded: {new_page.url}")
                await new_page.screenshot(
                    path="logs/debug/rtc_final.png",
                    full_page=True
                )
                subprocess.Popen(["open", "logs/debug/rtc_final.png"])
                print("SUCCESS: PreviewRTC screenshot saved!")

            context.on("page", handle_new_page)

            # Now click Fetch Details
            await page.click('#ctl00_MainContent_btnCFetchDetails')
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(5000)

            # Parse HTML content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Owner table
            owner_table = soup.find('table')
            rtc_data = {
                "survey_no": "2",
                "hissa_no": "6",
                "year": "2025-2026"
            }

            if owner_table:
                rows = owner_table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if cols:
                        owner = cols[0].text.strip()
                        extent = cols[1].text.strip()
                        khata = cols[2].text.strip()
                        print(f"Owner: {owner}")
                        print(f"Extent: {extent}")
                        print(f"Khata: {khata}")
                        rtc_data["owner"] = owner
                        rtc_data["extent"] = extent
                        rtc_data["khata_no"] = khata

            # RTC Details
            for label in soup.find_all('b'):
                text = label.text.strip()
                sibling = label.next_sibling
                if sibling:
                    sibling_text = str(sibling).strip()
                    print(f"{text}: {sibling_text}")
                    if "Village" in text:
                        rtc_data["village"] = sibling_text
                    elif "Validity" in text:
                        rtc_data["rtc_validity"] = sibling_text

            # Save to JSON
            os.makedirs("logs/debug", exist_ok=True)
            with open("logs/debug/rtc_data.json", "w") as f:
                json.dump(rtc_data, f, indent=2)
            print("RTC data saved to logs/debug/rtc_data.json")

            # Take screenshot of current page to see what's displayed
            await page.screenshot(path="logs/debug/after_fetch.png")
            subprocess.Popen(["open", "logs/debug/after_fetch.png"])
            print("Screenshot of current page saved")

            # Wait long enough for new page to open and screenshot
            await asyncio.sleep(10)

            print("Done")

        else:
            print("Button still disabled even after Hissa selection")

        await browser.close()

asyncio.run(get_rtc())
