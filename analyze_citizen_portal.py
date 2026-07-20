"""
Citizen Portal and Guest User Service Analysis Script.
Analyzes authentication requirements and RTC access capabilities.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class CitizenPortalAnalysis:
    """Analyze Citizen Portal and Guest User Service for RTC access."""
    
    def __init__(self, output_dir: str = "logs/debug"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_data = {
            "timestamp": datetime.now().isoformat(),
            "urls_tested": [],
            "results": {}
        }
    
    async def capture_screenshot(self, page: Page, filename: str) -> str:
        """Capture screenshot."""
        filepath = self.output_dir / filename
        await page.screenshot(path=str(filepath))
        return str(filepath)
    
    def detect_login_requirements(self, inputs: List[Dict[str, Any]], buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect login requirements."""
        detection = {
            "has_login": False,
            "has_password": False,
            "has_username": False,
            "has_mobile": False,
            "has_email": False,
            "has_submit_button": False,
            "login_fields": []
        }
        
        # Check for password fields
        password_inputs = [inp for inp in inputs if inp.get('type') == 'password']
        if password_inputs:
            detection['has_password'] = True
            detection['has_login'] = True
            detection['login_fields'].extend(password_inputs)
        
        # Check for username/email/mobile fields
        for inp in inputs:
            inp_name = (inp.get('name') or inp.get('id') or '').lower()
            inp_placeholder = (inp.get('placeholder') or '').lower()
            
            if 'user' in inp_name or 'user' in inp_placeholder:
                detection['has_username'] = True
                detection['has_login'] = True
                detection['login_fields'].append(inp)
            
            if 'mobile' in inp_name or 'mobile' in inp_placeholder or 'phone' in inp_name:
                detection['has_mobile'] = True
                detection['has_login'] = True
                detection['login_fields'].append(inp)
            
            if 'email' in inp_name or 'email' in inp_placeholder:
                detection['has_email'] = True
                detection['has_login'] = True
                detection['login_fields'].append(inp)
        
        # Check for submit buttons
        submit_buttons = [btn for btn in buttons if btn.get('type') in ['submit', 'button']]
        if submit_buttons:
            detection['has_submit_button'] = True
        
        return detection
    
    def detect_otp_requirements(self, inputs: List[Dict[str, Any]], buttons: List[Dict[str, Any]], page_text: str) -> Dict[str, Any]:
        """Detect OTP requirements."""
        detection = {
            "has_otp": False,
            "has_otp_input": False,
            "has_send_otp_button": False,
            "otp_keywords_found": []
        }
        
        otp_keywords = ['otp', 'one time password', 'verification code', 'verify']
        
        # Check page text for OTP keywords
        page_text_lower = page_text.lower()
        for keyword in otp_keywords:
            if keyword in page_text_lower:
                detection['otp_keywords_found'].append(keyword)
        
        if detection['otp_keywords_found']:
            detection['has_otp'] = True
        
        # Check for OTP input fields
        for inp in inputs:
            inp_name = (inp.get('name') or inp.get('id') or '').lower()
            inp_placeholder = (inp.get('placeholder') or '').lower()
            
            if 'otp' in inp_name or 'otp' in inp_placeholder or 'verify' in inp_name:
                detection['has_otp_input'] = True
                detection['has_otp'] = True
        
        # Check for "Send OTP" buttons
        for btn in buttons:
            btn_text = (btn.get('text') or btn.get('value') or '').lower()
            if 'send' in btn_text and 'otp' in btn_text:
                detection['has_send_otp_button'] = True
                detection['has_otp'] = True
        
        return detection
    
    def detect_aadhaar_requirements(self, inputs: List[Dict[str, Any]], page_text: str) -> Dict[str, Any]:
        """Detect Aadhaar requirements."""
        detection = {
            "has_aadhaar": False,
            "has_aadhaar_input": False,
            "aadhaar_keywords_found": []
        }
        
        aadhaar_keywords = ['aadhaar', 'aadhar', 'uid', 'unique identification']
        
        # Check page text for Aadhaar keywords
        page_text_lower = page_text.lower()
        for keyword in aadhaar_keywords:
            if keyword in page_text_lower:
                detection['aadhaar_keywords_found'].append(keyword)
        
        if detection['aadhaar_keywords_found']:
            detection['has_aadhaar'] = True
        
        # Check for Aadhaar input fields
        for inp in inputs:
            inp_name = (inp.get('name') or inp.get('id') or '').lower()
            inp_placeholder = (inp.get('placeholder') or '').lower()
            
            if 'aadhaar' in inp_name or 'aadhar' in inp_name or 'uid' in inp_name:
                detection['has_aadhaar_input'] = True
                detection['has_aadhaar'] = True
        
        return detection
    
    def detect_rtc_search_forms(self, inputs: List[Dict[str, Any]], selects: List[Dict[str, Any]], page_text: str) -> Dict[str, Any]:
        """Detect RTC search forms."""
        detection = {
            "has_rtc_search": False,
            "has_survey_input": False,
            "has_district_select": False,
            "has_taluk_select": False,
            "has_hobli_select": False,
            "has_village_select": False,
            "rtc_keywords_found": []
        }
        
        rtc_keywords = ['rtc', 'pahani', 'record of rights', 'survey number', 'survey no', 'khata']
        
        # Check page text for RTC keywords
        page_text_lower = page_text.lower()
        for keyword in rtc_keywords:
            if keyword in page_text_lower:
                detection['rtc_keywords_found'].append(keyword)
        
        if detection['rtc_keywords_found']:
            detection['has_rtc_search'] = True
        
        # Check for survey number input
        for inp in inputs:
            inp_name = (inp.get('name') or inp.get('id') or '').lower()
            inp_placeholder = (inp.get('placeholder') or '').lower()
            
            if 'survey' in inp_name or 'survey' in inp_placeholder:
                detection['has_survey_input'] = True
                detection['has_rtc_search'] = True
        
        # Check for location dropdowns
        for select in selects:
            select_name = (select.get('name') or select.get('id') or '').lower()
            
            if 'district' in select_name:
                detection['has_district_select'] = True
                detection['has_rtc_search'] = True
            if 'taluk' in select_name:
                detection['has_taluk_select'] = True
                detection['has_rtc_search'] = True
            if 'hobli' in select_name:
                detection['has_hobli_select'] = True
                detection['has_rtc_search'] = True
            if 'village' in select_name:
                detection['has_village_select'] = True
                detection['has_rtc_search'] = True
        
        return detection
    
    async def extract_elements(self, page: Page) -> Dict[str, Any]:
        """Extract page elements."""
        elements = {
            "inputs": [],
            "selects": [],
            "buttons": [],
            "page_text": ""
        }
        
        # Extract inputs
        input_elements = await page.query_selector_all('input:not([type="hidden"])')
        for i, element in enumerate(input_elements):
            try:
                input_type = await element.get_attribute('type')
                input_id = await element.get_attribute('id')
                input_name = await element.get_attribute('name')
                input_placeholder = await element.get_attribute('placeholder')
                
                elements['inputs'].append({
                    "index": i,
                    "type": input_type,
                    "id": input_id,
                    "name": input_name,
                    "placeholder": input_placeholder
                })
            except Exception:
                continue
        
        # Extract selects
        select_elements = await page.query_selector_all('select')
        for i, element in enumerate(select_elements):
            try:
                select_id = await element.get_attribute('id')
                select_name = await element.get_attribute('name')
                
                elements['selects'].append({
                    "index": i,
                    "id": select_id,
                    "name": select_name
                })
            except Exception:
                continue
        
        # Extract buttons
        button_elements = await page.query_selector_all('button, input[type="button"], input[type="submit"]')
        for i, element in enumerate(button_elements):
            try:
                text = await element.text_content()
                button_type = await element.get_attribute('type')
                button_id = await element.get_attribute('id')
                button_name = await element.get_attribute('name')
                button_value = await element.get_attribute('value')
                
                elements['buttons'].append({
                    "index": i,
                    "text": text.strip() if text else None,
                    "type": button_type,
                    "id": button_id,
                    "name": button_name,
                    "value": button_value
                })
            except Exception:
                continue
        
        # Extract page text
        elements['page_text'] = await page.inner_text('body')
        
        return elements
    
    async def analyze_url(self, url: str, context: BrowserContext) -> Dict[str, Any]:
        """Analyze a single URL."""
        print(f"\n{'=' * 80}")
        print(f"Analyzing: {url}")
        print('=' * 80)
        
        result = {
            "url": url,
            "redirects": [],
            "final_url": None,
            "page_title": None,
            "screenshots": [],
            "login_requirements": {},
            "otp_requirements": {},
            "aadhaar_requirements": {},
            "rtc_search_forms": {},
            "api_calls": [],
            "can_access_rtc_without_auth": False
        }
        
        page = await context.new_page()
        
        try:
            # Capture initial screenshot
            screenshot_name = f"citizen_portal_{url.split('/')[-2]}_initial.png"
            await self.capture_screenshot(page, screenshot_name)
            result['screenshots'].append(screenshot_name)
            
            # Navigate and track redirects
            response = await page.goto(url, wait_until='networkidle')
            
            # Track URL changes
            final_url = page.url
            result['final_url'] = final_url
            
            if final_url != url:
                result['redirects'].append({
                    "from": url,
                    "to": final_url,
                    "status": response.status if response else None
                })
            
            # Get page title
            title = await page.title()
            result['page_title'] = title
            print(f"Final URL: {final_url}")
            print(f"Page Title: {title}")
            
            # Capture screenshot after navigation
            screenshot_name = f"citizen_portal_{url.split('/')[-2]}_after_nav.png"
            await self.capture_screenshot(page, screenshot_name)
            result['screenshots'].append(screenshot_name)
            
            # Extract elements
            elements = await self.extract_elements(page)
            
            # Detect requirements
            result['login_requirements'] = self.detect_login_requirements(
                elements['inputs'], elements['buttons']
            )
            
            result['otp_requirements'] = self.detect_otp_requirements(
                elements['inputs'], elements['buttons'], elements['page_text']
            )
            
            result['aadhaar_requirements'] = self.detect_aadhaar_requirements(
                elements['inputs'], elements['page_text']
            )
            
            result['rtc_search_forms'] = self.detect_rtc_search_forms(
                elements['inputs'], elements['selects'], elements['page_text']
            )
            
            # Determine if RTC can be accessed without authentication
            if (result['rtc_search_forms']['has_rtc_search'] and 
                not result['login_requirements']['has_login'] and
                not result['otp_requirements']['has_otp'] and
                not result['aadhaar_requirements']['has_aadhaar']):
                result['can_access_rtc_without_auth'] = True
            
            # Print summary
            print(f"\nLogin Required: {result['login_requirements']['has_login']}")
            print(f"OTP Required: {result['otp_requirements']['has_otp']}")
            print(f"Aadhaar Required: {result['aadhaar_requirements']['has_aadhaar']}")
            print(f"RTC Search Form: {result['rtc_search_forms']['has_rtc_search']}")
            print(f"Can Access RTC Without Auth: {result['can_access_rtc_without_auth']}")
            
        except Exception as e:
            print(f"Error analyzing {url}: {e}")
            result['error'] = str(e)
        finally:
            await page.close()
        
        return result
    
    async def analyze(self):
        """Analyze Citizen Portal and Guest User Service."""
        print("=" * 80)
        print("CITIZEN PORTAL AND GUEST USER SERVICE ANALYSIS")
        print("=" * 80)
        
        urls_to_test = [
            "https://landrecords.karnataka.gov.in/citizenportal",
            "https://landrecords.karnataka.gov.in/Service38/GuestUserInfo.aspx"
        ]
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            
            try:
                for url in urls_to_test:
                    result = await self.analyze_url(url, context)
                    self.analysis_data['urls_tested'].append(url)
                    self.analysis_data['results'][url] = result
                
                # Save analysis data
                output_file = self.output_dir / "citizen_portal_analysis.json"
                with open(output_file, 'w') as f:
                    json.dump(self.analysis_data, f, indent=2)
                print(f"\nAnalysis data saved to: {output_file}")
                
                # Print final summary
                print("\n" + "=" * 80)
                print("FINAL SUMMARY")
                print("=" * 80)
                
                for url, result in self.analysis_data['results'].items():
                    print(f"\n{url}:")
                    print(f"  Can Access RTC Without Auth: {result['can_access_rtc_without_auth']}")
                    print(f"  Login Required: {result['login_requirements']['has_login']}")
                    print(f"  OTP Required: {result['otp_requirements']['has_otp']}")
                    print(f"  Aadhaar Required: {result['aadhaar_requirements']['has_aadhaar']}")
                    print(f"  RTC Search Form: {result['rtc_search_forms']['has_rtc_search']}")
                
                print("\n" + "=" * 80)
                
            except Exception as e:
                print(f"\nError during analysis: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()


async def main():
    """Main execution."""
    analysis = CitizenPortalAnalysis()
    await analysis.analyze()


if __name__ == "__main__":
    asyncio.run(main())
