"""
Discover dashboard navigation path to service37/PreviewRTC.aspx.
Maps the exact sequence to reach the free RTC preview service.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


class Service37Discovery:
    """Discover navigation path to service37 RTC preview."""
    
    def __init__(self, output_dir: str = "logs/debug/bhoomi_live"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load credentials from .env.example file
        env_file = Path(".env.example")
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key == "BHOOMI_USERNAME":
                            self.username = value
                        elif key == "BHOOMI_PASSWORD":
                            self.password = value
        else:
            # Fallback to environment variables
            self.username = os.getenv("BHOOMI_USERNAME", "")
            self.password = os.getenv("BHOOMI_PASSWORD", "")
        
        self.discovery_data = {
            "timestamp": datetime.now().isoformat(),
            "login_success": False,
            "dashboard_url": None,
            "service_links": [],
            "navigation_path": [],
            "service37_url": "https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx",
            "service38_url": "https://landrecords.karnataka.gov.in/service38/",
            "dropdowns_found": [],
            "captcha_detected": False,
            "result_table_structure": None
        }
    
    async def capture_screenshot(self, page, filename: str) -> str:
        """Capture screenshot."""
        filepath = self.output_dir / filename
        await page.screenshot(path=str(filepath))
        return str(filepath)
    
    async def discover(self):
        """Discover navigation path to service37."""
        print("=" * 80)
        print("SERVICE37 NAVIGATION DISCOVERY")
        print("=" * 80)
        
        if not self.username or not self.password:
            print("✗ ERROR: BHOOMI_USERNAME and BHOOMI_PASSWORD must be set")
            return
        
        print(f"\nCredentials loaded: {self.username}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Step 1: Login to citizen portal first (since service37 requires authentication)
                print("\n1. Logging into citizen portal...")
                citizen_portal_url = "https://landrecords.karnataka.gov.in/citizenportal"
                await page.goto(citizen_portal_url, wait_until='networkidle')
                
                await self.capture_screenshot(page, "01_login_page.png")
                
                # Check for CAPTCHA before filling form
                print("   Checking for CAPTCHA...")
                captcha_elements = await page.query_selector_all('img[src*="captcha"], img[src*="Captcha"]')
                if captcha_elements:
                    print("   ⚠ CAPTCHA detected - requires manual intervention")
                    await self.capture_screenshot(page, "02_captcha_detected.png")
                    print("   ⚠ Please solve the CAPTCHA manually in the browser...")
                    print("   ⚠ Waiting 60 seconds for manual CAPTCHA solving...")
                    await page.wait_for_timeout(60000)  # Wait for manual CAPTCHA solving
                else:
                    print("   No CAPTCHA detected")
                
                # Try to find username input with multiple selectors
                username_input = None
                for selector in ['#txtUname', 'input[name*="user"]', 'input[id*="user"]']:
                    try:
                        username_input = await page.wait_for_selector(selector, timeout=3000)
                        if username_input:
                            print(f"   Found username input with selector: {selector}")
                            break
                    except:
                        continue
                
                if not username_input:
                    print("   ✗ Username input not found")
                    return
                
                # Try to find password input with multiple selectors
                password_input = None
                for selector in ['#txtPwd', '#Password2', 'input[type="password"]']:
                    try:
                        password_input = await page.wait_for_selector(selector, timeout=3000)
                        if password_input:
                            print(f"   Found password input with selector: {selector}")
                            break
                    except:
                        continue
                
                if not password_input:
                    print("   ✗ Password input not found")
                    return
                
                # Fill username first
                await username_input.fill(self.username)
                await page.wait_for_timeout(500)
                
                # Check if password input is enabled after filling username
                is_enabled = await password_input.is_enabled()
                print(f"   Password input enabled after username: {is_enabled}")
                
                if not is_enabled:
                    print("   ⚠ Password input still disabled - waiting for CAPTCHA to be solved...")
                    print("   ⚠ Please solve CAPTCHA if not already done...")
                    print("   ⚠ Waiting additional 30 seconds...")
                    await page.wait_for_timeout(30000)
                    
                    # Check again
                    is_enabled = await password_input.is_enabled()
                    print(f"   Password input enabled after wait: {is_enabled}")
                    
                    if not is_enabled:
                        print("   ✗ Password input still disabled - cannot proceed")
                        return
                
                # Fill password
                await password_input.fill(self.password)
                await self.capture_screenshot(page, "03_filled_login.png")
                
                submit_button = await page.query_selector('input[type="submit"], button[type="submit"]')
                if submit_button:
                    await submit_button.click()
                    await page.wait_for_timeout(5000)
                
                current_url = page.url
                print(f"   Current URL after login: {current_url}")
                
                if current_url != citizen_portal_url:
                    self.discovery_data["login_success"] = True
                    self.discovery_data["dashboard_url"] = current_url
                    print("   ✓ Login successful")
                else:
                    print("   ✗ Login failed")
                    return
                
                await self.capture_screenshot(page, "04_dashboard.png")
                
                # Step 2: Find all service links on dashboard
                print("\n2. Finding service links on dashboard...")
                links = await page.query_selector_all('a[href]')
                service_links = []
                
                for link in links:
                    try:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        if href and ('service' in href.lower() or 'rtc' in href.lower() or 'preview' in href.lower()):
                            service_links.append({
                                "text": text.strip() if text else "",
                                "href": href
                            })
                    except:
                        continue
                
                self.discovery_data["service_links"] = service_links
                print(f"   Found {len(service_links)} service links")
                
                for i, link in enumerate(service_links[:30]):  # Show first 30
                    print(f"   {i+1}. {link['text']}: {link['href']}")
                
                # Step 3: Try to navigate to service37 through dashboard
                print("\n3. Attempting to navigate to service37...")
                
                # First try direct navigation
                service37_url = self.discovery_data["service37_url"]
                await page.goto(service37_url, wait_until='networkidle')
                await self.capture_screenshot(page, "05_service37_direct.png")
                print(f"   Current URL: {page.url}")
                
                # If 405 error, try POST method or find the correct link
                if "405" in await page.title() or "not allowed" in await page.title():
                    print("   ⚠ 405 error - trying to find correct service link on dashboard")
                    
                    # Look for service37 or PreviewRTC links
                    for link in service_links:
                        if 'service37' in link['href'].lower() or 'previewrtc' in link['href'].lower() or 'preview' in link['href'].lower():
                            print(f"   Found potential link: {link['text']} -> {link['href']}")
                            try:
                                await page.goto(link['href'], wait_until='networkidle')
                                await self.capture_screenshot(page, "06_service37_via_link.png")
                                print(f"   Current URL: {page.url}")
                                
                                if "405" not in await page.title() and "not allowed" not in await page.title():
                                    print("   ✓ Successfully navigated to service37")
                                    break
                            except:
                                continue
                
                # Step 4: Analyze current page structure
                print("\n4. Analyzing current page structure...")
                current_url = page.url
                print(f"   Current URL: {current_url}")
                
                # Get page title
                page_title = await page.title()
                print(f"   Page Title: {page_title}")
                
                # Check for dropdowns
                print("\n5. Checking for dropdowns...")
                dropdowns = await page.query_selector_all('select')
                print(f"   Found {len(dropdowns)} dropdowns")
                
                for i, dropdown in enumerate(dropdowns):
                    try:
                        select_id = await dropdown.get_attribute('id')
                        select_name = await dropdown.get_attribute('name')
                        
                        # Get options
                        options = []
                        option_elements = await dropdown.query_selector_all('option')
                        for opt in option_elements:
                            opt_text = await opt.text_content()
                            opt_value = await opt.get_attribute('value')
                            options.append({
                                "text": opt_text.strip() if opt_text else None,
                                "value": opt_value
                            })
                        
                        dropdown_info = {
                            "index": i,
                            "id": select_id,
                            "name": select_name,
                            "option_count": len(options),
                            "sample_options": options[:5]  # First 5 options
                        }
                        self.discovery_data["dropdowns_found"].append(dropdown_info)
                        
                        print(f"   Dropdown {i+1}: {select_name or select_id} ({len(options)} options)")
                        for opt in options[:3]:
                            print(f"      - {opt['text']}: {opt['value']}")
                            
                    except Exception as e:
                        print(f"   Error analyzing dropdown {i}: {e}")
                
                # Check for survey number input
                print("\n6. Checking for survey number input...")
                survey_inputs = await page.query_selector_all('input[name*="survey"], input[id*="survey"], input[placeholder*="survey"]')
                print(f"   Found {len(survey_inputs)} survey number inputs")
                
                for inp in survey_inputs:
                    try:
                        inp_id = await inp.get_attribute('id')
                        inp_name = await inp.get_attribute('name')
                        inp_placeholder = await inp.get_attribute('placeholder')
                        print(f"   - {inp_name or inp_id}: {inp_placeholder}")
                    except:
                        continue
                
                # Check for all input fields
                print("\n7. Checking for all input fields...")
                all_inputs = await page.query_selector_all('input:not([type="hidden"])')
                print(f"   Found {len(all_inputs)} input fields")
                
                for inp in all_inputs:
                    try:
                        inp_type = await inp.get_attribute('type')
                        inp_id = await inp.get_attribute('id')
                        inp_name = await inp.get_attribute('name')
                        inp_placeholder = await inp.get_attribute('placeholder')
                        print(f"   - {inp_type} | {inp_name or inp_id} | {inp_placeholder}")
                    except:
                        continue
                
                # Check for buttons/submit
                print("\n8. Checking for buttons...")
                buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"]')
                print(f"   Found {len(buttons)} buttons")
                
                for btn in buttons:
                    try:
                        btn_text = await btn.text_content()
                        btn_type = await btn.get_attribute('type')
                        btn_id = await btn.get_attribute('id')
                        print(f"   - {btn_type or 'button'} | {btn_id or 'N/A'} | {btn_text.strip() if btn_text else 'N/A'}")
                    except:
                        continue
                
                # Check for tables (result tables)
                print("\n9. Checking for result tables...")
                tables = await page.query_selector_all('table')
                print(f"   Found {len(tables)} tables")
                
                for i, table in enumerate(tables):
                    try:
                        rows = await table.query_selector_all('tr')
                        print(f"   Table {i+1}: {len(rows)} rows")
                        
                        # Get first few rows to understand structure
                        for j, row in enumerate(rows[:3]):
                            cells = await row.query_selector_all('td, th')
                            row_text = []
                            for cell in cells:
                                cell_text = await cell.text_content()
                                row_text.append(cell_text.strip() if cell_text else "")
                            print(f"      Row {j+1}: {' | '.join(row_text[:5])}")
                    except:
                        continue
                
                # Check for captcha
                print("\n10. Checking for captcha...")
                captcha_elements = await page.query_selector_all('img[src*="captcha"], img[src*="Captcha"], img[id*="captcha"]')
                if captcha_elements:
                    self.discovery_data["captcha_detected"] = True
                    print("   ✓ Captcha detected")
                else:
                    print("   No captcha detected")
                
                # Save discovery data
                import json
                output_file = self.output_dir / "service37_discovery.json"
                with open(output_file, 'w') as f:
                    json.dump(self.discovery_data, f, indent=2)
                print(f"\nDiscovery data saved to: {output_file}")
                
                print("\n" + "=" * 80)
                print("DISCOVERY COMPLETE")
                print("=" * 80)
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()


async def main():
    """Main execution."""
    discovery = Service37Discovery()
    await discovery.discover()


if __name__ == "__main__":
    asyncio.run(main())
