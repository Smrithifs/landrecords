from playwright.async_api import async_playwright
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="/Users/smrithis/Library/Application Support/Google/Chrome/Default",
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False
        )
        page = await context.new_page()
        
        postback_data = []
        
        async def handle_request(request):
            if request.method == "POST":
                print(f"\n=== POST REQUEST ===")
                print(f"URL: {request.url}")
                post_data = request.post_data
                if post_data:
                    # Parse form data
                    parsed = parse_qs(post_data)
                    postback_entry = {
                        "url": request.url,
                        "post_data": post_data,
                        "parsed": {}
                    }
                    
                    for key, value in parsed.items():
                        if key not in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
                            print(f"  {key}: {value}")
                            postback_entry["parsed"][key] = value
                    
                    viewstate_len = len(parsed.get("__VIEWSTATE", [""])[0])
                    print(f"  __VIEWSTATE length: {viewstate_len}")
                    postback_entry["viewstate_length"] = viewstate_len
                    
                    postback_data.append(postback_entry)
        
        page.on("request", handle_request)
        
        # Navigate to citizen portal login page
        print("Navigating to citizen portal login page...")
        await page.goto("https://landrecords.karnataka.gov.in/citizenportal")
        
        print("LOGIN NOW THEN PRESS ENTER")
        input()
        
        # Navigate to service37
        print("\nNavigating to service37/PreviewRTC.aspx...")
        await page.goto("https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx")
        
        # Get current dropdowns
        print("\n=== CURRENT DROPDOWNS ===")
        dropdowns = await page.query_selector_all('select')
        for i, dropdown in enumerate(dropdowns):
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            print(f"Dropdown {i+1}: {select_name or select_id}")
            
            # Get options
            options = await dropdown.query_selector_all('option')
            for opt in options[:5]:  # Show first 5 options
                opt_text = await opt.text_content()
                opt_value = await opt.get_attribute('value')
                print(f"  - {opt_text}: {opt_value}")
            if len(options) > 5:
                print(f"  ... and {len(options) - 5} more options")
        
        print("\nSELECT DISTRICT FROM DROPDOWN THEN PRESS ENTER")
        input()
        
        # Get dropdowns after district selection
        print("\n=== DROPDOWNS AFTER DISTRICT SELECTION ===")
        dropdowns = await page.query_selector_all('select')
        for i, dropdown in enumerate(dropdowns):
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            print(f"Dropdown {i+1}: {select_name or select_id}")
            
            options = await dropdown.query_selector_all('option')
            for opt in options[:5]:
                opt_text = await opt.text_content()
                opt_value = await opt.get_attribute('value')
                print(f"  - {opt_text}: {opt_value}")
            if len(options) > 5:
                print(f"  ... and {len(options) - 5} more options")
        
        print("\nSELECT TALUK THEN PRESS ENTER")
        input()
        
        print("\n=== DROPDOWNS AFTER TALUK SELECTION ===")
        dropdowns = await page.query_selector_all('select')
        for i, dropdown in enumerate(dropdowns):
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            print(f"Dropdown {i+1}: {select_name or select_id}")
            
            options = await dropdown.query_selector_all('option')
            for opt in options[:5]:
                opt_text = await opt.text_content()
                opt_value = await opt.get_attribute('value')
                print(f"  - {opt_text}: {opt_value}")
            if len(options) > 5:
                print(f"  ... and {len(options) - 5} more options")
        
        print("\nSELECT HOBLI THEN PRESS ENTER")
        input()
        
        print("\n=== DROPDOWNS AFTER HOBLI SELECTION ===")
        dropdowns = await page.query_selector_all('select')
        for i, dropdown in enumerate(dropdowns):
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            print(f"Dropdown {i+1}: {select_name or select_id}")
            
            options = await dropdown.query_selector_all('option')
            for opt in options[:5]:
                opt_text = await opt.text_content()
                opt_value = await opt.get_attribute('value')
                print(f"  - {opt_text}: {opt_value}")
            if len(options) > 5:
                print(f"  ... and {len(options) - 5} more options")
        
        print("\nSELECT VILLAGE THEN PRESS ENTER")
        input()
        
        print("\n=== DROPDOWNS AFTER VILLAGE SELECTION ===")
        dropdowns = await page.query_selector_all('select')
        for i, dropdown in enumerate(dropdowns):
            select_id = await dropdown.get_attribute('id')
            select_name = await dropdown.get_attribute('name')
            print(f"Dropdown {i+1}: {select_name or select_id}")
            
            options = await dropdown.query_selector_all('option')
            for opt in options[:5]:
                opt_text = await opt.text_content()
                opt_value = await opt.get_attribute('value')
                print(f"  - {opt_text}: {opt_value}")
            if len(options) > 5:
                print(f"  ... and {len(options) - 5} more options")
        
        print("\nENTER SURVEY NO AND CLICK FETCH THEN PRESS ENTER")
        input()
        
        # Save final page HTML
        print("\nSaving final page HTML...")
        content = await page.content()
        output_dir = Path("logs/debug")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        html_file = output_dir / "rtc_result.html"
        with open(html_file, 'w') as f:
            f.write(content)
        print(f"Saved to: {html_file}")
        
        # Save postback data
        json_file = output_dir / "postback_data.json"
        with open(json_file, 'w') as f:
            json.dump(postback_data, f, indent=2)
        print(f"Saved {len(postback_data)} POST requests to: {json_file}")
        
        await context.close()

asyncio.run(main())
