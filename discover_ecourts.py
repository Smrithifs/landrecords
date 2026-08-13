"""
eCourts page structure discovery script.
Maps the page to understand form elements and selectors.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    """Discover eCourts page structure."""
    
    # Create debug directory
    debug_dir = Path("logs/debug/ecourts")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Navigate to eCourts
        print("Navigating to eCourts...")
        await page.goto(
            "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus/index",
            wait_until="domcontentloaded",
            timeout=60000
        )
        
        # Wait 3 seconds
        print("Waiting 3 seconds...")
        await asyncio.sleep(3)
        
        # Save screenshot
        screenshot_path = debug_dir / "page.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"Screenshot saved to: {screenshot_path}")
        
        # Save HTML
        content = await page.content()
        html_path = debug_dir / "page.html"
        with open(html_path, "w") as f:
            f.write(content)
        print(f"HTML saved to: {html_path}")
        print("Page saved")
        
        # Print all select element IDs
        print("\n=== SELECT ELEMENTS ===")
        selects = await page.query_selector_all("select")
        for s in selects:
            elem_id = await s.get_attribute("id")
            elem_name = await s.get_attribute("name")
            print(f"ID: {elem_id}, Name: {elem_name}")
        
        # Print all input IDs
        print("\n=== INPUT ELEMENTS ===")
        inputs = await page.query_selector_all("input")
        for i in inputs:
            elem_id = await i.get_attribute("id")
            elem_type = await i.get_attribute("type")
            elem_name = await i.get_attribute("name")
            print(f"ID: {elem_id}, Type: {elem_type}, Name: {elem_name}")
        
        await browser.close()
        print("\nDiscovery complete")

if __name__ == "__main__":
    asyncio.run(main())
