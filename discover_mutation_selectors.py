import asyncio
from playwright.async_api import async_playwright
from scrapers.bhoomi_base import BhoomiBaseScraper

async def discover_selectors():
    scraper = BhoomiBaseScraper()
    
    # Use cached session if available
    if scraper._is_session_valid():
        print("Using cached session")
        cookies_for_playwright = scraper._session_cache
    else:
        # Login first
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
        print("\n=== PAGE LOADED ===")
        print(f"URL: {page.url}")
        
        # Find all select elements
        selects = await page.query_selector_all('select')
        print(f"\nFound {len(selects)} select elements")
        
        for idx, select in enumerate(selects):
            select_id = await select.get_attribute('id')
            select_name = await select.get_attribute('name')
            options = await select.query_selector_all('option')
            print(f"\n--- Select {idx} ---")
            print(f"ID: {select_id}")
            print(f"Name: {select_name}")
            print(f"Number of options: {len(options)}")
            print("First 5 options:")
            for i, opt in enumerate(options[:5]):
                val = await opt.get_attribute('value')
                text = await opt.inner_text()
                print(f"  {i} value={val}, text={text}")
        
        # Find all input elements
        inputs = await page.query_selector_all('input[type="text"], input[type="number"]')
        print(f"\nFound {len(inputs)} text/number input elements")
        
        for idx, inp in enumerate(inputs):
            inp_id = await inp.get_attribute('id')
            inp_name = await inp.get_attribute('name')
            inp_placeholder = await inp.get_attribute('placeholder')
            print(f"\n--- Input {idx} ---")
            print(f"ID: {inp_id}")
            print(f"Name: {inp_name}")
            print(f"Placeholder: {inp_placeholder}")
        
        # Find all buttons
        buttons = await page.query_selector_all('input[type="submit"], button')
        print(f"\nFound {len(buttons)} submit/button elements")
        
        for idx, btn in enumerate(buttons):
            btn_id = await btn.get_attribute('id')
            btn_name = await btn.get_attribute('name')
            btn_value = await btn.get_attribute('value')
            btn_text = await btn.inner_text() if await btn.evaluate('el => el.tagName') == 'BUTTON' else None
            print(f"\n--- Button {idx} ---")
            print(f"ID: {btn_id}")
            print(f"Name: {btn_name}")
            print(f"Value: {btn_value}")
            print(f"Text: {btn_text}")
        
        # Save page HTML for inspection
        html_content = await page.content()
        with open("logs/debug/mutation_page.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nPage HTML saved to: logs/debug/mutation_page.html")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(discover_selectors())
