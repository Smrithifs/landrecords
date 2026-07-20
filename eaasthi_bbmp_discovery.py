"""
e-Aasthi BBMP Discovery Script
Investigate how BBMP properties are represented in e-Aasthi portal.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import datetime


class EAAsthiBBMPDiscovery:
    """Discover BBMP property representation in e-Aasthi."""
    
    def __init__(self):
        self.base_url = "https://eaasthi.karnataka.gov.in"
        self.debug_dir = Path("logs/debug")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.debug_dir / "eaasthi_bbmp_discovery.json"
        
        self.captured_requests = []
        self.captured_responses = []
        self.findings = {
            "timestamp": datetime.now().isoformat(),
            "investigation_questions": {
                "1. Is BBMP included in e-Aasthi search?": "PENDING",
                "2. Can ePID/PID be searched for BBMP properties?": "PENDING",
                "3. Which ULB corresponds to BBMP properties?": "PENDING",
                "4. Path from Bhoomi RTC to ePID/PID/Assessment Number": "PENDING"
            },
            "network_requests": [],
            "dropdown_options": {},
            "search_fields": {},
            "api_endpoints": {},
            "notes": []
        }
    
    async def capture_network(self, page):
        """Capture all network requests and responses."""
        
        def handle_request(request):
            url = request.url
            method = request.method
            self.captured_requests.append({
                "url": url,
                "method": method,
                "headers": dict(request.headers),
                "timestamp": datetime.now().isoformat()
            })
            print(f"[REQUEST] {method} {url}")
        
        def handle_response(response):
            url = response.url
            status = response.status
            content_type = response.headers.get('content-type', '')
            
            # Only capture JSON responses
            if 'application/json' in content_type:
                try:
                    body = response.body()
                    self.captured_responses.append({
                        "url": url,
                        "status": status,
                        "content_type": content_type,
                        "body": body.decode('utf-8', errors='ignore'),
                        "timestamp": datetime.now().isoformat()
                    })
                    print(f"[RESPONSE] {status} {url} ({content_type})")
                except Exception as e:
                    print(f"[RESPONSE ERROR] {url}: {e}")
        
        page.on('request', handle_request)
        page.on('response', handle_response)
    
    async def investigate_district_dropdown(self, page):
        """Investigate district dropdown options."""
        print("\n=== INVESTIGATING DISTRICT DROPDOWN ===")
        
        try:
            # Wait for district dropdown
            await page.wait_for_selector('select[name*="district"], select[id*="district"], select[name*="District"]', timeout=10000)
            
            # Get all options
            districts = await page.eval_on_selector_all(
                'select[name*="district"], select[id*="district"], select[name*="District"] option',
                'options => options.map(opt => ({value: opt.value, text: opt.text}))'
            )
            
            self.findings["dropdown_options"]["districts"] = districts
            print(f"Found {len(districts)} district options")
            
            # Check for BBMP/Bengaluru
            bbmp_found = any('BBMP' in str(d).upper() or 'BENGALURU' in str(d).upper() for d in districts)
            self.findings["investigation_questions"]["1. Is BBMP included in e-Aasthi search?"] = "YES" if bbmp_found else "NO"
            print(f"BBMP/Bengaluru in districts: {bbmp_found}")
            
        except Exception as e:
            print(f"Error investigating district dropdown: {e}")
            self.findings["notes"].append(f"District dropdown error: {e}")
    
    async def investigate_ulb_dropdown(self, page):
        """Investigate ULB (Urban Local Body) dropdown options."""
        print("\n=== INVESTIGATING ULB DROPDOWN ===")
        
        try:
            # Try different ULB dropdown selectors
            ulb_selectors = [
                'select[name*="ulb"], select[id*="ulb"]',
                'select[name*="ULB"], select[id*="ULB"]',
                'select[name*="municipality"], select[id*="municipality"]',
                'select[name*="corporation"], select[id*="corporation"]'
            ]
            
            for selector in ulb_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    ulbs = await page.eval_on_selector_all(
                        f'{selector} option',
                        'options => options.map(opt => ({value: opt.value, text: opt.text}))'
                    )
                    
                    self.findings["dropdown_options"]["ulbs"] = ulbs
                    print(f"Found {len(ulbs)} ULB options using selector: {selector}")
                    
                    # Check for BBMP
                    bbmp_ulbs = [ulb for ulb in ulbs if 'BBMP' in str(ulb).upper() or 'BENGALURU' in str(ulb).upper()]
                    if bbmp_ulbs:
                        self.findings["investigation_questions"]["3. Which ULB corresponds to BBMP properties?"] = bbmp_ulbs
                        print(f"BBMP ULBs found: {bbmp_ulbs}")
                    
                    break
                except:
                    continue
            else:
                print("No ULB dropdown found")
                self.findings["notes"].append("No ULB dropdown found")
                
        except Exception as e:
            print(f"Error investigating ULB dropdown: {e}")
            self.findings["notes"].append(f"ULB dropdown error: {e}")
    
    async def investigate_search_fields(self, page):
        """Investigate available search fields."""
        print("\n=== INVESTIGATING SEARCH FIELDS ===")
        
        try:
            # Get all input fields
            inputs = await page.eval_on_selector_all(
                'input, select',
                'elements => elements.map(el => ({tag: el.tagName, type: el.type, name: el.name, id: el.id, placeholder: el.placeholder}))'
            )
            
            self.findings["search_fields"] = inputs
            print(f"Found {len(inputs)} input fields")
            
            # Check for ePID/PID fields
            epid_fields = [inp for inp in inputs if 'epid' in str(inp).lower() or 'pid' in str(inp).lower()]
            if epid_fields:
                self.findings["investigation_questions"]["2. Can ePID/PID be searched for BBMP properties?"] = "YES - Fields found"
                print(f"ePID/PID fields found: {epid_fields}")
            else:
                self.findings["investigation_questions"]["2. Can ePID/PID be searched for BBMP properties?"] = "NO - No fields found"
                
        except Exception as e:
            print(f"Error investigating search fields: {e}")
            self.findings["notes"].append(f"Search fields error: {e}")
    
    async def run_discovery(self):
        """Run the discovery investigation."""
        print("=== e-Aasthi BBMP Discovery ===")
        print("Opening browser for manual investigation...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Capture network requests
            await self.capture_network(page)
            
            # Navigate to e-Aasthi
            print(f"\nNavigating to {self.base_url}...")
            await page.goto(self.base_url)
            await page.wait_for_load_state("networkidle")
            
            print("\n=== MANUAL INVESTIGATION MODE ===")
            print("1. Investigate the portal structure")
            print("2. Check dropdowns for BBMP/Bengaluru")
            print("3. Try searching with different parameters")
            print("4. Check if ePID/PID search is available")
            print("5. Note the ULB options for Bengaluru")
            print("\n=== PRESS ENTER WHEN DONE WITH MANUAL INVESTIGATION ===")
            input()
            
            # Run automated investigations
            await self.investigate_district_dropdown(page)
            await self.investigate_ulb_dropdown(page)
            await self.investigate_search_fields(page)
            
            # Save captured network data
            self.findings["network_requests"] = self.captured_requests
            self.findings["api_endpoints"] = {
                "requests": len(self.captured_requests),
                "responses": len(self.captured_responses),
                "sample_endpoints": list(set([req["url"].split('?')[0] for req in self.captured_requests[:20]]))
            }
            
            # Save findings
            print(f"\n=== SAVING FINDINGS TO {self.output_file} ===")
            with open(self.output_file, 'w') as f:
                json.dump(self.findings, f, indent=2)
            
            print(f"Discovery complete. Findings saved to {self.output_file}")
            print(f"\n=== SUMMARY ===")
            for question, answer in self.findings["investigation_questions"].items():
                print(f"{question}: {answer}")
            
            await browser.close()


async def main():
    discovery = EAAsthiBBMPDiscovery()
    await discovery.run_discovery()


if __name__ == "__main__":
    asyncio.run(main())
