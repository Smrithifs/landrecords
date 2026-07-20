import asyncio
import hashlib
import os
import time
from typing import Dict, Optional
from playwright.async_api import Error as PlaywrightError
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv


class ScraperException(Exception):
    """Custom exception for scraper errors"""
    pass


class BhoomiBaseScraper:
    """Base class for Bhoomi scrapers with common functionality"""
    
    # Class-level session cache (shared across all instances)
    _session_cache: Dict = None
    _session_timestamp: float = None
    _SESSION_TTL = 25 * 60  # 25 minutes in seconds
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        load_dotenv()
        self.username = username or os.getenv("BHOOMI_USERNAME")
        self.password = password or os.getenv("BHOOMI_PASSWORD")
        
        if not self.username or not self.password:
            load_dotenv(".env.example")
            self.username = os.getenv("BHOOMI_USERNAME")
            self.password = os.getenv("BHOOMI_PASSWORD")
        
        if not self.username or not self.password:
            raise ScraperException("BHOOMI_USERNAME and BHOOMI_PASSWORD must be set")
    
    def _is_session_valid(self) -> bool:
        """Check if cached session is still valid (< 25 minutes old)"""
        if self._session_cache is None or self._session_timestamp is None:
            return False
        return (time.time() - self._session_timestamp) < self._SESSION_TTL
    
    def _update_session_cache(self, cookies_for_playwright):
        """Update the session cache with fresh cookies"""
        self._session_cache = cookies_for_playwright
        self._session_timestamp = time.time()
        print("Session cache updated")
    
    def _md5(self, text: str) -> str:
        """Generate MD5 hash of text"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _get_viewstate(self, html: str) -> tuple:
        """Extract __VIEWSTATE, __EVENTVALIDATION, __VIEWSTATEGENERATOR from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        vs = soup.find('input', {'id': '__VIEWSTATE'})
        ev = soup.find('input', {'id': '__EVENTVALIDATION'})
        vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        return (
            vs['value'] if vs and vs.get('value') else '',
            ev['value'] if ev and ev.get('value') else '',
            vsg['value'] if vsg and vsg.get('value') else ''
        )
    
    async def _http_login(self) -> Dict:
        """Perform HTTP login and return cookies"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Get login page
        r = session.get("https://landrecords.karnataka.gov.in/citizenportal/")
        vs, ev, vsg = self._get_viewstate(r.text)
        
        # Get CAPTCHA
        captcha_r = session.get("https://landrecords.karnataka.gov.in/citizenportal/GenerateCaptcha.aspx")
        os.makedirs("logs/debug", exist_ok=True)
        with open("logs/debug/captcha.png", "wb") as f:
            f.write(captcha_r.content)
        
        print("=== LOGIN CAPTCHA ===")
        print("CAPTCHA image saved to: logs/debug/captcha.png")
        print("Please enter the CAPTCHA and press ENTER to continue...")
        captcha = input("Enter CAPTCHA: ").strip()
        
        # Login
        session.post("https://landrecords.karnataka.gov.in/citizenportal/", data={
            "ScriptManager1": "updpanl|btnLogin",
            "txtUname": self.username,
            "txtCapctha": captcha,
            "HDusername": self._md5(self.username),
            "HDPassword": self._md5(self.password),
            "__ASYNCPOST": "true",
            "btnLogin": "Login",
            "__VIEWSTATE": vs,
            "__VIEWSTATEGENERATOR": vsg,
            "__EVENTVALIDATION": ev,
        }, headers={"X-Requested-With": "XMLHttpRequest"})
        
        print("=== COOKIES AFTER CITIZENPORTAL LOGIN ===")
        for c in session.cookies:
            print(f"  {c.name}: {c.value}")
        has_aspnet_session = any(c.name == "ASP.NET_SessionId" for c in session.cookies)
        print(f"  ASP.NET_SessionId present: {has_aspnet_session}")
        
        # Navigate to dashboard
        session.get("https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx")
        
        print("=== COOKIES AFTER DASHBOARD NAVIGATION ===")
        for c in session.cookies:
            print(f"  {c.name}: {c.value}")
        has_aspnet_session = any(c.name == "ASP.NET_SessionId" for c in session.cookies)
        print(f"  ASP.NET_SessionId present: {has_aspnet_session}")
        
        # GET intermediate IRTC page
        r_int = session.get("https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
            headers={"Referer": "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"})
        
        print("=== INTERMEDIATE IRTC PAGE RESPONSE ===")
        print(f"Status: {r_int.status_code}")
        print(f"URL: {r_int.url}")
        
        # Parse form and POST to service37 (critical step for session establishment)
        soup_int = BeautifulSoup(r_int.text, 'html.parser')
        form = soup_int.find('form')
        if form:
            form_action = form.get('action')
            print(f"Form action: {form_action}")
            form_data = {inp.get('name'): inp.get('value','') for inp in form.find_all('input')}
            print(f"Form data keys: {list(form_data.keys())}")
            
            r_s37 = session.post(form_action, data=form_data, headers={
                "Referer": "https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
                "Origin": "https://landrecords.karnataka.gov.in"
            })
            
            print("=== SERVICE37 POST RESPONSE ===")
            print(f"Status: {r_s37.status_code}")
            print(f"URL: {r_s37.url}")
        else:
            print("NO FORM FOUND IN INTERMEDIATE IRTC PAGE")
        
        print("=== COOKIES AFTER SERVICE37 POST ===")
        for c in session.cookies:
            print(f"  {c.name}: {c.value}")
        has_aspnet_session = any(c.name == "ASP.NET_SessionId" for c in session.cookies)
        print(f"  ASP.NET_SessionId present: {has_aspnet_session}")
        
        # Prepare cookies for Playwright
        cookies_for_playwright = []
        for c in session.cookies:
            cookie = {
                "name": c.name,
                "value": c.value,
                "domain": "landrecords.karnataka.gov.in",
                "path": "/",
                "secure": True,
                "httpOnly": c.name in ["ASP.NET_SessionId", "Id"]
            }
            cookies_for_playwright.append(cookie)
        
        return cookies_for_playwright
    
    async def _match_dropdown_option(self, page, selector: str, target_text: str) -> Optional[str]:
        """
        Match dropdown option by fuzzy text matching (case-insensitive, stripped).
        Normalizes spacing and punctuation for comparison.
        Uses contains matching instead of exact matching.
        Returns the value of the matched option or None.
        """
        import re
        
        def normalize(s):
            s = s.upper().strip()
            s = s.replace(' (', '(').replace('( ', '(')
            s = s.replace(' )', ')').replace(') ', ')')
            s = re.sub(r'\s+', ' ', s)
            return s
        
        options = await page.query_selector_all(f'{selector} option')
        
        target_normalized = normalize(target_text)
        
        for opt in options:
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            text_normalized = normalize(text)
            
            # Fuzzy match: contains matching
            if (target_normalized in text_normalized or text_normalized in target_normalized) and val:
                print(f"Matched {selector}: {val} - {text.strip()}")
                return val
        
        print(f"No fuzzy match found for {selector}: target='{target_text}' (normalized: '{target_normalized}')")
        # Print available options for debugging
        print(f"Available options for {selector}:")
        for opt in options[:10]:  # Show first 10 options
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            print(f"  {val} - {text.strip()}")
        return None
    
    async def _wait_for_dropdown_options(self, page, selector: str, timeout: int = 30000) -> bool:
        """
        Wait for dropdown to have options loaded (AJAX response).
        """
        try:
            await page.wait_for_function(
                f"() => document.querySelector('{selector}').options.length > 1",
                timeout=timeout
            )
            return True
        except PlaywrightError:
            return False
    
    async def _retry_with_backoff(self, func, max_retries: int = 3):
        """
        Retry function with exponential backoff: 5s, 15s, 45s
        """
        delays = [5, 15, 45]
        for attempt in range(max_retries):
            try:
                return await func()
            except PlaywrightError as e:
                if attempt < max_retries - 1:
                    delay = delays[attempt]
                    print(f"Timeout error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                else:
                    raise ScraperException(f"Failed after {max_retries} retries: {str(e)}")
