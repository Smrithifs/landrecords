import asyncio
import os
import time
from typing import Dict, Optional
from playwright.async_api import async_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup
import requests
import pytesseract
from PIL import Image
import re
from datetime import datetime
from sqlalchemy import select, update
from database.models import BhoomiRTC, ScraperHealth
from database.connection import get_database
from scrapers.bhoomi_base import BhoomiBaseScraper, ScraperException


class BhoomiScraper(BhoomiBaseScraper):
    """Bhoomi RTC scraper using Playwright with manual CAPTCHA handling"""
    
    async def fetch_rtc(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str
    ) -> Dict:
        """
        Fetch RTC data from Bhoomi portal
        
        Args:
            district: District name (e.g., 'BENGALURU')
            taluk: Taluk name (e.g., 'Bangalore North (Additional)')
            hobli: Hobli name (e.g., 'YALAHANKA1')
            village: Village name (e.g., 'KRUSHNASAGARA')
            survey_no: Survey number (e.g., '2')
        
        Returns:
            Dict with keys: owner_name, khata_no, land_use, soil_type, 
            area_dryland_acres, area_wetland_acres, area_total_acres, encumbrances_text
        
        Raises:
            ScraperException: If any step fails
        """
        async def _fetch():
            # Check if we have a valid cached session
            if self._is_session_valid():
                print("Using cached session (age: {:.1f} minutes)".format(
                    (time.time() - self._session_timestamp) / 60
                ))
                cookies_for_playwright = self._session_cache
            else:
                print("Session cache expired or missing, performing fresh login")
                cookies_for_playwright = await self._http_login()
                print(f"Login successful. Cookies: {[c['name'] for c in cookies_for_playwright]}")
                self._update_session_cache(cookies_for_playwright)
            
            # Playwright automation
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                
                # Inject cookies
                await context.add_cookies(cookies_for_playwright)
                page = await context.new_page()
                
                # Navigate to dashboard
                await page.goto("https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx")
                await page.wait_for_load_state("networkidle")
                
                # Check if logged in
                if "Login" in page.url:
                    await browser.close()
                    self._session_cache = None
                    self._session_timestamp = None
                    raise ScraperException("Not logged in - cookies not working")
                
                # Click i-RTC link (base class already established session via service37 POST)
                async with context.expect_page() as new_page_info:
                    await page.click('a[href="App_Intermediate_IRTC.aspx"]')
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("networkidle")
                page = new_page
                
                # Print VIEWSTATE and EVENTVALIDATION from service37 page load
                print("=== SERVICE37 PAGE LOAD HIDDEN FIELDS ===")
                page_content = await page.content()
                soup = BeautifulSoup(page_content, 'html.parser')
                viewstate = soup.find('input', {'id': '__VIEWSTATE'})
                eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})
                viewstategenerator = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
                
                if viewstate:
                    print(f"__VIEWSTATE length: {len(viewstate.get('value', ''))}")
                else:
                    print("__VIEWSTATE NOT FOUND")
                
                if eventvalidation:
                    print(f"__EVENTVALIDATION length: {len(eventvalidation.get('value', ''))}")
                else:
                    print("__EVENTVALIDATION NOT FOUND")
                
                if viewstategenerator:
                    print(f"__VIEWSTATEGENERATOR: {viewstategenerator.get('value', '')}")
                else:
                    print("__VIEWSTATEGENERATOR NOT FOUND")
                
                # Select District using Playwright
                district_value = await self._match_dropdown_option(page, '#ctl00_MainContent_ddlCDistrict', district)
                if not district_value:
                    await browser.close()
                    raise ScraperException(f"District not found: {district}")
                await page.select_option('#ctl00_MainContent_ddlCDistrict', value=district_value)
                
                # Wait for page to process - use network idle
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Check how many taluk options loaded
                taluk_count = await page.eval_on_selector(
                    '#ctl00_MainContent_ddlCTaluk',
                    'el => el.options.length'
                )
                print(f"Taluk options count: {taluk_count}")
                
                # If still 1 option, try dispatching change event manually
                if taluk_count <= 1:
                    print("Taluk not loaded, trying change event...")
                    await page.dispatch_event('#ctl00_MainContent_ddlCDistrict', 'change')
                    await page.wait_for_timeout(3000)
                    taluk_count = await page.eval_on_selector(
                        '#ctl00_MainContent_ddlCTaluk',
                        'el => el.options.length'
                    )
                    print(f"Taluk options after change event: {taluk_count}")
                
                # Print all available taluk options
                options = await page.eval_on_selector_all(
                    '#ctl00_MainContent_ddlCTaluk option',
                    'els => els.map(e => e.text)'
                )
                print(f"Taluk options: {options}")
                
                # Take screenshot
                os.makedirs("logs/debug", exist_ok=True)
                await page.screenshot(path='logs/debug/after_district_select.png')
                print("Screenshot saved to logs/debug/after_district_select.png")
                
                # Select Taluk using Playwright
                taluk_value = await self._match_dropdown_option(page, '#ctl00_MainContent_ddlCTaluk', taluk)
                if not taluk_value:
                    await browser.close()
                    raise ScraperException(f"Taluk not found: {taluk}")
                await page.select_option('#ctl00_MainContent_ddlCTaluk', value=taluk_value)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Check hobli options count
                hobli_count = await page.eval_on_selector(
                    '#ctl00_MainContent_ddlCHobli',
                    'el => el.options.length'
                )
                print(f"Hobli options count: {hobli_count}")
                
                # If still 1 option, try dispatching change event manually
                if hobli_count <= 1:
                    print("Hobli not loaded, trying change event...")
                    await page.dispatch_event('#ctl00_MainContent_ddlCTaluk', 'change')
                    await page.wait_for_timeout(3000)
                    hobli_count = await page.eval_on_selector(
                        '#ctl00_MainContent_ddlCHobli',
                        'el => el.options.length'
                    )
                    print(f"Hobli options after change event: {hobli_count}")
                
                # Print all available hobli options
                hobli_options = await page.eval_on_selector_all(
                    '#ctl00_MainContent_ddlCHobli option',
                    'els => els.map(e => e.text)'
                )
                print(f"Hobli options: {hobli_options}")
                
                # Select Hobli using Playwright
                hobli_value = await self._match_dropdown_option(page, '#ctl00_MainContent_ddlCHobli', hobli)
                if not hobli_value:
                    await browser.close()
                    raise ScraperException(f"Hobli not found: {hobli}")
                await page.select_option('#ctl00_MainContent_ddlCHobli', value=hobli_value)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Check village options count
                village_count = await page.eval_on_selector(
                    '#ctl00_MainContent_ddlCVillage',
                    'el => el.options.length'
                )
                print(f"Village options count: {village_count}")
                
                # If still 1 option, try dispatching change event manually
                if village_count <= 1:
                    print("Village not loaded, trying change event...")
                    await page.dispatch_event('#ctl00_MainContent_ddlCHobli', 'change')
                    await page.wait_for_timeout(3000)
                    village_count = await page.eval_on_selector(
                        '#ctl00_MainContent_ddlCVillage',
                        'el => el.options.length'
                    )
                    print(f"Village options after change event: {village_count}")
                
                # Print all available village options
                village_options = await page.eval_on_selector_all(
                    '#ctl00_MainContent_ddlCVillage option',
                    'els => els.map(e => e.text)'
                )
                print(f"Village options: {village_options}")
                
                # Select Village using Playwright
                village_value = await self._match_dropdown_option(page, '#ctl00_MainContent_ddlCVillage', village)
                if not village_value:
                    await browser.close()
                    raise ScraperException(f"Village not found: {village}")
                await page.select_option('#ctl00_MainContent_ddlCVillage', value=village_value)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Fill survey number
                await page.fill('#ctl00_MainContent_txtCSurveyNo', survey_no)
                await page.wait_for_timeout(500)
                
                # Take screenshot before GO click
                await page.screenshot(path='logs/debug/before_go_click.png')
                print("Screenshot saved - check logs/debug/before_go_click.png")
                
                # Check if GO button exists
                go_button_exists = await page.is_visible('#ctl00_MainContent_btnGo')
                print(f"GO button visible: {go_button_exists}")
                
                if go_button_exists:
                    # Click GO button using JavaScript
                    await page.evaluate("document.querySelector('#ctl00_MainContent_btnGo').click()")
                    print("GO button clicked")
                else:
                    print("GO button not found, trying alternative selector...")
                    # Try alternative selector
                    await page.evaluate("document.querySelector('#ctl00_MainContent_btnCSearch').click()")
                    print("Tried btnCSearch instead")
                
                # Keep browser open and wait for surnoc
                await page.wait_for_timeout(2000)
                
                # Check if surnoc is enabled now
                is_disabled = await page.get_attribute('#ctl00_MainContent_ddlCSurnocNo', 'disabled')
                print(f"Surnoc disabled attribute: {is_disabled}")
                
                # Take screenshot to see current state
                await page.screenshot(path='logs/debug/after_go_click.png')
                print("Screenshot saved - check logs/debug/after_go_click.png")
                
                # Wait for surnoc to become enabled
                try:
                    await page.wait_for_function(
                        """() => {
                            const el = document.querySelector('#ctl00_MainContent_ddlCSurnocNo');
                            return el && !el.disabled && el.options.length > 1;
                        }""",
                        timeout=15000
                    )
                    print("Surnoc dropdown enabled and loaded")
                except:
                    print("Surnoc not enabled, trying change event on village...")
                    await page.dispatch_event('#ctl00_MainContent_ddlCVillage', 'change')
                    await page.wait_for_timeout(5000)
                
                # Now print surnoc options
                surnoc_options = await page.eval_on_selector_all(
                    '#ctl00_MainContent_ddlCSurnocNo option',
                    'els => els.map(e => ({value: e.value, text: e.text.trim()}))'
                )
                print(f"Surnoc options: {surnoc_options}")
                
                # Select first available surnoc
                for opt in surnoc_options:
                    if 'select' not in opt['text'].lower():
                        await page.select_option('#ctl00_MainContent_ddlCSurnocNo', value=opt['value'])
                        await page.wait_for_timeout(2000)
                        print(f"Selected Surnoc: {opt['value']} - {opt['text']}")
                        break
                
                # Select first available hissa
                hissa_options = await page.eval_on_selector_all(
                    '#ctl00_MainContent_ddlCHissaNo option',
                    'els => els.map(e => ({value: e.value, text: e.text.trim()}))'
                )
                print(f"Hissa options: {hissa_options}")
                for opt in hissa_options:
                    if 'select' not in opt['text'].lower():
                        await page.select_option('#ctl00_MainContent_ddlCHissaNo', value=opt['value'])
                        await page.wait_for_timeout(2000)
                        print(f"Selected Hissa: {opt['value']} - {opt['text']}")
                        break
                
                # Click Fetch Details
                await page.click('#ctl00_MainContent_btnFetch')
                await page.wait_for_timeout(5000)
                await page.screenshot(path='logs/debug/after_fetch.png')
                print("Screenshot saved to logs/debug/after_fetch.png")
                
                # Wait for loading to complete (wait for loading spinner to disappear)
                print("Waiting for data to load...")
                try:
                    # Wait for loading element to disappear (common loading patterns)
                    await page.wait_for_selector('div:has-text("LOADING"), .loading, #loading, [id*="loading"], [class*="loading"]', state="hidden", timeout=60000)
                    print("Loading complete")
                except PlaywrightError:
                    print("No loading element found or timeout, proceeding anyway")
                
                # Additional wait to ensure data is fully rendered
                await page.wait_for_timeout(3000)
                
                # Part 1: Extract summary data from the summary page (before View RTC)
                print("Extracting summary data from summary page...")
                summary_content = await page.content()
                summary_soup = BeautifulSoup(summary_content, 'html.parser')
                
                rtc_data = {
                    "district": district,
                    "taluk": taluk,
                    "hobli": hobli,
                    "village": village,
                    "survey_no": survey_no,
                    "surnoc": "*",
                    "hissa_no": hissa_text if hissa_text else hissa_value,  # Use visible text (e.g., "1") not option value (e.g., "6")
                    "owner_name": None,
                    "khata_no": None,
                    "area_total_acres": None,
                    # Note: The following fields may remain null if not available from HTML/API or OCR
                    "land_use": None,
                    "soil_type": None,
                    "area_dryland_acres": None,
                    "area_wetland_acres": None,
                    "encumbrances_text": None,
                    "rtc_validity": None,
                    "screenshot_path": None,
                    "rtc_png_path": None
                }
                
                # Parse owner table from summary page
                tables = summary_soup.find_all('table')
                owner_found = False
                
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if cols and len(cols) >= 3:
                            # Look for owner name pattern (Kannada or English)
                            text0 = cols[0].text.strip()
                            text1 = cols[1].text.strip()
                            text2 = cols[2].text.strip()
                            
                            # Check if this looks like owner data (has numbers for extent/khata)
                            if text1 and any(c.isdigit() for c in text1):
                                rtc_data["owner_name"] = text0
                                extent = text1
                                rtc_data["khata_no"] = text2
                                owner_found = True
                                
                                # Parse extent (format: 0.28.00.00)
                                if extent:
                                    parts = extent.split('.')
                                    if len(parts) >= 4:
                                        rtc_data["area_total_acres"] = f"{parts[0]}.{parts[1]}.{parts[2]}"
                                break
                    if owner_found:
                        break
                
                print(f"Summary data extracted: owner={rtc_data['owner_name']}, khata={rtc_data['khata_no']}, area={rtc_data['area_total_acres']}")
                
                # Part 2: Navigate to View RTC and download PNG
                view_rtc_button = await page.query_selector('a:has-text("View RTC"), input[value*="View"], input[value*="RTC"], button:has-text("View")')
                if view_rtc_button:
                    print("Found View RTC button, clicking...")
                    async with context.expect_page() as new_page_info:
                        await view_rtc_button.click()
                    rtc_view_page = await new_page_info.value
                    await rtc_view_page.wait_for_load_state("networkidle")
                    await rtc_view_page.wait_for_timeout(3000)
                    page = rtc_view_page
                    print("Navigated to RTC view page")
                else:
                    print("No View RTC button found, using current page")
                
                # Extract PNG URL from img#ImgSketchPage
                # Initialize response tracking for final verification
                http_status = 'N/A'
                content_type = 'N/A'
                
                img_element = await page.query_selector('#ImgSketchPage')
                if img_element:
                    png_url = await img_element.get_attribute('src')
                    print(f"Found RTC PNG URL: {png_url}")
                    
                    # PART 1: Verify the download with detailed logging
                    os.makedirs("logs/debug", exist_ok=True)
                    png_path = "logs/debug/rtc_full_document.png"
                    
                    # Get cookies from context
                    cookies = await context.cookies()
                    cookie_dict = {c['name']: c['value'] for c in cookies}
                    
                    # Get current page URL for Referer header
                    current_url = page.url
                    
                    # PART 3: Download using authenticated session with proper headers
                    headers = {
                        'Referer': current_url,
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    
                    print(f"\n=== DOWNLOAD DETAILS ===")
                    print(f"Request URL: {png_url}")
                    print(f"Referer: {current_url}")
                    
                    response = requests.get(png_url, cookies=cookie_dict, headers=headers, allow_redirects=True)
                    
                    # Track for final verification
                    http_status = response.status_code
                    content_type = response.headers.get('Content-Type', 'unknown')
                    
                    print(f"Status: {response.status_code}")
                    print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                    print(f"Content-Length: {response.headers.get('Content-Length', 'unknown')}")
                    print(f"Final URL: {response.url}")
                    
                    # PART 2: Handle non-image responses
                    content_type = response.headers.get('Content-Type', '').lower()
                    if response.status_code == 200:
                        if 'image' in content_type:
                            # Save as PNG
                            with open(png_path, 'wb') as f:
                                f.write(response.content)
                            print(f"RTC PNG downloaded to: {png_path}")
                            
                            # PART 4: Verify image before OCR
                            try:
                                Image.open(png_path)
                                print("✓ Downloaded file is a valid image")
                                rtc_data["rtc_png_path"] = png_path
                            except Exception as e:
                                print(f"✗ Downloaded file is not a valid image: {e}")
                                print("Skipping OCR")
                                # Remove invalid file
                                if os.path.exists(png_path):
                                    os.remove(png_path)
                                rtc_data["rtc_png_path"] = None
                        else:
                            # Save as HTML for debugging
                            html_path = "logs/debug/rtc_response.html"
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            print(f"\nDownloaded response is not an image (Content-Type: {content_type})")
                            print(f"Saved response to: {html_path}")
                            print(f"First 1000 characters of response:")
                            print(response.text[:1000])
                            rtc_data["rtc_png_path"] = None
                    else:
                        print(f"Failed to download: HTTP {response.status_code}")
                        rtc_data["rtc_png_path"] = None
                    
                    # PART 5: If download failed, use Playwright screenshot of RTC image element
                    if not rtc_data["rtc_png_path"]:
                        print("\nDownload failed, using Playwright screenshot of RTC image element...")
                        try:
                            # Screenshot just the image element
                            await img_element.screenshot(path=png_path)
                            print(f"RTC image screenshot saved to: {png_path}")
                            rtc_data["rtc_png_path"] = png_path
                            
                            # Verify the screenshot
                            try:
                                Image.open(png_path)
                                print("✓ Screenshot is a valid image")
                            except Exception as e:
                                print(f"✗ Screenshot is not a valid image: {e}")
                                rtc_data["rtc_png_path"] = None
                        except Exception as e:
                            print(f"Failed to screenshot image element: {e}")
                            rtc_data["rtc_png_path"] = None
                else:
                    print("PNG image element not found")
                
                # Part 2: Inspect View RTC page for fields in HTML/hidden inputs/JS before OCR
                print("Inspecting View RTC page for data in HTML/hidden inputs/JS...")
                view_content = await page.content()
                view_soup = BeautifulSoup(view_content, 'html.parser')
                
                extraction_method = None
                
                # Check for rtc_validity in HTML text
                for label in view_soup.find_all(['b', 'strong', 'span', 'div', 'td', 'th']):
                    text = label.get_text(strip=True)
                    if 'valid' in text.lower() or 'till' in text.lower():
                        # Look for patterns like "Valid from 25/02/2015 11:01:00 Till Date"
                        validity_match = re.search(r'valid\s+from\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', text, re.IGNORECASE)
                        if validity_match:
                            rtc_data["rtc_validity"] = f"Valid from {validity_match.group(1)} Till Date"
                            extraction_method = "HTML"
                            print(f"Found rtc_validity in HTML: {rtc_data['rtc_validity']}")
                            break
                        # Also check if the text itself contains the validity info with date pattern
                        if 'from' in text.lower() and ('till' in text.lower() or 'to' in text.lower()):
                            date_match = re.search(r'\d{2}/\d{2}/\d{4}', text)
                            if date_match:
                                rtc_data["rtc_validity"] = text.strip()
                                extraction_method = "HTML"
                                print(f"Found rtc_validity in HTML: {rtc_data['rtc_validity']}")
                                break
                
                # Check for hidden inputs - skip validity extraction from hidden inputs (they contain encrypted tokens)
                hidden_inputs = view_soup.find_all('input', type='hidden')
                for inp in hidden_inputs:
                    name = inp.get('name', '')
                    value = inp.get('value', '')
                    if value and any(kw in name.lower() for kw in ['land', 'soil', 'area', 'use', 'encumbrance']):
                        print(f"Found hidden input: {name} = {value}")
                
                # Check for data in JavaScript variables
                scripts = view_soup.find_all('script')
                for script in scripts:
                    if script.string:
                        script_content = script.string
                        # Look for validity in JS
                        validity_match = re.search(r'validity["\']?\s*[:=]\s*["\']([^"\']+)["\']', script_content, re.IGNORECASE)
                        if validity_match:
                            rtc_data["rtc_validity"] = validity_match.group(1).strip()
                            extraction_method = "JavaScript"
                            print(f"Found rtc_validity in JavaScript: {rtc_data['rtc_validity']}")
                            break
                
                # PART 6: OCR - only run if Pillow successfully opens PNG
                ocr_status = "Skipped"
                if rtc_data["rtc_png_path"] and os.path.exists(rtc_data["rtc_png_path"]):
                    print("\n=== OCR ===")
                    try:
                        # Verify image again before OCR
                        image = Image.open(rtc_data["rtc_png_path"])
                        print("✓ Image verified, running OCR...")
                        
                        # OCR with Kannada + English
                        ocr_text = pytesseract.image_to_string(image, lang='kan+eng')
                        print(f"OCR text extracted (length: {len(ocr_text)})")
                        ocr_status = "Completed"
                        
                        # Save raw OCR output
                        os.makedirs("logs/debug", exist_ok=True)
                        ocr_path = "logs/debug/rtc_ocr.txt"
                        with open(ocr_path, "w", encoding="utf-8") as f:
                            f.write(ocr_text)
                        print(f"Raw OCR output saved to: {ocr_path}")
                        
                        # PART 7: Try extraction in order - OCR is last resort
                        ocr_lines = ocr_text.split('\n')
                        
                        # First pass: collect all dates and times with their line indices
                        dates = []
                        times = []
                        for i, line in enumerate(ocr_lines):
                            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                            if date_match:
                                dates.append((i, date_match.group(1), line.lower()))
                            time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                            if time_match:
                                times.append((i, time_match.group(1), line.lower()))
                        
                        # Try to match dates and times that are close together (within 5 lines)
                        if not rtc_data["rtc_validity"]:
                            for date_idx, date_str, date_line in dates:
                                for time_idx, time_str, time_line in times:
                                    if abs(date_idx - time_idx) <= 5:
                                        # Check if "valid" or "from" is nearby
                                        if 'valid' in date_line or 'from' in date_line or 'valid' in time_line or 'till' in time_line:
                                            rtc_data["rtc_validity"] = f"Valid from {date_str} {time_str} Till Date"
                                            extraction_method = "OCR"
                                            print(f"Found rtc_validity in OCR: {rtc_data['rtc_validity']}")
                                            break
                                if rtc_data["rtc_validity"]:
                                    break
                        
                        # If still not found, look for date with "valid" keyword
                        if not rtc_data["rtc_validity"]:
                            for date_idx, date_str, date_line in dates:
                                if 'valid' in date_line or 'from' in date_line:
                                    rtc_data["rtc_validity"] = f"Valid from {date_str} Till Date"
                                    extraction_method = "OCR"
                                    print(f"Found rtc_validity in OCR: {rtc_data['rtc_validity']}")
                                    break
                        
                        for line in ocr_lines:
                            line_upper = line.upper()
                            line_lower = line.lower()
                            
                            # Land use - only if not already found
                            if not rtc_data["land_use"]:
                                if "AGRICULTURAL" in line_upper and "NON" not in line_upper:
                                    rtc_data["land_use"] = "Agricultural"
                                elif "NON-AGRICULTURAL" in line_upper or "NON AGRICULTURAL" in line_upper:
                                    rtc_data["land_use"] = "Non-Agricultural"
                                elif "CONVERTED" in line_upper:
                                    rtc_data["land_use"] = "Converted"
                            
                            # Soil type - only if not already found
                            if not rtc_data["soil_type"]:
                                soil_match = re.search(r'SOIL\s*:?\s*([A-Za-z]+)', line_upper)
                                if soil_match:
                                    rtc_data["soil_type"] = soil_match.group(1).strip()
                            
                            # Dry land - only if not already found
                            if not rtc_data["area_dryland_acres"]:
                                if "DRY LAND" in line_upper or "DRYLAND" in line_upper:
                                    dry_match = re.search(r'(\d+\.?\d*)', line)
                                    if dry_match:
                                        rtc_data["area_dryland_acres"] = dry_match.group(1)
                            
                            # Wet land - only if not already found
                            if not rtc_data["area_wetland_acres"]:
                                if "WET LAND" in line_upper or "WETLAND" in line_upper:
                                    wet_match = re.search(r'(\d+\.?\d*)', line)
                                    if wet_match:
                                        rtc_data["area_wetland_acres"] = wet_match.group(1)
                            
                            # Encumbrances - only if not already found
                            if not rtc_data["encumbrances_text"]:
                                if "ENCUMBRANCE" in line_upper or "ENCUMBRANCES" in line_upper:
                                    encumbrance_text = line.strip()
                                    if encumbrance_text:
                                        rtc_data["encumbrances_text"] = encumbrance_text
                        
                        if extraction_method == "OCR":
                            print(f"OCR extracted fields: rtc_validity={rtc_data['rtc_validity']}, land_use={rtc_data['land_use']}, soil_type={rtc_data['soil_type']}")
                        
                    except pytesseract.TesseractNotFoundError:
                        print("OCR skipped because Tesseract is not installed.")
                        ocr_status = "Skipped (Tesseract not installed)"
                    except Exception as e:
                        print(f"OCR failed: {e}")
                        ocr_status = f"Failed: {e}"
                else:
                    print("PNG not available for OCR")
                    ocr_status = "Skipped (no PNG)"
                
                # PART 8: Final verification
                print("\n=== FINAL VERIFICATION ===")
                print(f"HTTP Status: {http_status}")
                print(f"Content-Type: {content_type}")
                print(f"Image verification: {'Valid' if rtc_data['rtc_png_path'] and os.path.exists(rtc_data['rtc_png_path']) else 'Failed/Not available'}")
                print(f"OCR status: {ocr_status}")
                print(f"Extraction method for rtc_validity: {extraction_method or 'Not found'}")
                print(f"Extraction method for land_use: {'OCR' if rtc_data['land_use'] else 'Not found'}")
                print(f"Extraction method for soil_type: {'OCR' if rtc_data['soil_type'] else 'Not found'}")
                print(f"Extraction method for area_dryland_acres: {'OCR' if rtc_data['area_dryland_acres'] else 'Not found'}")
                print(f"Extraction method for area_wetland_acres: {'OCR' if rtc_data['area_wetland_acres'] else 'Not found'}")
                print(f"Extraction method for encumbrances_text: {'OCR' if rtc_data['encumbrances_text'] else 'Not found'}")
                
                # Print absolute paths
                print(f"\n=== FILE PATHS ===")
                if rtc_data["screenshot_path"]:
                    print(f"rtc_screenshot.png: {os.path.abspath(rtc_data['screenshot_path'])}")
                if rtc_data["rtc_png_path"]:
                    print(f"rtc_full_document.png: {os.path.abspath(rtc_data['rtc_png_path'])}")
                if ocr_status == "Completed":
                    print(f"rtc_ocr.txt: {os.path.abspath('logs/debug/rtc_ocr.txt')}")
                
                # Part 4: Screenshot verification
                print("Verifying screenshots...")
                os.makedirs("logs/debug", exist_ok=True)
                
                # Take full-page screenshot
                screenshot_path = "logs/debug/rtc_screenshot.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                rtc_data["screenshot_path"] = screenshot_path
                print(f"Full-page screenshot saved to: {os.path.abspath(screenshot_path)}")
                
                # Verify both files exist
                if rtc_data["rtc_png_path"] and os.path.exists(rtc_data["rtc_png_path"]):
                    print(f"RTC PNG verified: {os.path.abspath(rtc_data['rtc_png_path'])}")
                else:
                    print("RTC PNG not found")
                
                if os.path.exists(screenshot_path):
                    print(f"Screenshot verified: {os.path.abspath(screenshot_path)}")
                else:
                    print("Screenshot not found")
                
                # Part 5: Save to database (optional)
                print("Saving to database...")
                try:
                    db = await get_database()
                    async with db.get_session() as session:
                        # Insert into bhoomi_rtc table
                        rtc_record = BhoomiRTC(
                            district=rtc_data["district"],
                            taluk=rtc_data["taluk"],
                            hobli=rtc_data["hobli"],
                            village=rtc_data["village"],
                            survey_no=rtc_data["survey_no"],
                            hissa_no=rtc_data["hissa_no"],
                            owner_name=rtc_data["owner_name"],
                            khata_no=rtc_data["khata_no"],
                            land_use=rtc_data["land_use"],
                            soil_type=rtc_data["soil_type"],
                            area_dryland_acres=rtc_data["area_dryland_acres"],
                            area_wetland_acres=rtc_data["area_wetland_acres"],
                            area_total_acres=rtc_data["area_total_acres"],
                            encumbrances_text=rtc_data["encumbrances_text"],
                            screenshot_path=rtc_data["screenshot_path"],
                            created_at=datetime.utcnow()
                        )
                        session.add(rtc_record)
                        await session.commit()
                        print("Data saved to bhoomi_rtc table")
                        
                        # Part 6: Update scraper_health table
                        await session.execute(
                            update(ScraperHealth)
                            .where(ScraperHealth.portal == 'bhoomi')
                            .values(
                                total_attempts=ScraperHealth.total_attempts + 1,
                                success_count=ScraperHealth.success_count + 1,
                                last_success_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                        )
                        await session.commit()
                        print("Scraper health updated")
                        
                except Exception as e:
                    print(f"DB save skipped: {e}")
                    # Scraper continues without database - data is still returned
                
                await browser.close()
                
                # Print final JSON with all fields
                print("\n=== FINAL RTC DATA ===")
                import json
                final_json = {
                    "district": rtc_data["district"],
                    "taluk": rtc_data["taluk"],
                    "hobli": rtc_data["hobli"],
                    "village": rtc_data["village"],
                    "survey_no": rtc_data["survey_no"],
                    "surnoc": rtc_data["surnoc"],
                    "hissa_no": rtc_data["hissa_no"],
                    "owner_name": rtc_data["owner_name"],
                    "khata_no": rtc_data["khata_no"],
                    "area_total_acres": rtc_data["area_total_acres"],
                    "land_use": rtc_data["land_use"],
                    "soil_type": rtc_data["soil_type"],
                    "area_dryland_acres": rtc_data["area_dryland_acres"],
                    "area_wetland_acres": rtc_data["area_wetland_acres"],
                    "encumbrances_text": rtc_data["encumbrances_text"],
                    "rtc_validity": rtc_data["rtc_validity"],
                    "screenshot_path": rtc_data["screenshot_path"],
                    "rtc_png_path": rtc_data["rtc_png_path"]
                }
                print(json.dumps(final_json, indent=2, ensure_ascii=False))
                
                return rtc_data
        
        return await self._retry_with_backoff(_fetch)
