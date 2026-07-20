"""
Test Bhoomi authentication with valid credentials.
Tests login process and captures authentication state.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class BhoomiAuthTest:
    """Test Bhoomi authentication process."""
    
    def __init__(self, output_dir: str = "logs/debug"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.test_data = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "authentication",
            "credentials_used": {},
            "login_page": {},
            "filled_form": {},
            "post_login": {},
            "session_cookies": [],
            "authentication_result": False,
            "error": None
        }
    
    async def capture_screenshot(self, page: Page, filename: str) -> str:
        """Capture screenshot."""
        filepath = self.output_dir / filename
        await page.screenshot(path=str(filepath))
        return str(filepath)
    
    async def test_citizen_portal_login(self, username: str, password: str) -> Dict[str, Any]:
        """Test citizen portal login with username/password."""
        print("=" * 80)
        print("TESTING CITIZEN PORTAL LOGIN")
        print("=" * 80)
        
        self.test_data["credentials_used"] = {
            "method": "citizen_portal",
            "username": username,
            "password": "***"  # Mask password in logs
        }
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Capture initial state
                print(f"\n1. Navigating to citizen portal...")
                citizen_portal_url = "https://landrecords.karnataka.gov.in/citizenportal"
                await page.goto(citizen_portal_url, wait_until='networkidle')
                
                # Capture login page screenshot
                login_screenshot = await self.capture_screenshot(page, "auth_01_login_page.png")
                self.test_data["login_page"] = {
                    "url": page.url,
                    "title": await page.title(),
                    "screenshot": login_screenshot
                }
                print(f"   - URL: {page.url}")
                print(f"   - Title: {await page.title()}")
                print(f"   - Screenshot: {login_screenshot}")
                
                # Fill login form
                print(f"\n2. Filling login form...")
                username_input = await page.wait_for_selector('#txtUname', timeout=10000)
                password_input = await page.wait_for_selector('#txtPwd', timeout=10000)
                
                await username_input.fill(username)
                await password_input.fill(password)
                
                # Capture filled form screenshot
                filled_screenshot = await self.capture_screenshot(page, "auth_02_filled_form.png")
                self.test_data["filled_form"] = {
                    "screenshot": filled_screenshot,
                    "username_filled": True,
                    "password_filled": True
                }
                print(f"   - Username filled: {username}")
                print(f"   - Password filled: ***")
                print(f"   - Screenshot: {filled_screenshot}")
                
                # Submit login
                print(f"\n3. Submitting login form...")
                submit_button = await page.query_selector('input[type="submit"], button[type="submit"]')
                if submit_button:
                    await submit_button.click()
                    await page.wait_for_timeout(5000)  # Wait for redirect
                
                # Capture post-login state
                print(f"\n4. Capturing post-login state...")
                post_login_screenshot = await self.capture_screenshot(page, "auth_03_post_login.png")
                
                # Get session cookies
                cookies = await context.cookies()
                self.test_data["session_cookies"] = cookies
                
                current_url = page.url
                current_title = await page.title()
                
                self.test_data["post_login"] = {
                    "url": current_url,
                    "title": current_title,
                    "screenshot": post_login_screenshot
                }
                
                print(f"   - Current URL: {current_url}")
                print(f"   - Page Title: {current_title}")
                print(f"   - Screenshot: {post_login_screenshot}")
                print(f"   - Session Cookies: {len(cookies)} cookies created")
                
                # Determine authentication success
                if current_url != citizen_portal_url:
                    self.test_data["authentication_result"] = True
                    print(f"\n✓ AUTHENTICATION SUCCESSFUL")
                    print(f"  - Redirect detected: {citizen_portal_url} → {current_url}")
                else:
                    self.test_data["authentication_result"] = False
                    print(f"\n✗ AUTHENTICATION FAILED")
                    print(f"  - No redirect detected, still on login page")
                
                # Print session cookie details
                print(f"\n5. Session Cookies:")
                for cookie in cookies:
                    print(f"   - {cookie['name']}: {cookie['value'][:20]}..." if len(cookie['value']) > 20 else f"   - {cookie['name']}: {cookie['value']}")
                
            except Exception as e:
                self.test_data["error"] = str(e)
                self.test_data["authentication_result"] = False
                print(f"\n✗ ERROR: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()
        
        return self.test_data
    
    def generate_markdown_report(self) -> str:
        """Generate markdown authentication test report."""
        report = f"""# Bhoomi Authentication Test Report

**Test Date:** {self.test_data['timestamp']}
**Test Type:** {self.test_data['test_type']}

