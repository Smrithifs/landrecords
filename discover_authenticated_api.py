"""
Intercept API calls from authenticated Bhoomi session using Chrome profile.
Connects to existing Chrome browser or launches with saved profile to capture
network traffic during RTC data retrieval.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


class AuthenticatedAPIInterceptor:
    """Intercept API calls using authenticated Chrome session."""
    
    def __init__(self, output_dir: str = "logs/debug"):
        self.output_dir = Path(output_dir)
        self.api_steps_dir = self.output_dir / "api_steps"
        self.api_steps_dir.mkdir(parents=True, exist_ok=True)
        
        self.network_data = {
            "timestamp": datetime.now().isoformat(),
            "url": "https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx",
            "steps": [],
            "requests": []
        }
        
        self.step_counter = 0
    
    async def handle_request(self, request):
        """Handle incoming requests."""
        resource_type = request.resource_type
        url = request.url
        
        # Log all requests (not just fetch/XHR to see everything)
        request_data = {
            "url": url,
            "method": request.method,
            "resource_type": resource_type,
            "headers": dict(request.headers),
            "post_data": request.post_data
        }
        self.network_data["requests"].append(request_data)
        print(f"  [REQUEST] {request.method} {url}")
    
    async def handle_response(self, response):
        """Handle responses."""
        resource_type = response.request.resource_type
        url = response.url
        
        # Only log responses for API-like requests
        if resource_type in ['fetch', 'xhr', 'document']:
            try:
                body = await response.text()
                response_data = {
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body[:50000]  # Limit body size
                }
                
                # Update corresponding request with response data
                for req in self.network_data["requests"]:
                    if req["url"] == url:
                        req["response"] = response_data
                        break
                
                print(f"  [RESPONSE] {response.status} {url}")
            except Exception as e:
                print(f"  [ERROR] Could not get response body for {url}: {e}")
    
    async def capture_step(self, page, step_name: str):
        """Capture screenshot and log step."""
        self.step_counter += 1
        screenshot_path = self.api_steps_dir / f"step_{self.step_counter:02d}_{step_name}.png"
        await page.screenshot(path=str(screenshot_path))
        
        step_info = {
            "step_number": self.step_counter,
            "step_name": step_name,
            "url": page.url,
            "screenshot": str(screenshot_path),
            "timestamp": datetime.now().isoformat()
        }
        self.network_data["steps"].append(step_info)
        
        print(f"\n[STEP {self.step_counter}] {step_name}")
        print(f"  URL: {page.url}")
        print(f"  Screenshot: {screenshot_path}")
    
    async def discover(self):
        """Discover API calls using authenticated Chrome session."""
        print("=" * 80)
        print("AUTHENTICATED BHOOMI API DISCOVERY")
        print("=" * 80)
        
        target_url = "https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx"
        chrome_profile = "/Users/smrithis/Library/Application Support/Google/Chrome/Default"
        
        print(f"\nTarget URL: {target_url}")
        print(f"Chrome Profile: {chrome_profile}")
        print("Connecting to Chrome with existing session...")
        
        async with async_playwright() as p:
            # Launch Chrome with existing profile
            context = await p.chromium.launch_persistent_context(
                user_data_dir=chrome_profile,
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            # Get or create page
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = await context.new_page()
            
            # Set up request interception
            page.on('request', lambda req: asyncio.create_task(self.handle_request(req)))
            page.on('response', lambda res: asyncio.create_task(self.handle_response(res)))
            
            try:
                # Step 1: Navigate to service37
                print(f"\n1. Navigating to service37...")
                await page.goto(target_url, wait_until='networkidle')
                await self.capture_step(page, "navigate_to_service37")
                
                # Wait for page to load
                await page.wait_for_timeout(3000)
                
                # Step 2: Check for dropdowns
                print("\n2. Checking for dropdowns...")
                dropdowns = await page.query_selector_all('select')
                print(f"   Found {len(dropdowns)} dropdowns")
                
                if len(dropdowns) == 0:
                    print("   ⚠ No dropdowns found - page may not have loaded correctly")
                    await self.capture_step(page, "no_dropdowns_found")
                else:
                    # Step 3: Interact with first dropdown (likely District)
                    for i, dropdown in enumerate(dropdowns):
                        try:
                            select_id = await dropdown.get_attribute('id')
                            select_name = await dropdown.get_attribute('name')
                            print(f"   Dropdown {i+1}: {select_name or select_id}")
                            
                            # Get options
                            options = await dropdown.query_selector_all('option')
                            print(f"   Options: {len(options)}")
                            
                            if len(options) > 1:  # Skip if only default option
                                # Select second option (first non-default)
                                await dropdown.select_option(index=1)
                                await page.wait_for_timeout(2000)
                                await self.capture_step(page, f"dropdown_{i+1}_selected")
                                
                                # Check if new dropdowns appeared
                                new_dropdowns = await page.query_selector_all('select')
                                if len(new_dropdowns) > len(dropdowns):
                                    print(f"   New dropdowns appeared: {len(new_dropdowns) - len(dropdowns)}")
                                    dropdowns = new_dropdowns
                        except Exception as e:
                            print(f"   Error with dropdown {i}: {e}")
                
                # Step 4: Check for survey number input
                print("\n3. Checking for survey number input...")
                survey_inputs = await page.query_selector_all('input[name*="survey"], input[id*="survey"], input[placeholder*="survey"]')
                print(f"   Found {len(survey_inputs)} survey inputs")
                
                if survey_inputs:
                    for inp in survey_inputs:
                        try:
                            inp_id = await inp.get_attribute('id')
                            inp_name = await inp.get_attribute('name')
                            print(f"   Input: {inp_name or inp_id}")
                            
                            # Enter test survey number
                            await inp.fill("2")
                            await page.wait_for_timeout(1000)
                            await self.capture_step(page, "survey_number_entered")
                        except Exception as e:
                            print(f"   Error with survey input: {e}")
                
                # Step 5: Check for submit/fetch button
                print("\n4. Checking for submit/fetch button...")
                buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"]')
                print(f"   Found {len(buttons)} buttons")
                
                for btn in buttons:
                    try:
                        btn_text = await btn.text_content()
                        btn_type = await btn.get_attribute('type')
                        btn_id = await btn.get_attribute('id')
                        
                        print(f"   Button: {btn_type or 'button'} | {btn_id or 'N/A'} | {btn_text.strip() if btn_text else 'N/A'}")
                        
                        # Click submit/fetch buttons
                        if btn_text and ('submit' in btn_text.lower() or 'fetch' in btn_text.lower() or 'get' in btn_text.lower() or 'search' in btn_text.lower()):
                            print(f"   Clicking button: {btn_text.strip()}")
                            await btn.click()
                            await page.wait_for_timeout(5000)
                            await self.capture_step(page, f"button_clicked_{btn_text.strip().lower()}")
                            break
                    except Exception as e:
                        print(f"   Error clicking button: {e}")
                
                # Step 6: Wait for final requests
                print("\n5. Waiting for final requests...")
                await page.wait_for_timeout(5000)
                await self.capture_step(page, "final_state")
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Keep browser open for user to see
                print("\n" + "=" * 80)
                print("Browser will remain open for inspection")
                print("Press Ctrl+C to close and save results")
                print("=" * 80)
                
                try:
                    # Wait for user to close
                    await asyncio.sleep(300)  # Wait 5 minutes
                except KeyboardInterrupt:
                    pass
                
                await context.close()
        
        # Save network data
        output_file = self.output_dir / "api_calls.json"
        with open(output_file, 'w') as f:
            json.dump(self.network_data, f, indent=2)
        
        print(f"\nNetwork data saved to: {output_file}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("DISCOVERY SUMMARY")
        print("=" * 80)
        print(f"Total steps captured: {len(self.network_data['steps'])}")
        print(f"Total requests intercepted: {len(self.network_data['requests'])}")
        
        if self.network_data['requests']:
            print("\nAPI Endpoints Found:")
            for i, req in enumerate(self.network_data['requests']):
                print(f"  {i+1}. {req['method']} {req['url']}")
                if 'response' in req:
                    print(f"     Status: {req['response']['status']}")
                    content_type = req['response']['headers'].get('content-type', 'N/A')
                    print(f"     Content-Type: {content_type}")
                    
                    # Check if response is JSON
                    if 'application/json' in content_type:
                        print(f"     JSON Response: YES")
                        try:
                            json_data = json.loads(req['response']['body'])
                            print(f"     JSON Keys: {list(json_data.keys())}")
                        except:
                            pass
        else:
            print("\nNo API endpoints found")
        
        print("=" * 80)


async def main():
    """Main execution."""
    interceptor = AuthenticatedAPIInterceptor()
    await interceptor.discover()


if __name__ == "__main__":
    asyncio.run(main())
