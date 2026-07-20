"""
Portal discovery script for Bhoomi land records portal.
Maps the portal structure without making assumptions.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class PortalDiscovery:
    """Discover and map Bhoomi portal structure."""
    
    def __init__(self, output_dir: str = "logs/debug"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.discovery_data = {
            "timestamp": datetime.now().isoformat(),
            "initial_url": "https://landrecords.karnataka.gov.in",
            "redirects": [],
            "final_url": None,
            "page_title": None,
            "buttons": [],
            "links": [],
            "input_fields": [],
            "select_dropdowns": [],
            "iframes": [],
            "login_forms": [],
            "rtc_links": [],
            "service_links": []
        }
    
    async def capture_screenshot(self, page: Page, filename: str) -> str:
        """Capture screenshot."""
        filepath = self.output_dir / filename
        await page.screenshot(path=str(filepath))
        print(f"Screenshot saved: {filename}")
        return str(filepath)
    
    async def extract_buttons(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all visible buttons."""
        buttons = []
        elements = await page.query_selector_all('button, input[type="button"], input[type="submit"]')
        
        for i, element in enumerate(elements):
            try:
                text = await element.text_content()
                button_type = await element.get_attribute('type')
                button_id = await element.get_attribute('id')
                button_name = await element.get_attribute('name')
                button_value = await element.get_attribute('value')
                
                buttons.append({
                    "index": i,
                    "text": text.strip() if text else None,
                    "type": button_type,
                    "id": button_id,
                    "name": button_name,
                    "value": button_value
                })
            except Exception:
                continue
        
        return buttons
    
    async def extract_links(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all visible links."""
        links = []
        elements = await page.query_selector_all('a[href]')
        
        for i, element in enumerate(elements):
            try:
                text = await element.text_content()
                href = await element.get_attribute('href')
                link_id = await element.get_attribute('id')
                
                if href:
                    links.append({
                        "index": i,
                        "text": text.strip() if text else None,
                        "href": href,
                        "id": link_id
                    })
            except Exception:
                continue
        
        return links
    
    async def extract_input_fields(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all input fields."""
        inputs = []
        elements = await page.query_selector_all('input:not([type="button"]):not([type="submit"]):not([type="hidden"])')
        
        for i, element in enumerate(elements):
            try:
                input_type = await element.get_attribute('type')
                input_id = await element.get_attribute('id')
                input_name = await element.get_attribute('name')
                input_placeholder = await element.get_attribute('placeholder')
                
                inputs.append({
                    "index": i,
                    "type": input_type,
                    "id": input_id,
                    "name": input_name,
                    "placeholder": input_placeholder
                })
            except Exception:
                continue
        
        return inputs
    
    async def extract_select_dropdowns(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all select dropdowns."""
        selects = []
        elements = await page.query_selector_all('select')
        
        for i, element in enumerate(elements):
            try:
                select_id = await element.get_attribute('id')
                select_name = await element.get_attribute('name')
                
                # Get options
                options = []
                option_elements = await element.query_selector_all('option')
                for opt in option_elements:
                    opt_text = await opt.text_content()
                    opt_value = await opt.get_attribute('value')
                    options.append({
                        "text": opt_text.strip() if opt_text else None,
                        "value": opt_value
                    })
                
                selects.append({
                    "index": i,
                    "id": select_id,
                    "name": select_name,
                    "options": options
                })
            except Exception:
                continue
        
        return selects
    
    async def extract_iframes(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all iframe sources."""
        iframes = []
        elements = await page.query_selector_all('iframe')
        
        for i, element in enumerate(elements):
            try:
                src = await element.get_attribute('src')
                iframe_id = await element.get_attribute('id')
                
                iframes.append({
                    "index": i,
                    "src": src,
                    "id": iframe_id
                })
            except Exception:
                continue
        
        return iframes
    
    def detect_login_forms(self, inputs: List[Dict[str, Any]], buttons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect potential login forms."""
        login_forms = []
        
        # Look for password fields
        password_inputs = [inp for inp in inputs if inp.get('type') == 'password']
        
        for pwd_input in password_inputs:
            login_forms.append({
                "password_field": pwd_input,
                "related_inputs": [inp for inp in inputs if inp != pwd_input],
                "submit_buttons": [btn for btn in buttons if btn.get('type') in ['submit', 'button']]
            })
        
        return login_forms
    
    def detect_rtc_links(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect RTC-related links."""
        rtc_keywords = ['rtc', 'pahani', 'record of rights', 'view rtc', 'rtc form']
        rtc_links = []
        
        for link in links:
            text = link.get('text', '').lower() if link.get('text') else ''
            href = link.get('href', '').lower() if link.get('href') else ''
            
            if any(keyword in text or keyword in href for keyword in rtc_keywords):
                rtc_links.append(link)
        
        return rtc_links
    
    def detect_service_links(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect service-related links."""
        service_keywords = ['mutation', 'khata', 'survey', 'akarband', 'chavadi', 'ec', 'encumbrance']
        service_links = []
        
        for link in links:
            text = link.get('text', '').lower() if link.get('text') else ''
            href = link.get('href', '').lower() if link.get('href') else ''
            
            if any(keyword in text or keyword in href for keyword in service_keywords):
                service_links.append(link)
        
        return service_links
    
    async def discover(self):
        """Discover portal structure."""
        print("=" * 80)
        print("BHOOMI PORTAL DISCOVERY")
        print("=" * 80)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Capture landing screenshot
                print(f"\nNavigating to: {self.discovery_data['initial_url']}")
                await self.capture_screenshot(page, "01_landing.png")
                
                # Navigate and track redirects
                response = await page.goto(self.discovery_data['initial_url'], wait_until='networkidle')
                
                # Capture URL after navigation
                current_url = page.url
                self.discovery_data['final_url'] = current_url
                self.discovery_data['redirects'].append({
                    "from": self.discovery_data['initial_url'],
                    "to": current_url,
                    "status": response.status if response else None
                })
                
                print(f"Final URL: {current_url}")
                
                # Capture screenshot after redirect
                await self.capture_screenshot(page, "02_after_redirect.png")
                
                # Get page title
                title = await page.title()
                self.discovery_data['page_title'] = title
                print(f"Page Title: {title}")
                
                # Extract all elements
                print("\nExtracting page elements...")
                
                self.discovery_data['buttons'] = await self.extract_buttons(page)
                print(f"Found {len(self.discovery_data['buttons'])} buttons")
                
                self.discovery_data['links'] = await self.extract_links(page)
                print(f"Found {len(self.discovery_data['links'])} links")
                
                self.discovery_data['input_fields'] = await self.extract_input_fields(page)
                print(f"Found {len(self.discovery_data['input_fields'])} input fields")
                
                self.discovery_data['select_dropdowns'] = await self.extract_select_dropdowns(page)
                print(f"Found {len(self.discovery_data['select_dropdowns'])} select dropdowns")
                
                self.discovery_data['iframes'] = await self.extract_iframes(page)
                print(f"Found {len(self.discovery_data['iframes'])} iframes")
                
                # Detect specific elements
                self.discovery_data['login_forms'] = self.detect_login_forms(
                    self.discovery_data['input_fields'],
                    self.discovery_data['buttons']
                )
                
                self.discovery_data['rtc_links'] = self.detect_rtc_links(self.discovery_data['links'])
                self.discovery_data['service_links'] = self.detect_service_links(self.discovery_data['links'])
                
                # Capture final screenshot
                await self.capture_screenshot(page, "03_final_page.png")
                
                # Save discovery data
                output_file = self.output_dir / "discovery.json"
                with open(output_file, 'w') as f:
                    json.dump(self.discovery_data, f, indent=2)
                print(f"\nDiscovery data saved to: {output_file}")
                
                # Print summary
                print("\n" + "=" * 80)
                print("DISCOVERY SUMMARY")
                print("=" * 80)
                
                print(f"\nLogin Forms Detected: {len(self.discovery_data['login_forms'])}")
                for form in self.discovery_data['login_forms']:
                    print(f"  - Password field: {form['password_field'].get('name') or form['password_field'].get('id')}")
                
                print(f"\nRTC Links Detected: {len(self.discovery_data['rtc_links'])}")
                for link in self.discovery_data['rtc_links'][:10]:  # Show first 10
                    print(f"  - {link.get('text')}: {link.get('href')}")
                
                print(f"\nService Links Detected: {len(self.discovery_data['service_links'])}")
                for link in self.discovery_data['service_links'][:10]:  # Show first 10
                    print(f"  - {link.get('text')}: {link.get('href')}")
                
                print(f"\nSelect Dropdowns: {len(self.discovery_data['select_dropdowns'])}")
                for select in self.discovery_data['select_dropdowns']:
                    print(f"  - {select.get('name') or select.get('id')}: {len(select.get('options', []))} options")
                
                print("\n" + "=" * 80)
                
            except Exception as e:
                print(f"\nError during discovery: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()


async def main():
    """Main execution."""
    discovery = PortalDiscovery()
    await discovery.discover()


if __name__ == "__main__":
    asyncio.run(main())
