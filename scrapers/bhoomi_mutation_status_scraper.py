import asyncio
import os
import json
from typing import Dict, Optional
from playwright.async_api import async_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup
import requests
from deep_translator import GoogleTranslator


class ScraperException(Exception):
    """Custom exception for scraper errors"""
    pass


class BhoomiMutationStatusScraper:
    """Bhoomi Mutation Status scraper using public portal (no authentication required)"""
    
    def __init__(self):
        self.status_url = "https://landrecords.karnataka.gov.in/Service12/MutationStatus.aspx"
    
    def translate_text(self, text: str) -> str:
        """Translate Kannada text to English"""
        try:
            translator = GoogleTranslator(source='auto', target='en')
            translated = translator.translate(text)
            return translated
        except Exception as e:
            print(f"Translation failed: {e}")
            return text
    
    async def _match_dropdown_option(self, page, selector: str, target_text: str) -> Optional[str]:
        """
        Match dropdown option using fuzzy matching.
        Returns the value of the matched option or None.
        """
        import re
        
        def normalize(s):
            s = s.upper().strip()
            s = s.replace(' (', '(').replace('( ', '(')
            s = s.replace(' )', ')').replace(') ', ')')
            s = re.sub(r'\s+', ' ', s)
            return s
        
        options = await page.query_selector_all(f'{selector} option')
        
        target_normalized = normalize(target_text)
        
        for opt in options:
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            text_normalized = normalize(text)
            
            # Fuzzy match: contains matching
            if (target_normalized in text_normalized or text_normalized in target_normalized) and val:
                print(f"Matched {selector}: {val} - {text.strip()}")
                return val
        
        print(f"No fuzzy match found for {selector}: target='{target_text}' (normalized: '{target_normalized}')")
        # Print available options for debugging
        print(f"Available options for {selector}:")
        for opt in options[:10]:  # Show first 10 options
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            print(f"  {val} - {text.strip()}")
        return None
    
    async def _wait_for_dropdown_options(self, page, selector: str, timeout: int = 30000) -> bool:
        """
        Wait for dropdown to have options loaded (AJAX response).
        """
        try:
            await page.wait_for_function(
                f"() => document.querySelector('{selector}').options.length > 1",
                timeout=timeout
            )
            return True
        except PlaywrightError:
            return False
    
    async def fetch_mutation_status(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str,
        surnoc: Optional[str] = None,
        hissa: Optional[str] = None
    ) -> Dict:
        """
        Fetch Mutation Status data from Bhoomi public portal
        
        Args:
            district: District name (e.g., 'BENGALURU')
            taluk: Taluk name (e.g., 'BANGALORE-NORTH')
            hobli: Hobli name (e.g., 'DASANAPURA1')
            village: Village name (e.g., 'ADAKAMARANAHALLI')
            survey_no: Survey number (e.g., '1')
            surnoc: Surnoc number (optional)
            hissa: Hissa number (optional)
        
        Returns:
            Dict with mutation status details
        
        Raises:
            ScraperException: If any step fails
        """
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # Navigate to Mutation Status page (public portal)
                    print(f"Navigating to {self.status_url}")
                    await page.goto(self.status_url)
                    await page.wait_for_load_state("networkidle")
                    print("Mutation Status page loaded")
                    
                    # Switch to English language
                    print("Switching to English language...")
                    try:
                        await page.click('#btnEnglish')
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(2000)
                        print("Language switched to English")
                    except PlaywrightError:
                        print("English button not found or click failed, continuing with current language")
                    
                    # Select District
                    district_value = await self._match_dropdown_option(page, '#MainContent_drpdist', district)
                    if not district_value:
                        await browser.close()
                        raise ScraperException(f"District not found: {district}")
                    await page.select_option('#MainContent_drpdist', value=district_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"District selected: {district}")
                    
                    # Wait for Taluk dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#MainContent_drptaluk'):
                        await browser.close()
                        raise ScraperException("Taluk dropdown failed to load")
                    
                    # Select Taluk
                    taluk_value = await self._match_dropdown_option(page, '#MainContent_drptaluk', taluk)
                    if not taluk_value:
                        await browser.close()
                        raise ScraperException(f"Taluk not found: {taluk}")
                    await page.select_option('#MainContent_drptaluk', value=taluk_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Taluk selected: {taluk}")
                    
                    # Wait for Hobli dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#MainContent_drphobli'):
                        await browser.close()
                        raise ScraperException("Hobli dropdown failed to load")
                    
                    # Select Hobli
                    hobli_value = await self._match_dropdown_option(page, '#MainContent_drphobli', hobli)
                    if not hobli_value:
                        await browser.close()
                        raise ScraperException(f"Hobli not found: {hobli}")
                    await page.select_option('#MainContent_drphobli', value=hobli_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Hobli selected: {hobli}")
                    
                    # Wait for Village dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#MainContent_drpvillage'):
                        await browser.close()
                        raise ScraperException("Village dropdown failed to load")
                    
                    # Select Village
                    village_value = await self._match_dropdown_option(page, '#MainContent_drpvillage', village)
                    if not village_value:
                        await browser.close()
                        raise ScraperException(f"Village not found: {village}")
                    await page.select_option('#MainContent_drpvillage', value=village_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Village selected: {village}")
                    
                    # Enter Survey Number
                    await page.fill('#MainContent_txtSurvey', survey_no)
                    await page.wait_for_timeout(1000)
                    print(f"Survey number entered: {survey_no}")
                    
                    # Select Surnoc if provided
                    if surnoc:
                        if not await self._wait_for_dropdown_options(page, '#MainContent_drpsurnoc'):
                            await browser.close()
                            raise ScraperException("Surnoc dropdown failed to load")
                        
                        surnoc_value = await self._match_dropdown_option(page, '#MainContent_drpsurnoc', surnoc)
                        if surnoc_value:
                            await page.select_option('#MainContent_drpsurnoc', value=surnoc_value)
                            await page.wait_for_load_state("networkidle")
                            print(f"Surnoc selected: {surnoc}")
                    
                    # Select Hissa if provided
                    if hissa:
                        if not await self._wait_for_dropdown_options(page, '#MainContent_drphissa'):
                            await browser.close()
                            raise ScraperException("Hissa dropdown failed to load")
                        
                        hissa_value = await self._match_dropdown_option(page, '#MainContent_drphissa', hissa)
                        if hissa_value:
                            await page.select_option('#MainContent_drphissa', value=hissa_value)
                            await page.wait_for_load_state("networkidle")
                            print(f"Hissa selected: {hissa}")
                    
                    # Click Fetch Details button using ASP.NET postback
                    print("Clicking Fetch Details button...")
                    try:
                        # Try to trigger the ASP.NET postback using __doPostBack
                        await page.evaluate("""
                            (function() {
                                // Set the event target to the button
                                var eventTarget = document.getElementById('__EVENTTARGET');
                                if (eventTarget) {
                                    eventTarget.value = 'ctl00$MainContent$btnFetch';
                                }
                                
                                // Try to call __doPostBack if available
                                if (typeof __doPostBack === 'function') {
                                    __doPostBack('ctl00$MainContent$btnFetch', '');
                                } else {
                                    // Fallback to clicking the button
                                    var btn = document.getElementById('MainContent_btnFetch');
                                    if (btn) {
                                        btn.click();
                                    }
                                }
                            })();
                        """)
                    except PlaywrightError as e:
                        print(f"JavaScript click failed: {e}")
                        # Fallback to normal click
                        try:
                            await page.click('#MainContent_btnFetch')
                        except PlaywrightError:
                            print("Normal click also failed")
                    
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(5000)
                    print("Fetch Details button clicked")
                    
                    # Take screenshot
                    log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
                    os.makedirs(log_dir, exist_ok=True)
                    await page.screenshot(path=f'{log_dir}/bhoomi_mutation_status_result.png')
                    print(f"Screenshot saved: {log_dir}/bhoomi_mutation_status_result.png")
                    
                    # Extract mutation status data
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    # Save raw HTML for debugging
                    with open(f"{log_dir}/bhoomi_mutation_status_raw.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    print(f"Raw HTML saved to {log_dir}/bhoomi_mutation_status_raw.html")
                    
                    status_data = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no": survey_no,
                        "surnoc": surnoc,
                        "hissa": hissa,
                        "mutation_pending": False,
                        "status": None,
                        "status_original": None,
                        "status_records": []
                    }
                    
                    # First check for status message (no mutation pending)
                    status_message = None
                    
                    # Look for the last blue line (status message) in the page
                    # Check all text elements for status messages, focusing on the last meaningful text
                    all_text_elements = soup.find_all(['span', 'div', 'label', 'p', 'td'])
                    kannada_texts = []
                    for element in all_text_elements:
                        text = element.get_text(strip=True)
                        # Look for Kannada text that might be a status message
                        if text and len(text) > 5 and any('\u0C80' <= char <= '\u0CFF' for char in text):
                            # Filter out dropdown options (too long, contains many district names)
                            if len(text) < 200:  # Status messages are usually shorter
                                kannada_texts.append(text)
    
                    # Use the last Kannada text as the status message
                    if kannada_texts:
                        status_message = kannada_texts[-1]
                        print(f"Found status message (Kannada): {status_message}")
    
                    # If no Kannada text found, look for English status messages
                    if not status_message:
                        status_keywords = ['no mutation', 'mutation pending', 'status', 'pending', 'approved', 'rejected']
                        for element in all_text_elements:
                            text = element.get_text(strip=True)
                            if text and any(keyword.lower() in text.lower() for keyword in status_keywords):
                                status_message = text
                                print(f"Found status message (English): {status_message}")
                                break
    
                    if status_message:
                        # Translate if in Kannada
                        status_data["status_original"] = status_message
                        status_data["status"] = self.translate_text(status_message)
                        # Determine if mutation is pending based on status
                        if 'pending' in status_data["status"].lower() or 'ಬಾಕಿ' in status_message or 'ನಮೂದಾಗಬೇಕಿದೆ' in status_message:
                            status_data["mutation_pending"] = True
                        else:
                            status_data["mutation_pending"] = False
                        print(f"Status (original): {status_message}")
                        print(f"Status (translated): {status_data['status']}")
                    else:
                        # No status message, look for mutation details table
                        tables = soup.find_all('table')
                        print(f"Found {len(tables)} tables")
                        for table_idx, table in enumerate(tables):
                            rows = table.find_all('tr')
                            print(f"Table {table_idx}: {len(rows)} rows")
                            for i, row in enumerate(rows):
                                cells = row.find_all(['td', 'th'])
                                if len(cells) >= 2:
                                    row_text = ' | '.join([c.get_text(strip=True) for c in cells])
                                    # Skip header row
                                    if i == 0:
                                        continue
                                    # Add all data rows that have actual content
                                    if row_text and len(row_text) > 10:
                                        status_data["status_records"].append(row_text)
                                        print(f"Found status row: {row_text}")
                        
                        if status_data["status_records"]:
                            status_data["mutation_pending"] = True
                            status_data["status"] = f"Found {len(status_data['status_records'])} mutation records"
                        else:
                            status_data["status"] = "No mutation records found"
                            status_data["status_original"] = "No mutation records found"
                    
                    # Save results
                    with open(f"{log_dir}/bhoomi_mutation_status_result.json", "w", encoding="utf-8") as f:
                        json.dump(status_data, f, indent=2, ensure_ascii=False)
                    print(f"Results saved to {log_dir}/bhoomi_mutation_status_result.json")
                    
                    return status_data
                    
                finally:
                    await browser.close()
        
        return await _fetch()
