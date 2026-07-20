import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def extract_table_data(page):
    """Extract data from the results table."""
    results = []
    
    try:
        # Try to find the results table
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
            mapped_data = map_fields(row_data)
            if mapped_data:
                results.append(mapped_data)
        
    except Exception as e:
        print(f"Error extracting table data: {e}")
        import traceback
        traceback.print_exc()
    
    return results


def map_fields(row_data):
    """Map raw table data to expected field names."""
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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Step 1: Login
        print("=== STEP 1: LOGIN ===")
        await page.goto(
            "https://kaveri.karnataka.gov.in/landing-page",
            timeout=60000,
            wait_until="domcontentloaded"
        )
        
        await page.wait_for_load_state("networkidle")
        
        print("\n=== LOGIN MANUALLY THEN PRESS ENTER ===")
        input()
        
        # Save cookies
        await page.wait_for_timeout(2000)
        cookies = await context.cookies()
        
        with open("logs/debug/kaveri_session.json", "w") as f:
            json.dump(cookies, f, indent=2)
        
        print(f"Saved {len(cookies)} cookies")
        print(f"Current page URL: {page.url}")
        
        # Step 2: EC Search
        print("\n=== STEP 2: EC SEARCH ===")
        ec_search_url = "https://kaveri.karnataka.gov.in/ec-search-citizen"
        
        await page.goto(
            ec_search_url,
            timeout=60000,
            wait_until="domcontentloaded"
        )
        
        print(f"Navigated to: {ec_search_url}")
        print("\n=== ENTER SEARCH DETAILS MANUALLY THEN PRESS ENTER ===")
        input()
        
        # Extract results
        await page.wait_for_timeout(2000)
        
        # Take screenshot
        debug_dir = Path("logs/debug")
        kaveri_dir = debug_dir / "kaveri"
        kaveri_dir.mkdir(parents=True, exist_ok=True)
        screenshot_file = kaveri_dir / "ec_results.png"
        
        print(f"Taking screenshot: {screenshot_file}")
        await page.screenshot(path=str(screenshot_file), full_page=True)
        
        # Extract table data
        print("Extracting EC results from table...")
        results = await extract_table_data(page)
        
        if results:
            results_file = debug_dir / "kaveri_ec_results.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"\n=== EXTRACTION COMPLETE ===")
            print(f"Found {len(results)} EC records")
            print(f"Results saved to: {results_file}")
            print(f"Screenshot saved to: {screenshot_file}")
            
            # Print sample result
            if results:
                print("\nSample record:")
                print(json.dumps(results[0], indent=2))
        else:
            print("No EC records found in the table")
        
        print("\n=== COMPLETE ===")
        print("Press ENTER to close browser...")
        input()
        
        await browser.close()


asyncio.run(main())
