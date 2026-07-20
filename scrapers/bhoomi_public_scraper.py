"""
Bhoomi Public Portal Scraper
No login required - uses public portal at https://landrecords.karnataka.gov.in/Service2/
"""

import asyncio
import json
import os
import requests
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pytesseract
from PIL import Image
import io


class BhoomiPublicScraper:
    def __init__(self):
        self.base_url = "https://landrecords.karnataka.gov.in/Service2/"
        self.rtc_url = "https://landrecords.karnataka.gov.in/Service2/RTC.aspx"
        self.translator = GoogleTranslator(source='kn', target='en')
    
    def translate_text(self, text: str) -> str:
        """Translate Kannada text to English."""
        if not text or not text.strip():
            return text
        try:
            translated = self.translator.translate(text)
            return translated
        except Exception as e:
            print(f"Translation error for '{text}': {e}")
            return text  # Return original if translation fails
    
    def _parse_rtc_ocr_text(self, ocr_text: str) -> dict:
        """Parse OCR text to extract RTC fields."""
        fields = {}
        lines = ocr_text.split('\n')
        
        # Common Kannada field labels in RTC documents
        field_patterns = {
            'owner_name': ['ಹೆಸರು', 'ಹೆಸರು', 'Name', 'ಒಡೆತನ', 'ಸ್ವಾಧೀನದಾರನ'],
            'father_husband': ['ತಂದೆ', 'ಪತಿ', 'Father', 'Husband', 'ಬಿನ್'],
            'survey_number': ['ಸರ್ವೆ ಸಂಖ್ಯೆ', 'Survey No', 'ಸರ್ವೆ'],
            'surnoc': ['ಸರ್ ನಾಕ್', 'Surnoc', 'ಸರ್ನಾಕ್'],
            'hissa': ['ಹಿಸ್ಸಾ', 'Hissa', 'ಹಿಸ್ಸ'],
            'village': ['ಗ್ರಾಮ', 'Village', 'ಗ್ರಾಮದ'],
            'hobli': ['ಹೊಬಳಿ', 'Hobli', 'ಹೊಬಳಿಯ'],
            'taluk': ['ತಾಲ್ಲೂಕು', 'Taluk', 'ತಾಲ್ಲೂಕ'],
            'district': ['ಜಿಲ್ಲೆ', 'District', 'ಜಿಲ್ಲಾ'],
            'khata_number': ['ಖತ', 'Khata', 'ಖತಾ'],
            'land_extent': ['ವಿಸ್ತೀರ್ಣ', 'Extent', 'ವಿಸ್ತೀರ್ಣ', 'ಎಕರೆ'],
            'land_classification': ['ವರ್ಗ', 'Class', 'ವರ್ಗೀಕರಣ'],
            'soil_type': ['ಮಣ್ಣು', 'Soil', 'ಮಣ್ಣಿನ'],
            'rtc_period': ['ಅವಧಿ', 'Period', 'ಅವಧಿಯ'],
        }
        
        # Extract owner name from specific RTC format
        # Look for lines with year patterns followed by Kannada names
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for year patterns like "2025-2026" followed by Kannada names
            if '2025-2026' in line or '2024-2025' in line or '2023-2024' in line:
                # Extract Kannada text after the year on the same line
                kannada_part = line.split('2025-2026')[-1].split('2024-2025')[-1].split('2023-2024')[-1].strip()
                # Remove brackets
                kannada_part = kannada_part.replace('[', '').replace(']', '').replace(']', '').strip()
                # Remove trailing crop names
                for crop in ['ಮು೦ಗಾರು', 'ಹಿಂಗಾರು', 'ಬೇಸಿಗೆ', 'ಉರುಫ್', '|']:
                    kannada_part = kannada_part.split(crop)[0].strip()
                
                # Check if this is a valid owner name (contains Kannada, reasonable length)
                if kannada_part and len(kannada_part) > 5 and any('\u0C80' <= char <= '\u0CFF' for char in kannada_part):
                    # Skip if it's a label
                    if not any(label in kannada_part for label in ['ತಂದೆ', 'ಪತಿ', 'ವಿಳಾಸ', 'ಕಚ್ಚೆ', 'ಸ್ವಾಧೀನತೆ', 'ರೀತಿ']):
                        fields['owner_name'] = kannada_part
                        print(f"Found owner name: {kannada_part}")
                        break
        
        # If owner name not found with year pattern, try direct extraction
        if 'owner_name' not in fields:
            # Look for lines with typical Kannada name patterns
            for line in lines:
                line = line.strip()
                # Skip lines that are clearly headers or labels
                if any(label in line for label in ['ಗ್ರಾಮ', 'ತಾಲ್ಲೂಕು', 'ಹೋಬಳಿ', 'ವಿಸ್ತೀರ್ಣ', 'ಖೇತವಾರು', 'ಕಂದಾಯ', 'ರೆಕಾರ್ಡ್‌', 'RTC', 'DIGITALLY', 'SIGNED', 'ಮಿಶ್ರಣದ', 'ವಿಸ್ತೀರ್ಣ', 'ಎಕರೆ', 'ನೀರಿನ', 'ಮರಗಳ', 'ನೀರಾವರಿ', 'ವರ್ಷ']):
                    continue
                
                # Look for Kannada text with dots or spaces (typical name patterns)
                if any('\u0C80' <= char <= '\u0CFF' for char in line):
                    if '.' in line or ' ' in line:
                        # Extract Kannada text only
                        kannada_text = ''.join(char for char in line if '\u0C80' <= char <= '\u0CFF' or char in ' .')
                        # Remove trailing crop names
                        for crop in ['ಮು೦ಗಾರು', 'ಹಿಂಗಾರು', 'ಬೇಸಿಗೆ', 'ಉರುಫ್', '|']:
                            kannada_text = kannada_text.split(crop)[0].strip()
                        if len(kannada_text) > 5:  # Minimum length for a name
                            fields['owner_name'] = kannada_text
                            print(f"Found owner name (direct): {kannada_text}")
                            break
        
        # Simple pattern matching - look for field labels and extract following text
        current_field = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line contains a field label
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    if pattern in line:
                        current_field = field
                        # Extract value after the label
                        value = line.replace(pattern, '').strip()
                        if value:
                            fields[field] = value
                        break
                if current_field:
                    break
            
            # If no field label found but we have a current field, append to it
            if not any(pattern in line for patterns in field_patterns.values() for pattern in patterns):
                if current_field and line:
                    if current_field in fields:
                        fields[current_field] += ' ' + line
                    else:
                        fields[current_field] = line
        
        return fields
    
    async def fetch_rtc(self, district: str, taluk: str, hobli: str, village: str, survey_no: str):
        """
        Fetch RTC data from public Bhoomi portal.
        
        Args:
            district: District name (e.g., "BENGALURU")
            taluk: Taluk name (e.g., "BANGALORE-NORTH")
            hobli: Hobli name (e.g., "DASANAPURA1")
            village: Village name (e.g., "ADAKAMARANAHALLI")
            survey_no: Survey number (e.g., "2")
        
        Returns:
            dict: Extracted RTC data
        """
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # Navigate directly to RTC.aspx page
                    print(f"Navigating to {self.rtc_url}")
                    await page.goto(self.rtc_url)
                    await page.wait_for_load_state("networkidle")
                    print("RTC page loaded")
                    
                    # Set language to English ONCE at the beginning
                    print("Setting language to English...")
                    english_locator = page.locator('a:has-text("English"), a[href*="en"], button:has-text("English")')
                    if await english_locator.count() > 0:
                        await english_locator.first.click()
                        await page.wait_for_timeout(1000)
                        print("Language set to English")
                    else:
                        print("English link not found, may already be in English")
                    
                    # Select District using locator
                    print(f"Selecting District: {district}")
                    await page.wait_for_selector('select[name*="District"], select[id*="District"]', timeout=10000)
                    await page.locator('select[name*="District"], select[id*="District"]').select_option(label=district)
                    await page.wait_for_timeout(2000)
                    print(f"District selected: {district}")
                    
                    # Select Taluk using locator
                    print(f"Selecting Taluk: {taluk}")
                    await page.wait_for_selector('select[name*="Taluk"], select[id*="Taluk"]', timeout=10000)
                    await page.locator('select[name*="Taluk"], select[id*="Taluk"]').select_option(label=taluk)
                    await page.wait_for_timeout(2000)
                    print(f"Taluk selected: {taluk}")
                    
                    # Select Hobli using locator
                    print(f"Selecting Hobli: {hobli}")
                    await page.wait_for_selector('select[name*="Hobli"], select[id*="Hobli"]', timeout=10000)
                    await page.locator('select[name*="Hobli"], select[id*="Hobli"]').select_option(label=hobli)
                    await page.wait_for_timeout(2000)
                    print(f"Hobli selected: {hobli}")
                    
                    # Select Village using locator
                    print(f"Selecting Village: {village}")
                    await page.wait_for_selector('select[name*="Village"], select[id*="Village"]', timeout=10000)
                    await page.locator('select[name*="Village"], select[id*="Village"]').select_option(label=village)
                    await page.wait_for_timeout(2000)
                    print(f"Village selected: {village}")
                    
                    # Enter Survey Number using exact ID with locator
                    print(f"Entering Survey Number: {survey_no}")
                    survey_locator = page.locator('#ctl00_MainContent_txtSurvey')
                    if await survey_locator.count() > 0:
                        await survey_locator.fill(survey_no)
                        await page.wait_for_timeout(500)
                        print(f"Survey number entered: {survey_no}")
                    else:
                        print("Survey input not found with exact ID, trying generic selector...")
                        survey_locator = page.locator('input[name*="Survey"], input[id*="Survey"]')
                        if await survey_locator.count() > 0:
                            await survey_locator.fill(survey_no)
                            await page.wait_for_timeout(500)
                            print(f"Survey number entered: {survey_no}")
                    
                    # Click Go button using exact ID - this is a standard ASP.NET submit button (form.submit)
                    print("Clicking Go button (ID: ctl00_MainContent_btnCGo)...")
                    print("GO button mechanism: Standard HTML <input type=\"submit\"> triggering form.submit postback")
                    await page.locator('#ctl00_MainContent_btnCGo').click()
                    print("Go button clicked, waiting for postback to complete...")
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(3000)
                    print("Postback complete")
                    
                    # DO NOT change language after Go - let it stay in Kannada to avoid interrupting ASP.NET lifecycle
                    
                    # Take screenshot after GO
                    os.makedirs("logs/debug", exist_ok=True)
                    await page.screenshot(path='logs/debug/bhoomi_public_after_go.png')
                    print("Screenshot saved: logs/debug/bhoomi_public_after_go.png")
                    
                    # Wait for Surnoc dropdown to become enabled using locator
                    print("Waiting for Surnoc dropdown to enable...")
                    try:
                        await page.wait_for_function(
                            """() => {
                                const el = document.querySelector('#ctl00_MainContent_ddlCSurnocNo');
                                return el && !el.disabled && el.options.length > 1;
                            }""",
                            timeout=15000
                        )
                        print("Surnoc dropdown enabled")
                    except Exception as e:
                        print(f"Surnoc not enabled after timeout: {e}")
                    
                    # Take screenshot to debug current state
                    await page.screenshot(path='logs/debug/bhoomi_public_before_surnoc.png')
                    print("Screenshot saved: logs/debug/bhoomi_public_before_surnoc.png")
                    
                    # Check if surnoc dropdown exists and its state using locator
                    print("Checking surnoc dropdown state...")
                    surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                    if await surnoc_locator.count() > 0:
                        is_disabled = await surnoc_locator.get_attribute('disabled')
                        option_count = await surnoc_locator.evaluate('el => el.options.length')
                        print(f"Surnoc exists: True, disabled: {is_disabled}, options: {option_count}")
                        
                        # If still disabled, try pressing Enter on survey field using locator
                        if is_disabled or option_count <= 1:
                            print("Surnoc still disabled, trying Enter key on survey field...")
                            survey_locator = page.locator('#ctl00_MainContent_txtSurvey')
                            if await survey_locator.count() > 0:
                                await survey_locator.focus()
                                await page.keyboard.press('Enter')
                                await page.wait_for_timeout(5000)
                                print("Enter key pressed")
                                
                                # Check again using fresh locator
                                surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                                is_disabled = await surnoc_locator.evaluate('el => el.disabled')
                                option_count = await surnoc_locator.evaluate('el => el.options.length')
                                print(f"After Enter - disabled: {is_disabled}, options: {option_count}")
                                
                                # If still disabled after Enter, skip Surnoc selection
                                if is_disabled or option_count <= 1:
                                    print("Surnoc still disabled after Enter, skipping Surnoc selection")
                                    print("Proceeding with Fetch Details anyway...")
                    else:
                        print("Surnoc dropdown not found on page")
                    
                    # Select Surnoc * using fresh locator after postback - only if enabled
                    print("Selecting Surnoc *")
                    surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                    if await surnoc_locator.count() > 0:
                        is_disabled = await surnoc_locator.evaluate('el => el.disabled')
                        if not is_disabled:
                            await surnoc_locator.select_option(value='*')
                            await page.wait_for_timeout(2000)
                            print("Surnoc * selected")
                        else:
                            print("Surnoc dropdown is disabled, skipping selection")
                    
                    # Select Hissa * using locator - only if enabled
                    print("Selecting Hissa *")
                    hissa_locator = page.locator('#ctl00_MainContent_ddlCHissaNo')
                    if await hissa_locator.count() > 0:
                        is_disabled = await hissa_locator.evaluate('el => el.disabled')
                        if not is_disabled:
                            await hissa_locator.select_option(value='*')
                            await page.wait_for_timeout(2000)
                            print("Hissa * selected")
                        else:
                            print("Hissa dropdown is disabled, skipping selection")
                    
                    # Click Fetch Details using exact ID
                    print("Clicking Fetch Details button (ID: ctl00_MainContent_btnCFetchDetails)...")
                    fetch_locator = page.locator('#ctl00_MainContent_btnCFetchDetails')
                    if await fetch_locator.count() > 0:
                        await fetch_locator.click()
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(5000)
                        print("Fetch Details clicked")
                    
                    # Take screenshot after Fetch
                    await page.screenshot(path='logs/debug/bhoomi_public_after_fetch.png')
                    print("Screenshot saved: logs/debug/bhoomi_public_after_fetch.png")
                    
                    # Extract data from results table
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    rtc_data = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no": survey_no,
                        "surnoc": "*",
                        "hissa_no": "*",
                        "owner_name": "",
                        "extent": "",
                        "owner_category": "",
                        "gov_restriction": "",
                        "court_stay": "",
                        "period": "",
                        "year": "",
                        "raw_html": page_content
                    }
                    
                    # Try to extract from table
                    tables = soup.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')
                        # Skip header row, extract data rows
                        for i, row in enumerate(rows):
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 2:
                                # First row is header, skip it
                                if i == 0:
                                    continue
                                
                                # Extract owner name from first column
                                owner_name = cells[0].get_text(strip=True)
                                if owner_name and owner_name not in ['Owner', '']:
                                    if not rtc_data["owner_name"]:
                                        rtc_data["owner_name"] = owner_name
                                    else:
                                        # Append additional owners
                                        rtc_data["owner_name"] += f", {owner_name}"
                                
                                # Extract extent from second column
                                if len(cells) >= 2:
                                    extent = cells[1].get_text(strip=True)
                                    if extent and extent not in ['Extent', '']:
                                        if not rtc_data["extent"]:
                                            rtc_data["extent"] = extent
                                        else:
                                            rtc_data["extent"] += f", {extent}"
                                
                                # Extract category from third column
                                if len(cells) >= 3:
                                    category = cells[2].get_text(strip=True)
                                    if category and category not in ['Owner Category', '']:
                                        if not rtc_data["owner_category"]:
                                            rtc_data["owner_category"] = category
                                        else:
                                            rtc_data["owner_category"] += f", {category}"
                    
                    # Click View button for full RTC
                    print("Waiting for View button to be visible and enabled...")
                    view_locator = page.locator('#ctl00_MainContent_btnCPreview')
                    await view_locator.wait_for(state='visible', timeout=10000)
                    print("View button found")
                    
                    # Check if button is enabled
                    is_disabled = await view_locator.get_attribute('disabled')
                    if is_disabled:
                        print(f"View button is disabled: {is_disabled}")
                    else:
                        print("View button is enabled")
                    
                    print("Clicking View button...")
                    
                    # Detect navigation type and handle accordingly
                    async with context.expect_page() as popup_info:
                        await view_locator.click()
                    
                    try:
                        # Check if a popup/new tab opened
                        popup = await popup_info.value
                        print("Popup detected - switching to new page")
                        page = popup
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(3000)
                    except:
                        # No popup, check for navigation
                        print("No popup detected - checking for navigation...")
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        print("Navigation detected - stayed on same page with navigation")
                    
                    print("RTC document loaded")
                    
                    # Take full-page screenshot
                    await page.screenshot(path='logs/debug/full_rtc_document.png', full_page=True)
                    print("Screenshot saved: logs/debug/full_rtc_document.png")
                    
                    # Save full RTC HTML
                    full_rtc_html = await page.content()
                    with open("logs/debug/full_rtc_document.html", "w", encoding="utf-8") as f:
                        f.write(full_rtc_html)
                    print("HTML saved: logs/debug/full_rtc_document.html")
                    
                    # Extract RTC image URL from HTML
                    soup = BeautifulSoup(full_rtc_html, 'html.parser')
                    rtc_image = soup.find('img', id='ImgSketchPage')
                    if rtc_image and rtc_image.get('src'):
                        rtc_image_url = rtc_image['src']
                        print(f"RTC Image URL found: {rtc_image_url}")
                        
                        # Download the image
                        print("Downloading RTC image...")
                        try:
                            if not rtc_image_url.startswith('http'):
                                rtc_image_url = f"https://landrecords.karnataka.gov.in/{rtc_image_url}"
                            
                            response = requests.get(rtc_image_url)
                            if response.status_code == 200:
                                image = Image.open(io.BytesIO(response.content))
                                image_path = 'logs/debug/rtc_image.png'
                                image.save(image_path)
                                print(f"RTC image saved: {image_path}")
                                
                                # Try OCR if Tesseract is available, otherwise use existing OCR file
                                try:
                                    print("Attempting OCR on RTC image...")
                                    ocr_text = pytesseract.image_to_string(image, lang='kan')
                                    print(f"OCR extracted text length: {len(ocr_text)} characters")
                                    
                                    # Save OCR text
                                    with open("logs/debug/rtc_ocr_text.txt", "w", encoding="utf-8") as f:
                                        f.write(ocr_text)
                                    print("OCR text saved: logs/debug/rtc_ocr_text.txt")
                                except Exception as ocr_error:
                                    print(f"OCR failed: {ocr_error}")
                                    print("Using existing OCR file if available...")
                                    ocr_text = ""
                                    if os.path.exists("logs/debug/rtc_ocr.txt"):
                                        with open("logs/debug/rtc_ocr.txt", "r", encoding="utf-8") as f:
                                            ocr_text = f.read()
                                        print("Using existing OCR text from logs/debug/rtc_ocr.txt")
                                    elif os.path.exists("logs/debug/rtc_ocr_text.txt"):
                                        with open("logs/debug/rtc_ocr_text.txt", "r", encoding="utf-8") as f:
                                            ocr_text = f.read()
                                        print("Using existing OCR text from logs/debug/rtc_ocr_text.txt")
                                
                                if ocr_text:
                                    # Parse OCR text to extract RTC fields
                                    rtc_fields = self._parse_rtc_ocr_text(ocr_text)
                                    print(f"Parsed RTC fields: {list(rtc_fields.keys())}")
                                    
                                    # Translate Kannada fields to English
                                    # Only add OCR fields if not already extracted from HTML table
                                    for field, kannada_value in rtc_fields.items():
                                        if kannada_value and kannada_value.strip():
                                            # Don't overwrite fields already extracted from HTML table
                                            if field not in rtc_data or not rtc_data[field]:
                                                english_value = self.translate_text(kannada_value)
                                                rtc_data[f"{field}_kn"] = kannada_value
                                                rtc_data[f"{field}_en"] = english_value
                                                print(f"{field}: KN='{kannada_value}' -> EN='{english_value}'")
                                            else:
                                                print(f"Skipping OCR field '{field}' - already extracted from HTML table")
                        except Exception as e:
                            print(f"Error during image processing: {e}")
                    else:
                        print("No RTC image found in HTML")
                    
                    # Store in rtc_data
                    rtc_data["full_rtc_html"] = full_rtc_html
                    
                    # Save to JSON
                    os.makedirs("logs/debug", exist_ok=True)
                    with open("logs/debug/bhoomi_public_result.json", "w", encoding="utf-8") as f:
                        json.dump(rtc_data, f, indent=2, ensure_ascii=False)
                    print("Results saved to logs/debug/bhoomi_public_result.json")
                    
                    # Save English-only data to separate JSON
                    english_data = {k: v for k, v in rtc_data.items() if k.endswith('_en') or not k.endswith('_kn')}
                    with open("logs/debug/bhoomi_public_result_english.json", "w", encoding="utf-8") as f:
                        json.dump(english_data, f, indent=2, ensure_ascii=False)
                    print("English results saved to logs/debug/bhoomi_public_result_english.json")
                    
                    # Save to CSV for easy viewing
                    import csv
                    csv_data = []
                    for key, value in rtc_data.items():
                        if isinstance(value, str) and len(value) < 1000:  # Skip long HTML
                            csv_data.append([key, value])
                    
                    with open("logs/debug/bhoomi_public_result.csv", "w", encoding="utf-8", newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Field", "Value"])
                        writer.writerows(csv_data)
                    print("CSV results saved to logs/debug/bhoomi_public_result.csv")
                    
                    print("\n=== EXTRACTED DATA ===")
                    print(json.dumps(rtc_data, indent=2, ensure_ascii=False))
                    
                    return rtc_data
                    
                except Exception as e:
                    print(f"Error during scraping: {e}")
                    raise
                finally:
                    await browser.close()
        
        return await _fetch()


async def test_public_scraper():
    scraper = BhoomiPublicScraper()
    try:
        result = await scraper.fetch_rtc(
            district='BENGALURU',
            taluk='BANGALORE-NORTH',
            hobli='DASANAPURA1',
            village='ADAKAMARANAHALLI',
            survey_no='2'
        )
        print("\nTest completed successfully!")
        return result
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_public_scraper())
