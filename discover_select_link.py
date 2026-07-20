import asyncio
from playwright.async_api import async_playwright
from scrapers.bhoomi_base import BhoomiBaseScraper

async def discover_select_link():
    scraper = BhoomiBaseScraper()
    
    # Use cached session if available
    if scraper._is_session_valid():
        print("Using cached session")
        cookies_for_playwright = scraper._session_cache
    else:
        print("=== LOGIN ===")
        cookies_for_playwright = await scraper._http_login()
        scraper._update_session_cache(cookies_for_playwright)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.add_cookies(cookies_for_playwright)
        page = await context.new_page()
        
        # Navigate to Mutation Extract page
        await page.goto("https://landrecords.karnataka.gov.in/Service11/MR_MutationExtract.aspx")
        await page.wait_for_load_state("networkidle")
        
        # Fill form
        await page.select_option('#ctl00_MainContent_drpdist', value='20')  # BENGALURU
        await page.wait_for_timeout(1000)
        await page.select_option('#ctl00_MainContent_drptaluk', value='5')  # Bangalore North(Additional)
        await page.wait_for_timeout(1000)
        await page.select_option('#ctl00_MainContent_drphobli', value='1')  # YALAHANKA1
        await page.wait_for_timeout(1000)
        await page.select_option('#ctl00_MainContent_drpvillage', value='15')  # KRUSHNASAGARA
        await page.wait_for_timeout(1000)
        await page.fill('#ctl00_MainContent_txtSurvey', '2')
        
        # Click Fetch Details
        await page.click('#ctl00_MainContent_btnFetch')
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        
        # Find all links in the table
        print("\n=== FINDING ALL LINKS ===")
        all_links = await page.query_selector_all('a')
        print(f"Found {len(all_links)} links total")
        
        for idx, link in enumerate(all_links):
            link_text = await link.inner_text()
            link_href = await link.get_attribute('href')
            link_id = await link.get_attribute('id')
            link_class = await link.get_attribute('class')
            
            if link_text and ('select' in link_text.lower() or 'Select' in link_text):
                print(f"\n--- Link {idx} (Select candidate) ---")
                print(f"Text: {link_text}")
                print(f"Href: {link_href}")
                print(f"ID: {link_id}")
                print(f"Class: {link_class}")
        
        # Also check table cells
        print("\n=== CHECKING TABLE CELLS ===")
        tables = await page.query_selector_all('table')
        for table_idx, table in enumerate(tables):
            rows = await table.query_selector_all('tr')
            for row_idx, row in enumerate(rows):
                cells = await row.query_selector_all('td')
                for cell_idx, cell in enumerate(cells):
                    cell_text = await cell.inner_text()
                    if 'select' in cell_text.lower() or 'Select' in cell_text:
                        print(f"\nTable {table_idx}, Row {row_idx}, Cell {cell_idx}")
                        print(f"Text: {cell_text}")
                        # Check if there's a link inside
                        inner_link = await cell.query_selector('a')
                        if inner_link:
                            link_href = await inner_link.get_attribute('href')
                            link_id = await inner_link.get_attribute('id')
                            link_class = await inner_link.get_attribute('class')
                            print(f"  Inner link href: {link_href}")
                            print(f"  Inner link id: {link_id}")
                            print(f"  Inner link class: {link_class}")
        
        # Save HTML for inspection
        html_content = await page.content()
        with open("logs/debug/mutation_table_with_links.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nHTML saved to: logs/debug/mutation_table_with_links.html")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(discover_select_link())
