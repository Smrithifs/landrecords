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
from scrapers.bhoomi_base import BhoomiBaseScraper, ScraperException


class BhoomiMutationScraper(BhoomiBaseScraper):
    """Bhoomi Mutation Register scraper using Playwright with manual CAPTCHA handling"""
    
    async def fetch_mutation(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str
    ) -> Dict:
        """
        Fetch Mutation Register data from Bhoomi portal
        
        Args:
            district: District name (e.g., 'BENGALURU')
            taluk: Taluk name (e.g., 'Bangalore North (Additional)')
            hobli: Hobli name (e.g., 'YALAHANKA1')
            village: Village name (e.g., 'KRUSHNASAGARA')
            survey_no: Survey number (e.g., '2')
        
        Returns:
            Dict with mutation details
        
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
                
                # Navigate directly to Mutation Extract page
                await page.goto("https://landrecords.karnataka.gov.in/Service11/MR_MutationExtract.aspx")
                await page.wait_for_load_state("networkidle")
                print("Navigated to Mutation Extract page")
                
                # Check if logged in
                if "Login" in page.url:
                    await browser.close()
                    self._session_cache = None
                    self._session_timestamp = None
                    raise ScraperException("Not logged in - cookies not working")
                
                # Select District
                district_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpdist', district)
                if not district_value:
                    await browser.close()
                    raise ScraperException(f"District not found: {district}")
                await page.select_option('#ctl00_MainContent_drpdist', value=district_value)
                
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
                
                # Enter survey number (text input, not dropdown)
                await page.fill('#ctl00_MainContent_txtSurvey', survey_no)
                
                # Debug Fetch Details button state before clicking
                fetch_button = await page.query_selector('#ctl00_MainContent_btnFetch')
                if fetch_button:
                    button_exists = True
                    button_enabled = await fetch_button.is_enabled()
                    button_visible = await fetch_button.is_visible()
                    button_value = await fetch_button.get_attribute('value')
                    print(f"=== FETCH DETAILS BUTTON STATE ===")
                    print(f"Button exists: {button_exists}")
                    print(f"Button enabled: {button_enabled}")
                    print(f"Button visible: {button_visible}")
                    print(f"Button text: {button_value}")
                    
                    # Wait until button is enabled
                    if not button_enabled:
                        print("Button is disabled, waiting for it to be enabled...")
                        try:
                            await page.wait_for_selector('#ctl00_MainContent_btnFetch:not([disabled])', timeout=30000)
                            print("Button is now enabled")
                        except PlaywrightError:
                            print("Button did not become enabled within timeout, clicking anyway")
                    
                    # Try to click using locator.click()
                    try:
                        await fetch_button.click()
                        print("Clicked Fetch Details button using locator.click()")
                    except PlaywrightError as e:
                        print(f"locator.click() failed: {e}, trying evaluate...")
                        try:
                            await fetch_button.evaluate("button => button.click()")
                            print("Clicked Fetch Details button using evaluate()")
                        except Exception as e2:
                            print(f"evaluate() also failed: {e2}")
                            raise ScraperException(f"Failed to click Fetch Details button: {e2}")
                else:
                    raise ScraperException("Fetch Details button not found")
                
                # Wait for table to load
                print("Waiting for mutation details table to load...")
                try:
                    # Wait for networkidle first
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    print("Network idle reached")
                except PlaywrightError:
                    print("Network idle timeout, proceeding anyway")
                
                await page.wait_for_timeout(3000)
                
                # Try to wait for loading element to disappear
                try:
                    await page.wait_for_selector('div:has-text("LOADING"), .loading, #loading, [id*="loading"], [class*="loading"]', state="hidden", timeout=60000)
                    print("Loading complete")
                except PlaywrightError:
                    print("No loading element found or timeout, proceeding anyway")
                
                await page.wait_for_timeout(2000)
                
                # Initialize mutation data
                mutation_data = {
                    "district": district,
                    "taluk": taluk,
                    "hobli": hobli,
                    "village": village,
                    "survey_no": survey_no,
                    "mutations": [],
                    "mutation_details": []
                }
                
                # Extract mutation details table
                print("Extracting mutation details from table...")
                page_content = await page.content()
                soup = BeautifulSoup(page_content, 'html.parser')
                
                # Find the mutation details table
                tables = soup.find_all('table')
                mutation_table = None
                
                for table in tables:
                    # Look for table with mutation-related headers
                    headers = table.find_all('th')
                    header_texts = [h.get_text(strip=True) for h in headers]
                    if any('Survey' in h or 'Transaction' in h or 'MR' in h or 'Mutation' in h for h in header_texts):
                        mutation_table = table
                        print(f"Found mutation table with headers: {header_texts}")
                        break
                
                if mutation_table:
                    rows = mutation_table.find_all('tr')
                    
                    # Build header mapping from first row
                    header_mapping = {}
                    if rows:
                        header_row = rows[0]
                        headers = header_row.find_all('th')
                        print("=== DETECTED TABLE HEADERS ===")
                        for idx, header in enumerate(headers):
                            header_text = header.get_text(strip=True)
                            print(f"{idx}: {header_text}")
                            # Map header text to column index
                            header_mapping[header_text] = idx
                    
                    # Parse data rows (skip header row)
                    for row in rows[1:]:
                        cols = row.find_all('td')
                        if cols:
                            mutation_row = {
                                "survey_no": None,
                                "transaction_year": None,
                                "transaction_no": None,
                                "mr_number": None,
                                "mutation_type": None,
                                "acquisition_type": None,
                                "approved_date": None
                            }
                            
                            # Extract data using header mapping
                            for header_name, col_idx in header_mapping.items():
                                if col_idx < len(cols):
                                    value = cols[col_idx].get_text(strip=True)
                                    
                                    if "Survey" in header_name and "No" in header_name:
                                        mutation_row["survey_no"] = value
                                    elif "Transaction" in header_name and "Year" in header_name:
                                        mutation_row["transaction_year"] = value
                                    elif "Transaction" in header_name and "No" in header_name:
                                        mutation_row["transaction_no"] = value
                                    elif "MR" in header_name and "Number" in header_name:
                                        mutation_row["mr_number"] = value
                                    elif "Mutation" in header_name and "Type" in header_name:
                                        mutation_row["mutation_type"] = value
                                    elif "Acquisition" in header_name and "Type" in header_name:
                                        mutation_row["acquisition_type"] = value
                                    elif "Approved" in header_name or "Date" in header_name:
                                        mutation_row["approved_date"] = value
                            
                            mutation_data["mutations"].append(mutation_row)
                            print(f"Found mutation: MR {mutation_row['mr_number']}")
                
                # Print rows found
                print(f"\nRows found after Fetch Details: {len(mutation_data['mutations'])}")
                
                # If no rows found, take screenshot and save HTML for debugging
                if len(mutation_data["mutations"]) == 0:
                    print("No mutation rows found, saving debug information...")
                    os.makedirs("logs/debug", exist_ok=True)
                    screenshot_path = "logs/debug/mutation_after_fetch.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"Screenshot saved to: {os.path.abspath(screenshot_path)}")
                    
                    html_path = "logs/debug/mutation_after_fetch.html"
                    page_content = await page.content()
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page_content)
                    print(f"Page HTML saved to: {os.path.abspath(html_path)}")
                
                # For each mutation row, click Select and extract details
                for idx, mutation in enumerate(mutation_data["mutations"]):
                    mr_number = mutation["mr_number"]
                    if not mr_number:
                        continue
                    
                    print(f"\nProcessing mutation {idx + 1}/{len(mutation_data['mutations'])}: MR {mr_number}")
                    
                    # Find and click Select link for this row
                    try:
                        # Find all Select links in the table
                        select_links = await page.query_selector_all('a:has-text("Select")')
                        print(f"Found {len(select_links)} Select links")
                        
                        if select_links and idx < len(select_links):
                            # Click the idx-th Select link
                            await select_links[idx].click()
                            print(f"Clicked Select link {idx} for MR {mr_number}")
                            await page.wait_for_load_state("networkidle")
                            await page.wait_for_timeout(2000)
                            
                            # Extract additional fields from the opened page/panel
                            detail_content = await page.content()
                            detail_soup = BeautifulSoup(detail_content, 'html.parser')
                            
                            detail_data = {
                                "mr_number": mr_number,
                                "additional_fields": {}
                            }
                            
                            # Extract all text content from the detail view
                            # Try to find structured data in tables
                            detail_tables = detail_soup.find_all('table')
                            for table in detail_tables:
                                rows = table.find_all('tr')
                                for row in rows:
                                    cols = row.find_all('td')
                                    if cols and len(cols) >= 2:
                                        label = cols[0].get_text(strip=True)
                                        value = cols[1].get_text(strip=True)
                                        if label and value:
                                            detail_data["additional_fields"][label] = value
                            
                            # Take screenshot of the detail view
                            os.makedirs("logs/debug", exist_ok=True)
                            screenshot_path = f"logs/debug/mutation_{mr_number}.png"
                            await page.screenshot(path=screenshot_path, full_page=True)
                            detail_data["screenshot_path"] = screenshot_path
                            print(f"Screenshot saved to: {os.path.abspath(screenshot_path)}")
                            
                            # Try to find document/image
                            doc_element = await page.query_selector('img[src*="Mutation"], img[src*="mutation"], img[src*="MR"], img[src*="mr"]')
                            if doc_element:
                                doc_path = f"logs/debug/mutation_{mr_number}_doc.png"
                                await doc_element.screenshot(path=doc_path)
                                detail_data["document_path"] = doc_path
                                print(f"Captured document to: {os.path.abspath(doc_path)}")
                            else:
                                # Try to find PDF link
                                pdf_link = await page.query_selector('a[href*=".pdf"]')
                                if pdf_link:
                                    pdf_url = await pdf_link.get_attribute('href')
                                    print(f"Found PDF URL: {pdf_url}")
                                    try:
                                        cookies = await context.cookies()
                                        cookie_dict = {c['name']: c['value'] for c in cookies}
                                        headers = {
                                            'Referer': page.url,
                                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                        }
                                        response = requests.get(pdf_url, cookies=cookie_dict, headers=headers, allow_redirects=True)
                                        if response.status_code == 200:
                                            pdf_path = f"logs/debug/mutation_{mr_number}.pdf"
                                            with open(pdf_path, 'wb') as f:
                                                f.write(response.content)
                                            detail_data["document_path"] = pdf_path
                                            print(f"Downloaded PDF to: {os.path.abspath(pdf_path)}")
                                    except Exception as e:
                                        print(f"PDF download failed: {e}")
                            
                            mutation_data["mutation_details"].append(detail_data)
                            
                            # Go back to the main table
                            await page.go_back()
                            await page.wait_for_load_state("networkidle")
                            await page.wait_for_timeout(1000)
                        else:
                            print(f"No Select link found for MR {mr_number}")
                    except Exception as e:
                        print(f"Error processing MR {mr_number}: {e}")
                        # Try to go back if we navigated
                        try:
                            await page.go_back()
                            await page.wait_for_load_state("networkidle")
                        except:
                            pass
                
                await browser.close()
                
                # Print final JSON
                print("\n=== FINAL MUTATION DATA ===")
                import json
                print(json.dumps(mutation_data, indent=2, ensure_ascii=False))
                
                return mutation_data
        
        return await self._retry_with_backoff(_fetch)
