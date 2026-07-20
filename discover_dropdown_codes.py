"""
Quick script to discover Bhoomi dropdown codes for specific locations.
"""

import asyncio
import json
import os
import hashlib
import subprocess
import requests
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def get_viewstate(html: str) -> tuple:
    """Extract ASP.NET state parameters."""
    soup = BeautifulSoup(html, 'html.parser')
    vs = soup.find('input', {'id': '__VIEWSTATE'})
    ev = soup.find('input', {'id': '__EVENTVALIDATION'})
    vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
    return (
        vs['value'] if vs and vs.get('value') else '',
        ev['value'] if ev and ev.get('value') else '',
        vsg['value'] if vsg and vsg.get('value') else ''
    )


def http_login():
    """Perform HTTP login to Bhoomi."""
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv("BHOOMI_USERNAME")
    password = os.getenv("BHOOMI_PASSWORD")
    
    if not username or not password:
        print("ERROR: BHOOMI_USERNAME and BHOOMI_PASSWORD must be set in .env")
        return None
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    })
    
    # Get login page
    r = session.get("https://landrecords.karnataka.gov.in/citizenportal/")
    vs, ev, vsg = get_viewstate(r.text)
    
    # Get CAPTCHA
    captcha_r = session.get("https://landrecords.karnataka.gov.in/citizenportal/GenerateCaptcha.aspx")
    os.makedirs("logs/debug", exist_ok=True)
    with open("logs/debug/captcha.png", "wb") as f:
        f.write(captcha_r.content)
    subprocess.Popen(["open", "logs/debug/captcha.png"])
    captcha = input("Enter CAPTCHA: ").strip()
    
    # Login
    session.post("https://landrecords.karnataka.gov.in/citizenportal/", data={
        "ScriptManager1": "updpanl|btnLogin",
        "txtUname": username,
        "txtCapctha": captcha,
        "HDusername": md5(username),
        "HDPassword": md5(password),
        "__ASYNCPOST": "true",
        "btnLogin": "Login",
        "__VIEWSTATE": vs,
        "__VIEWSTATEGENERATOR": vsg,
        "__EVENTVALIDATION": ev,
    }, headers={"X-Requested-With": "XMLHttpRequest"})
    
    # Navigate to dashboard
    session.get("https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx")
    
    # Navigate to IRTC page
    r_int = session.get(
        "https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
        headers={"Referer": "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"}
    )
    
    return session


async def discover_dropdown_codes():
    """Extract dropdown codes from Bhoomi IRTC page automatically."""
    
    # First login via HTTP
    print("=== Logging in to Bhoomi ===")
    session = http_login()
    if not session:
        return
    
    print("Login successful. Extracting dropdown codes...")
    
    # Convert cookies for Playwright
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
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.add_cookies(cookies_for_playwright)
        page = await context.new_page()
        
        print("Opening IRTC page with authenticated session...")
        
        # Navigate to IRTC page
        await page.goto("https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx")
        await page.wait_for_load_state("networkidle")
        
        print("\n=== EXTRACTING ALL DROPDOWN OPTIONS ===")
        
        dropdown_data = {}
        
        # Extract District dropdown
        district_select = await page.query_selector('#ctl00_MainContent_ddlCDistrict')
        if district_select:
            district_options = await district_select.query_selector_all('option')
            districts = []
            for opt in district_options:
                val = await opt.get_attribute('value')
                text = await opt.inner_text()
                if val:
                    districts.append({"value": val, "text": text.strip()})
                    # Prioritize exact "BENGALURU" match over "Bangalore Rural"
                    if text.strip() == "BENGALURU":
                        print(f"District found (exact match): {val} - {text.strip()}")
                        dropdown_data['district'] = val
                    elif 'BENGALURU' in text.upper() and 'district' not in dropdown_data:
                        print(f"District found (partial match): {val} - {text.strip()}")
                        dropdown_data['district'] = val
            dropdown_data['all_districts'] = districts
        else:
            print("District dropdown not found")
        
        # Select District if found
        if 'district' in dropdown_data:
            await page.select_option('#ctl00_MainContent_ddlCDistrict', value=dropdown_data['district'])
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
        
        # Extract Taluk dropdown
        taluk_select = await page.query_selector('#ctl00_MainContent_ddlCTaluk')
        if taluk_select:
            taluk_options = await taluk_select.query_selector_all('option')
            taluks = []
            for opt in taluk_options:
                val = await opt.get_attribute('value')
                text = await opt.inner_text()
                if val:
                    taluks.append({"value": val, "text": text.strip()})
                    if 'NORTH' in text.upper() and 'ADDITIONAL' in text.upper():
                        print(f"Taluk found: {val} - {text.strip()}")
                        dropdown_data['taluk'] = val
            dropdown_data['all_taluks'] = taluks
        else:
            print("Taluk dropdown not found")
        
        # Select Taluk if found
        if 'taluk' in dropdown_data:
            await page.select_option('#ctl00_MainContent_ddlCTaluk', value=dropdown_data['taluk'])
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)
        
        # Extract Hobli dropdown
        hobli_select = await page.query_selector('#ctl00_MainContent_ddlCHobli')
        if hobli_select:
            hobli_options = await hobli_select.query_selector_all('option')
            hoblis = []
            for opt in hobli_options:
                val = await opt.get_attribute('value')
                text = await opt.inner_text()
                if val:
                    hoblis.append({"value": val, "text": text.strip()})
                    # Prioritize YALAHANKA1
                    if text.strip() == "YALAHANKA1":
                        print(f"Hobli found (exact match): {val} - {text.strip()}")
                        dropdown_data['hobli'] = val
                    elif 'YALAHANKA' in text.upper() and 'hobli' not in dropdown_data:
                        print(f"Hobli found (partial match): {val} - {text.strip()}")
                        dropdown_data['hobli'] = val
            dropdown_data['all_hoblis'] = hoblis
        else:
            print("Hobli dropdown not found")
        
        # Select Hobli if found
        if 'hobli' in dropdown_data:
            await page.select_option('#ctl00_MainContent_ddlCHobli', value=dropdown_data['hobli'])
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
        
        # Extract Village dropdown
        village_select = await page.query_selector('#ctl00_MainContent_ddlCVillage')
        if village_select:
            village_options = await village_select.query_selector_all('option')
            villages = []
            for opt in village_options:
                val = await opt.get_attribute('value')
                text = await opt.inner_text()
                if val:
                    villages.append({"value": val, "text": text.strip()})
                    if 'KRUSHNASAGARA' in text.upper() or 'KRISHNASAGARA' in text.upper():
                        print(f"Village found: {val} - {text.strip()}")
                        dropdown_data['village'] = val
            dropdown_data['all_villages'] = villages
        else:
            print("Village dropdown not found")
        
        # Save to file
        with open("logs/debug/bhoomi_dropdown_codes.json", "w") as f:
            json.dump(dropdown_data, f, indent=2)
        
        print(f"\n=== RESULTS ===")
        print(f"District: {dropdown_data.get('district', 'NOT FOUND')}")
        print(f"Taluk: {dropdown_data.get('taluk', 'NOT FOUND')}")
        print(f"Hobli: {dropdown_data.get('hobli', 'NOT FOUND')}")
        print(f"Village: {dropdown_data.get('village', 'NOT FOUND')}")
        print(f"\nAll data saved to: logs/debug/bhoomi_dropdown_codes.json")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(discover_dropdown_codes())