---

## Test Configuration

**Authentication Method:** {self.test_data['credentials_used'].get('method', 'N/A')}
**Username:** {self.test_data['credentials_used'].get('username', 'N/A')}
**Password:** {self.test_data['credentials_used'].get('password', 'N/A')}

---

## Test Results

**Authentication Status:** {'✓ SUCCESS' if self.test_data['authentication_result'] else '✗ FAILED'}

---

## Detailed Results

### 1. Login Page

**URL:** {self.test_data['login_page'].get('url', 'N/A')}
**Title:** {self.test_data['login_page'].get('title', 'N/A')}
**Screenshot:** `{self.test_data['login_page'].get('screenshot', 'N/A')}`

### 2. Filled Login Form

**Username Filled:** {self.test_data['filled_form'].get('username_filled', False)}
**Password Filled:** {self.test_data['filled_form'].get('password_filled', False)}
**Screenshot:** `{self.test_data['filled_form'].get('screenshot', 'N/A')}`

### 3. Post-Login State

**Current URL:** {self.test_data['post_login'].get('url', 'N/A')}
**Page Title:** {self.test_data['post_login'].get('title', 'N/A')}
**Screenshot:** `{self.test_data['post_login'].get('screenshot', 'N/A')}`

### 4. Session Cookies

**Number of Cookies:** {len(self.test_data['session_cookies'])}

"""
        
        if self.test_data['session_cookies']:
            report += "| Cookie Name | Value | Domain | Path | Secure | HttpOnly |\n"
            report += "|-------------|-------|--------|------|--------|----------|\n"
            for cookie in self.test_data['session_cookies']:
                value_display = cookie['value'][:20] + "..." if len(cookie['value']) > 20 else cookie['value']
                report += f"| {cookie['name']} | {value_display} | {cookie.get('domain', 'N/A')} | {cookie.get('path', 'N/A')} | {cookie.get('secure', False)} | {cookie.get('httpOnly', False)} |\n"
        else:
            report += "No session cookies created.\n"
        
        if self.test_data.get('error'):
            report += f"\n### 5. Error\n\n```\n{self.test_data['error']}\n```\n"
        
        report += f"""

---

## Screenshots

All screenshots saved to: `{self.output_dir}`

1. Login Page: `auth_01_login_page.png`
2. Filled Form: `auth_02_filled_form.png`
3. Post-Login: `auth_03_post_login.png`

---

## Conclusion

"""
        
        if self.test_data['authentication_result']:
            report += "✓ **Authentication Test PASSED**\n\nThe Bhoomi citizen portal authentication is working correctly. Session cookies were created and the user was successfully redirected to the authenticated area."
        else:
            report += "✗ **Authentication Test FAILED**\n\nThe Bhoomi citizen portal authentication failed. This could be due to incorrect credentials, CAPTCHA requirements, or other authentication barriers."
        
        return report


async def main():
    """Main execution."""
    print("=" * 80)
    print("BHOOMI AUTHENTICATION TEST")
    print("=" * 80)
    
    # Get credentials from environment variables
    username = os.getenv("BHOOMI_USERNAME", "")
    password = os.getenv("BHOOMI_PASSWORD", "")
    
    if not username or not password:
        print("\n✗ ERROR: BHOOMI_USERNAME and BHOOMI_PASSWORD environment variables must be set")
        print("\nTo run this test, set the environment variables:")
        print("  export BHOOMI_USERNAME='your_username'")
        print("  export BHOOMI_PASSWORD='your_password'")
        print("\nThen run: python3 test_bhoomi_auth.py")
        sys.exit(1)
    
    print(f"\nCredentials loaded from environment variables")
    print(f"Username: {username}")
    print(f"Password: ***")
    
    # Run authentication test
    auth_test = BhoomiAuthTest()
    test_data = await auth_test.test_citizen_portal_login(username, password)
    
    # Generate markdown report
    report = auth_test.generate_markdown_report()
    
    # Save report
    report_file = auth_test.output_dir / "authentication_test_report.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\nAuthentication test report saved to: {report_file}")
    
    # Save JSON data
    json_file = auth_test.output_dir / "authentication_test_data.json"
    with open(json_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print(f"Authentication test data saved to: {json_file}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Authentication Result: {'✓ SUCCESS' if test_data['authentication_result'] else '✗ FAILED'}")
    print(f"Session Cookies Created: {len(test_data['session_cookies'])}")
    print(f"Final URL: {test_data['post_login'].get('url', 'N/A')}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
