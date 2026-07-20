"""
Kaveri EC Results Extraction Script
Extract data from EC search results table and save as structured JSON.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import datetime


class KaveriECExtractor:
    """Extract EC search results from Kaveri portal."""
    
    def __init__(self):
        self.ec_search_url = "https://staging.kaveri.karnataka.gov.in/ec-search-citizen"
        self.debug_dir = Path("logs/debug")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.kaveri_dir = self.debug_dir / "kaveri"
        self.kaveri_dir.mkdir(parents=True, exist_ok=True)
        
        self.results_file = self.debug_dir / "kaveri_ec_results.json"
        self.screenshot_file = self.kaveri_dir / "ec_results.png"
        
        self.session_file = self.debug_dir / "kaveri_session.json"
    
    async def load_session(self, context):
        """Load session cookies from file."""
        if not self.session_file.exists():
            print(f"Session file not found: {self.session_file}")
            print("Please run kaveri_save_session.py first to create a session.")
            return False
        
        with open(self.session_file, 'r') as f:
            cookies = json.load(f)
        
        await context.add_cookies(cookies)
        print(f"Loaded {len(cookies)} cookies from session")
        return True
    
    async def extract_ec_results(self):
        """Extract EC results from the search page."""
        print("=== Kaveri EC Results Extraction ===")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Load session
            if not await self.load_session(context):
                await browser.close()
                return
            
            # Navigate to EC search page
            print(f"\nNavigating to {self.ec_search_url}...")
            await page.goto(
                self.ec_search_url,
                timeout=60000,
                wait_until="domcontentloaded"
            )
            
            print("\n=== MANUAL SEARCH REQUIRED ===")
            print("=== FILL THE SEARCH FORM MANUALLY ===")
            print("=== CLICK SEARCH TO GET RESULTS ===")
            print("=== PRESS ENTER WHEN RESULTS ARE VISIBLE ===")
            input()
            
            # Wait for results to load
            await page.wait_for_timeout(2000)
            
            # Take screenshot
            print(f"\nTaking screenshot: {self.screenshot_file}")
            await page.screenshot(path=str(self.screenshot_file), full_page=True)
            
            # Extract table data
            print("Extracting EC results from table...")
            results = await self.extract_table_data(page)
            
            if results:
                # Save results to JSON
                with open(self.results_file, 'w') as f:
                    json.dump(results, f, indent=2)
                
                print(f"\n=== EXTRACTION COMPLETE ===")
                print(f"Found {len(results)} EC records")
                print(f"Results saved to: {self.results_file}")
                print(f"Screenshot saved to: {self.screenshot_file}")
                
                # Print sample result
                if results:
                    print("\nSample record:")
                    print(json.dumps(results[0], indent=2))
            else:
                print("No EC records found in the table")
            
            print("\nPress ENTER to close browser...")
            input()
            
            await browser.close()
    
    async def extract_table_data(self, page):
        """Extract data from the results table."""
        results = []
        
        try:
            # Try to find the results table
            # Common table selectors
            table_selectors = [
                'table',
                '.table',
                '#resultsTable',
                '.results-table',
                'table[class*="table"]'
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    table = await page.query_selector(selector)
                    if table:
                        print(f"Found table using selector: {selector}")
                        break
                except:
                    continue
            
            if not table:
                print("No results table found")
                return results
            
            # Get all rows
            rows = await table.query_selector_all('tr')
            print(f"Found {len(rows)} rows in table")
            
            # Extract headers from first row
            headers = []
            if rows:
                header_cells = await rows[0].query_selector_all('th, td')
                for cell in header_cells:
                    text = await cell.text_content()
                    headers.append(text.strip() if text else "")
            
            print(f"Headers: {headers}")
            
            # Extract data from remaining rows
            for row in rows[1:]:  # Skip header row
                cells = await row.query_selector_all('td')
                if not cells:
                    continue
                
                row_data = {}
                for i, cell in enumerate(cells):
                    text = await cell.text_content()
                    if i < len(headers):
                        row_data[headers[i]] = text.strip() if text else ""
                    else:
                        row_data[f"column_{i}"] = text.strip() if text else ""
                
                # Map to expected fields
                mapped_data = self.map_fields(row_data)
                if mapped_data:
                    results.append(mapped_data)
            
        except Exception as e:
            print(f"Error extracting table data: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def map_fields(self, row_data):
        """Map raw table data to expected field names."""
        # Try to map based on common column names
        mapped = {}
        
        # Field mappings (case-insensitive)
        field_mappings = {
            'hobli': ['hobli', 'hobli name', 'hobliname'],
            'village': ['village', 'village name', 'villagename'],
            'property_number': ['property number', 'property no', 'property_no', 'propertynumber', 'survey no', 'survey_no', 'survey number'],
            'date': ['date', 'registration date', 'reg date', 'document date'],
            'article_name': ['article name', 'article', 'article type', 'document type'],
            'market_value': ['market value', 'marketvalue', 'mv'],
            'consideration_amount': ['consideration amount', 'consideration', 'considerationamount', 'sale amount'],
            'party_names': ['party names', 'executants', 'parties', 'executant names'],
            'claimant_names': ['claimant names', 'claimants', 'claimant'],
            'document_number': ['document number', 'document no', 'document_no', 'doc number', 'docno'],
            'book_number': ['book number', 'book no', 'book_no', 'booknumber'],
            'registration_number': ['registration number', 'reg no', 'reg_no', 'registration no', 'regno', 'sro no', 'sro_no']
        }
        
        # Map fields
        for target_field, possible_keys in field_mappings.items():
            for key, value in row_data.items():
                if any(pk in key.lower() for pk in possible_keys):
                    mapped[target_field] = value
                    break
        
        # If no mapping found, use raw data
        if not mapped:
            mapped = row_data
        
        return mapped


async def main():
    extractor = KaveriECExtractor()
    await extractor.extract_ec_results()


if __name__ == "__main__":
    asyncio.run(main())
