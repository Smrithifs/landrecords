import asyncio
import os
import json
from typing import Dict, Optional
from playwright.async_api import async_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup
import requests


class ScraperException(Exception):
    """Custom exception for scraper errors"""
    pass


class BhoomiPublicMutationScraper:
    """Bhoomi Mutation Register scraper using public portal (no authentication required)"""
    
    def __init__(self):
        self.mr_url = "https://landrecords.karnataka.gov.in/Service11/MR_MutationExtract.aspx"
    
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
    
    async def fetch_mutation(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str
    ) -> Dict:
        """
        Fetch Mutation Register data from Bhoomi public portal
        
        Args:
            district: District name (e.g., 'BENGALURU')
            taluk: Taluk name (e.g., 'BANGALORE-NORTH')
            hobli: Hobli name (e.g., 'DASANAPURA1')
            village: Village name (e.g., 'ADAKAMARANAHALLI')
            survey_no: Survey number (e.g., '2')
        
        Returns:
            Dict with mutation details
        
        Raises:
            ScraperException: If any step fails
        """
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # Navigate directly to Mutation Extract page (public portal)
                    print(f"Navigating to {self.mr_url}")
                    await page.goto(self.mr_url)
                    await page.wait_for_load_state("networkidle")
                    print("Mutation Extract page loaded")
                    
                    # Select District
                    district_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpdist', district)
                    if not district_value:
                        await browser.close()
                        raise ScraperException(f"District not found: {district}")
                    await page.select_option('#ctl00_MainContent_drpdist', value=district_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"District selected: {district}")
                    
                    # Wait for Taluk dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drptaluk'):
                        await browser.close()
                        raise ScraperException("Taluk dropdown failed to load")
                    
                    # Select Taluk
                    taluk_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drptaluk', taluk)
                    if not taluk_value:
                        await browser.close()
                        raise ScraperException(f"Taluk not found: {taluk}")
                    await page.select_option('#ctl00_MainContent_drptaluk', value=taluk_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Taluk selected: {taluk}")
                    
                    # Wait for Hobli dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drphobli'):
                        await browser.close()
                        raise ScraperException("Hobli dropdown failed to load")
                    
                    # Select Hobli
                    hobli_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drphobli', hobli)
                    if not hobli_value:
                        await browser.close()
                        raise ScraperException(f"Hobli not found: {hobli}")
                    await page.select_option('#ctl00_MainContent_drphobli', value=hobli_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Hobli selected: {hobli}")
                    
                    # Wait for Village dropdown to load via AJAX
                    if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drpvillage'):
                        await browser.close()
                        raise ScraperException("Village dropdown failed to load")
                    
                    # Select Village
                    village_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpvillage', village)
                    if not village_value:
                        await browser.close()
                        raise ScraperException(f"Village not found: {village}")
                    await page.select_option('#ctl00_MainContent_drpvillage', value=village_value)
                    await page.wait_for_load_state("networkidle")
                    print(f"Village selected: {village}")
                    
                    # Enter Survey Number
                    await page.fill('#ctl00_MainContent_txtSurvey', survey_no)
                    await page.wait_for_timeout(1000)
                    print(f"Survey number entered: {survey_no}")
                    
                    # Click Fetch Details button using JavaScript
                    print("Clicking Fetch Details button...")
                    try:
                        await page.click('#ctl00_MainContent_btnFetch')
                    except PlaywrightError:
                        print("Normal click failed, trying JavaScript click...")
                        await page.evaluate("document.getElementById('ctl00_MainContent_btnFetch').click()")
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(3000)
                    print("Fetch Details button clicked")
                    
                    # Take screenshot after Go
                    log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
                    os.makedirs(log_dir, exist_ok=True)
                    await page.screenshot(path=f'{log_dir}/bhoomi_public_mutation_after_go.png')
                    print(f"Screenshot saved: {log_dir}/bhoomi_public_mutation_after_go.png")
                    
                    # Extract mutation data from table
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    # Save raw HTML for debugging
                    with open(f"{log_dir}/bhoomi_public_mutation_raw.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    print(f"Raw HTML saved to {log_dir}/bhoomi_public_mutation_raw.html")
                    
                    mutation_data = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no": survey_no,
                        "mutations": []
                    }
                    
                    # Try to extract from mutation table
                    tables = soup.find_all('table')
                    print(f"Found {len(tables)} tables")
                    for table_idx, table in enumerate(tables):
                        rows = table.find_all('tr')
                        print(f"Table {table_idx}: {len(rows)} rows")
                        for i, row in enumerate(rows):
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 2:
                                row_text = ' | '.join([c.get_text(strip=True) for c in cells])
                                # Skip header row (row 0) and empty rows
                                if i == 0:
                                    continue
                                # Add all data rows that have actual content
                                if row_text and len(row_text) > 10 and 'Select' in row_text:
                                    mutation_data["mutations"].append(row_text)
                                    print(f"Found mutation row: {row_text}")
                    
                    # Save results
                    with open(f"{log_dir}/bhoomi_public_mutation_result.json", "w", encoding="utf-8") as f:
                        json.dump(mutation_data, f, indent=2, ensure_ascii=False)
                    print(f"Results saved to {log_dir}/bhoomi_public_mutation_result.json")
                    
                    return mutation_data
                    
                finally:
                    await browser.close()
        
        return await _fetch()
