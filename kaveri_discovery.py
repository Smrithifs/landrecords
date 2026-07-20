import asyncio
import json
import os
from playwright.async_api import async_playwright

async def discover_kaveri():
    """Discover Kaveri Online portal structure and accessibility"""
    
    discovery_report = {
        "portal_url": "https://kaverionline.karnataka.gov.in",
        "timestamp": "",
        "landing_page": {
            "url": "",
            "title": "",
            "screenshot": "logs/debug/kaveri/landing.png",
            "accessible_without_login": False
        },
        "ec_search": {
            "found": False,
            "accessible_without_login": False,
            "url": "",
            "form_fields": []
        },
        "network_requests": [],
        "sample_search": {
            "attempted": False,
            "success": False,
            "error": ""
        }
    }
    
    from datetime import datetime
    discovery_report["timestamp"] = datetime.now().isoformat()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Enable network request interception
        network_requests = []
        
        async def handle_request(request):
            network_requests.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type
            })
        
        context.on("request", handle_request)
        
        page = await context.new_page()
        
        print("=== Step 1: Opening landing page ===")
        try:
            await page.goto("https://kaverionline.karnataka.gov.in", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            print(f"Error loading page: {e}")
            print("Trying with networkidle...")
            await page.goto("https://kaverionline.karnataka.gov.in", wait_until="networkidle", timeout=120000)
        
        discovery_report["landing_page"]["url"] = page.url
        discovery_report["landing_page"]["title"] = await page.title()
        
        # Screenshot landing page
        await page.screenshot(path="logs/debug/kaveri/landing.png", full_page=True)
        print(f"Landing page screenshot saved to logs/debug/kaveri/landing.png")
        
        # Check if accessible without login
        if "login" not in page.url.lower():
            discovery_report["landing_page"]["accessible_without_login"] = True
            print("Landing page accessible without login")
        else:
            print("Landing page requires login")
        
        print("\n=== Step 2: Looking for EC Search ===")
        # Look for EC search links or buttons
        ec_links = await page.query_selector_all('a:has-text("EC"), a:has-text("Encumbrance"), a:has-text("Certificate")')
        print(f"Found {len(ec_links)} potential EC-related links")
        
        for link in ec_links:
            text = await link.text_content()
            href = await link.get_attribute('href')
            print(f"  Link: '{text}' -> {href}")
        
        # Look for EC search forms
        ec_forms = await page.query_selector_all('form')
        print(f"Found {len(ec_forms)} forms on the page")
        
        # Look for dropdowns that might be SRO selection
        dropdowns = await page.query_selector_all('select')
        print(f"Found {len(dropdowns)} dropdowns")
        
        for dropdown in dropdowns:
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            options = await dropdown.query_selector_all('option')
            option_count = len(options)
            print(f"  Dropdown: id='{select_id}' name='{select_name}' options={option_count}")
            
            # Get first few options
            for i, opt in enumerate(options[:5]):
                val = await opt.get_attribute('value')
                txt = await opt.text_content()
                print(f"    Option {i}: value='{val}' text='{txt}'")
        
        # Look for input fields
        inputs = await page.query_selector_all('input[type="text"], input[type="number"], input[type="date"]')
        print(f"Found {len(inputs)} text/number/date inputs")
        
        for inp in inputs:
            inp_id = await inp.get_attribute('id')
            inp_name = await inp.get_attribute('name')
            inp_placeholder = await inp.get_attribute('placeholder')
            print(f"  Input: id='{inp_id}' name='{inp_name}' placeholder='{inp_placeholder}'")
        
        # Try to find EC search specifically
        ec_search_found = False
        ec_search_url = ""
        
        # Check for common EC search patterns
        ec_selectors = [
            'a[href*="ec"]',
            'a[href*="encumbrance"]',
            'a[href*="certificate"]',
            'button:has-text("EC")',
            'button:has-text("Encumbrance")',
            'input[value*="EC"]',
            'input[value*="Search"]'
        ]
        
        for selector in ec_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                ec_search_found = True
                for el in elements:
                    href = await el.get_attribute('href')
                    if href:
                        ec_search_url = href
                        print(f"Found EC search element: {selector} -> {href}")
                        break
                break
        
        discovery_report["ec_search"]["found"] = ec_search_found
        discovery_report["ec_search"]["url"] = ec_search_url
        
        if ec_search_found:
            print("\n=== Step 3: Navigating to EC search ===")
            if ec_search_url.startswith('http'):
                await page.goto(ec_search_url)
            else:
                await page.click(selector)
            await page.wait_for_load_state("networkidle")
            
            await page.screenshot(path="logs/debug/kaveri/ec_search_page.png", full_page=True)
            print("EC search page screenshot saved")
            
            discovery_report["ec_search"]["accessible_without_login"] = "login" not in page.url.lower()
            
            # Find form fields on EC search page
            ec_form_fields = []
            
            # Get all form inputs
            ec_inputs = await page.query_selector_all('input, select, textarea')
            for inp in ec_inputs:
                field_info = {
                    "tag": inp.tag_name,
                    "id": await inp.get_attribute('id'),
                    "name": await inp.get_attribute('name'),
                    "type": await inp.get_attribute('type'),
                    "placeholder": await inp.get_attribute('placeholder'),
                    "required": await inp.get_attribute('required')
                }
                
                # Get options for select elements
                if inp.tag_name == 'select':
                    options = await inp.query_selector_all('option')
                    field_info["options"] = []
                    for opt in options[:10]:  # Limit to first 10 options
                        val = await opt.get_attribute('value')
                        txt = await opt.text_content()
                        field_info["options"].append({"value": val, "text": txt})
                
                ec_form_fields.append(field_info)
            
            discovery_report["ec_search"]["form_fields"] = ec_form_fields
            print(f"Found {len(ec_form_fields)} form fields on EC search page")
            
            # Try a sample search if public access exists
            if discovery_report["ec_search"]["accessible_without_login"]:
                print("\n=== Step 4: Attempting sample search ===")
                discovery_report["sample_search"]["attempted"] = True
                
                # Try to find and fill SRO dropdown
                sro_dropdown = await page.query_selector('select[name*="sro"], select[id*="sro"]')
                if sro_dropdown:
                    options = await sro_dropdown.query_selector_all('option')
                    if len(options) > 1:
                        # Select second option (first is usually "Select SRO")
                        await sro_dropdown.select_option(index=1)
                        print("Selected SRO option")
                
                # Try to find and fill property number
                prop_input = await page.query_selector('input[name*="property"], input[name*="number"], input[id*="property"]')
                if prop_input:
                    await prop_input.fill("123")
                    print("Filled property number")
                
                # Try to find and fill year
                year_input = await page.query_selector('input[name*="year"], input[id*="year"]')
                if year_input:
                    await year_input.fill("2024")
                    print("Filled year")
                
                # Try to click search button
                search_button = await page.query_selector('button:has-text("Search"), input[type="submit"], input[value*="Search"]')
                if search_button:
                    await search_button.click()
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(3000)
                    
                    await page.screenshot(path="logs/debug/kaveri/sample_search_result.png", full_page=True)
                    print("Sample search result screenshot saved")
                    
                    discovery_report["sample_search"]["success"] = True
                else:
                    discovery_report["sample_search"]["error"] = "Search button not found"
                    print("Search button not found")
            else:
                print("EC search requires login, skipping sample search")
        else:
            print("EC search not found on landing page")
        
        # Save network requests
        discovery_report["network_requests"] = network_requests
        print(f"\nCaptured {len(network_requests)} network requests")
        
        await browser.close()
    
    # Save discovery report
    os.makedirs("logs/debug/kaveri", exist_ok=True)
    with open("logs/debug/kaveri/discovery.json", "w") as f:
        json.dump(discovery_report, f, indent=2)
    
    print("\n=== Discovery Complete ===")
    print(f"Report saved to logs/debug/kaveri/discovery.json")
    print(f"\nSummary:")
    print(f"  Landing page accessible without login: {discovery_report['landing_page']['accessible_without_login']}")
    print(f"  EC search found: {discovery_report['ec_search']['found']}")
    print(f"  EC search accessible without login: {discovery_report['ec_search']['accessible_without_login']}")
    print(f"  Form fields found: {len(discovery_report['ec_search']['form_fields'])}")
    print(f"  Sample search attempted: {discovery_report['sample_search']['attempted']}")
    print(f"  Sample search success: {discovery_report['sample_search']['success']}")

if __name__ == "__main__":
    asyncio.run(discover_kaveri())
