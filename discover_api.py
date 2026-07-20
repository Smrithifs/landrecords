"""
Intercept network requests from Bhoomi service37 to find API endpoints.
Logs all fetch/XHR requests to discover potential direct API access.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


class APIInterceptor:
    """Intercept network requests to discover API endpoints."""
    
    def __init__(self, output_dir: str = "logs/debug"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.network_data = {
            "timestamp": datetime.now().isoformat(),
            "url": "https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx",
            "requests": []
        }
    
    async def handle_request(self, request):
        """Handle incoming requests."""
        resource_type = request.resource_type
        url = request.url
        
        # Only log fetch/XHR requests
        if resource_type in ['fetch', 'xhr']:
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
        
        # Only log fetch/XHR responses
        if resource_type in ['fetch', 'xhr']:
            try:
                # Try to get response body
                body = await response.text()
                response_data = {
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body[:10000]  # Limit body size
                }
                
                # Update corresponding request with response data
                for req in self.network_data["requests"]:
                    if req["url"] == url:
                        req["response"] = response_data
                        break
                
                print(f"  [RESPONSE] {response.status} {url}")
            except Exception as e:
                print(f"  [ERROR] Could not get response body for {url}: {e}")
    
    async def discover(self):
        """Discover API endpoints by intercepting network traffic."""
        print("=" * 80)
        print("BHOOMI SERVICE37 API DISCOVERY")
        print("=" * 80)
        
        target_url = "https://landrecords.karnataka.gov.in/service37/PreviewRTC.aspx"
        print(f"\nTarget URL: {target_url}")
        print("Intercepting network requests...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Set up request interception
            page.on('request', lambda req: asyncio.create_task(self.handle_request(req)))
            page.on('response', lambda res: asyncio.create_task(self.handle_response(res)))
            
            try:
                print(f"\n1. Navigating to service37...")
                await page.goto(target_url, wait_until='networkidle')
                
                # Wait a bit to capture any delayed requests
                print("2. Waiting for delayed requests...")
                await page.wait_for_timeout(5000)
                
                # Try to interact with the page to trigger API calls
                print("3. Checking for dropdowns and inputs...")
                
                # Check for dropdowns
                dropdowns = await page.query_selector_all('select')
                print(f"   Found {len(dropdowns)} dropdowns")
                
                # Try to interact with dropdowns to trigger API calls
                for i, dropdown in enumerate(dropdowns):
                    try:
                        select_id = await dropdown.get_attribute('id')
                        select_name = await dropdown.get_attribute('name')
                        print(f"   Dropdown {i+1}: {select_name or select_id}")
                        
                        # Try to select first option to trigger potential API calls
                        options = await dropdown.query_selector_all('option')
                        if options:
                            await dropdown.select_option(index=0)
                            await page.wait_for_timeout(1000)
                    except Exception as e:
                        print(f"   Error with dropdown {i}: {e}")
                
                # Check for buttons
                print("4. Checking for buttons...")
                buttons = await page.query_selector_all('button, input[type="submit"], input[type="button"]')
                print(f"   Found {len(buttons)} buttons")
                
                # Try to click submit button to trigger API calls
                for btn in buttons:
                    try:
                        btn_text = await btn.text_content()
                        btn_type = await btn.get_attribute('type')
                        if btn_text and ('submit' in btn_text.lower() or 'search' in btn_text.lower() or 'get' in btn_text.lower()):
                            print(f"   Clicking button: {btn_text.strip()}")
                            await btn.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception as e:
                        print(f"   Error clicking button: {e}")
                
                # Wait for any final requests
                print("5. Waiting for final requests...")
                await page.wait_for_timeout(3000)
                
                # Capture screenshot
                screenshot_path = self.output_dir / "api_discovery_screenshot.png"
                await page.screenshot(path=str(screenshot_path))
                print(f"   Screenshot saved: {screenshot_path}")
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()
        
        # Save network data
        output_file = self.output_dir / "api_discovery.json"
        with open(output_file, 'w') as f:
            json.dump(self.network_data, f, indent=2)
        
        print(f"\nNetwork data saved to: {output_file}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("DISCOVERY SUMMARY")
        print("=" * 80)
        print(f"Total requests intercepted: {len(self.network_data['requests'])}")
        
        if self.network_data['requests']:
            print("\nAPI Endpoints Found:")
            for i, req in enumerate(self.network_data['requests']):
                print(f"  {i+1}. {req['method']} {req['url']}")
                if 'response' in req:
                    print(f"     Status: {req['response']['status']}")
                    print(f"     Content-Type: {req['response']['headers'].get('content-type', 'N/A')}")
        else:
            print("\nNo API endpoints found - page may not use background API calls")
        
        print("=" * 80)


async def main():
    """Main execution."""
    interceptor = APIInterceptor()
    await interceptor.discover()


if __name__ == "__main__":
    asyncio.run(main())
