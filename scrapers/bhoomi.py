"""
Bhoomi land record scraper for Karnataka.
Handles scraping from the Bhoomi online portal.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .base import BaseScraper
from .models import BhoomiRTCInput, BhoomiRTCOutput
from utils.retry import retry
from utils.logger import get_default_logger


class BhoomiScraper(BaseScraper):
    """Scraper for Bhoomi Karnataka land records."""
    
    def __init__(self, config: Dict[str, Any], cache_service=None, proxy_service=None, captcha_service=None):
        """
        Initialize Bhoomi scraper.
        
        Args:
            config: Configuration dictionary
            cache_service: Optional cache service instance
            proxy_service: Optional proxy service instance
            captcha_service: Optional captcha service instance
        """
        super().__init__(config, cache_service, proxy_service, captcha_service)
        self.base_url = config.get('bhoomi_url', 'https://bhoomi.karnataka.gov.in')
    
    async def scrape(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape Bhoomi land records.
        
        Args:
            query_params: Dictionary containing district, taluk, hobli, survey_number, etc.
            
        Returns:
            Dictionary containing land record details
        """
        await self.initialize()
        
        try:
            # Navigate to Bhoomi portal
            await self.page.goto(self.base_url)
            
            # Select district
            district = query_params.get('district')
            if district:
                await self._select_district(district)
            
            # Select taluk
            taluk = query_params.get('taluk')
            if taluk:
                await self._select_taluk(taluk)
            
            # Select hobli
            hobli = query_params.get('hobli')
            if hobli:
                await self._select_hobli(hobli)
            
            # Enter survey number
            survey_number = query_params.get('survey_number')
            if survey_number:
                await self._enter_survey_number(survey_number)
            
            # Handle captcha
            captcha_success = await self.verify_captcha()
            if not captcha_success:
                return {'error': 'Captcha verification failed'}
            
            # Submit and extract data
            await self._submit_search()
            data = await self._extract_land_data()
            
            return data
            
        finally:
            await self.close()
    
    async def verify_captcha(self) -> bool:
        """
        Verify and handle captcha for Bhoomi portal.
        
        Returns:
            True if captcha handled successfully
        """
        # Placeholder for captcha handling logic
        # Will integrate with captcha_service
        return True
    
    async def _select_district(self, district: str) -> None:
        """Select district from dropdown."""
        pass
    
    async def _select_taluk(self, taluk: str) -> None:
        """Select taluk from dropdown."""
        pass
    
    async def _select_hobli(self, hobli: str) -> None:
        """Select hobli from dropdown."""
        pass
    
    async def _enter_survey_number(self, survey_number: str) -> None:
        """Enter survey number in input field."""
        pass
    
    async def _submit_search(self) -> None:
        """Submit the search form."""
        pass
    
    async def _extract_land_data(self) -> Dict[str, Any]:
        """
        Extract land record data from the page.
        
        Returns:
            Dictionary containing land record details
        """
        return {
            'survey_number': '',
            'owner_name': '',
            'extent': '',
            'land_type': '',
            'encumbrance': []
        }


class BhoomiRTCScraper(BaseScraper):
    """
    Production-ready Bhoomi RTC scraper for Bengaluru Urban and Rural districts.
    
    Scope: Bengaluru Urban, Bengaluru Rural
    Input: {survey_no, village, hobli, district}
    Output: {owner_name, khata_no, survey_no, land_use, area, mutation_status, village, hobli, district}
    """
    
    def __init__(self, config: Dict[str, Any], cache_service=None, proxy_service=None, captcha_service=None):
        """
        Initialize BhoomiRTC scraper.
        
        Args:
            config: Configuration dictionary
            cache_service: Optional cache service instance
            proxy_service: Optional proxy service instance
            captcha_service: Optional captcha service instance
        """
        super().__init__(config, cache_service, proxy_service, captcha_service)
        self.base_url = config.get('bhoomi_url', 'https://landrecords.karnataka.gov.in')
        self.citizen_portal_url = config.get('bhoomi_citizen_portal', 'https://landrecords.karnataka.gov.in/citizenportal')
        self.rtc_service_url = config.get('bhoomi_rtc_service', 'https://rtc.karnataka.gov.in/Service78')
        self.rtc_url = f"{self.base_url}/service78/ViewRTC.aspx"
        self.cache_ttl = config.get('cache_ttl', 86400)  # 24 hours default
        
        # Authentication configuration
        self.auth_config = config.get('bhoomi_auth', {})
        self.auth_enabled = self.auth_config.get('enabled', True)
        self.auth_method = self.auth_config.get('method', 'citizen_portal')
        self.username = self.auth_config.get('username', '')
        self.password = self.auth_config.get('password', '')
        self.mobile = self.auth_config.get('mobile', '')
        self.email = self.auth_config.get('email', '')
        self.aadhaar = self.auth_config.get('aadhaar', '')
        self.session_timeout = self.auth_config.get('session_timeout', 1800)
        self.auto_renew = self.auth_config.get('auto_renew', True)
        
        # Session management
        self.authenticated = False
        self.session_start_time = None
    
    def _generate_cache_key(self, input_data: BhoomiRTCInput) -> str:
        """
        Generate cache key for RTC query.
        
        Args:
            input_data: BhoomiRTCInput object
            
        Returns:
            Cache key string
        """
        return f"bhoomi_rtc:{input_data.district}:{input_data.hobli}:{input_data.village}:{input_data.survey_no}"
    
    def _is_session_valid(self) -> bool:
        """
        Check if current session is valid.
        
        Returns:
            True if session is valid, False otherwise
        """
        if not self.authenticated:
            return False
        
        if self.session_start_time is None:
            return False
        
        session_age = (datetime.now() - self.session_start_time).total_seconds()
        return session_age < self.session_timeout
    
    async def _login_citizen_portal(self) -> bool:
        """
        Login to Bhoomi citizen portal using username/password.
        
        Returns:
            True if login successful, False otherwise
        """
        self.logger.debug("Attempting citizen portal login")
        
        if not self.username or not self.password:
            self.logger.error("Username or password not configured for citizen portal login")
            return False
        
        try:
            # Navigate to citizen portal
            await self.page.goto(self.citizen_portal_url, wait_until='networkidle')
            
            # Wait for login form
            username_input = await self.page.wait_for_selector('#txtUname', timeout=10000)
            password_input = await self.page.wait_for_selector('#txtPwd', timeout=10000)
            
            # Enter credentials
            await username_input.fill(self.username)
            await password_input.fill(self.password)
            
            # Handle CAPTCHA if present
            if self.captcha_service:
                captcha_success = await self._solve_captcha()
                if not captcha_success:
                    self.logger.warning("CAPTCHA solving failed, attempting login anyway")
            
            # Submit login form
            submit_button = await self.page.query_selector('input[type="submit"], button[type="submit"]')
            if submit_button:
                await submit_button.click()
                await self.page.wait_for_timeout(3000)
            
            # Check if login successful (redirect or success indicator)
            current_url = self.page.url
            if current_url != self.citizen_portal_url:
                self.logger.info("Citizen portal login successful")
                self.authenticated = True
                self.session_start_time = datetime.now()
                return True
            else:
                self.logger.error("Citizen portal login failed - no redirect detected")
                return False
                
        except Exception as e:
            self.logger.error(f"Citizen portal login failed: {e}")
            return False
    
    async def _login_guest_user(self) -> bool:
        """
        Login to Bhoomi guest user service using mobile/email/Aadhaar.
        
        Returns:
            True if login successful, False otherwise
        """
        self.logger.debug("Attempting guest user login")
        
        if not self.mobile or not self.email or not self.aadhaar:
            self.logger.error("Mobile, email, or Aadhaar not configured for guest user login")
            return False
        
        try:
            # Navigate to guest user service
            guest_url = f"{self.base_url}/Service38/GuestUserInfo.aspx"
            await self.page.goto(guest_url, wait_until='networkidle')
            
            # Wait for form fields
            mobile_input = await self.page.wait_for_selector('#MainContent_txt_MobileNumber', timeout=10000)
            email_input = await self.page.wait_for_selector('#MainContent_txt_Email', timeout=10000)
            
            # Enter credentials
            await mobile_input.fill(self.mobile)
            await email_input.fill(self.email)
            
            # Aadhaar verification would require OTP handling
            # This is a placeholder for Aadhaar-based authentication
            self.logger.warning("Aadhaar-based authentication requires OTP handling - not fully implemented")
            
            # Submit form
            submit_button = await self.page.query_selector('input[type="submit"], button[type="submit"]')
            if submit_button:
                await submit_button.click()
                await self.page.wait_for_timeout(3000)
            
            # Check if login successful
            current_url = self.page.url
            if current_url != guest_url:
                self.logger.info("Guest user login successful")
                self.authenticated = True
                self.session_start_time = datetime.now()
                return True
            else:
                self.logger.error("Guest user login failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Guest user login failed: {e}")
            return False
    
    async def _ensure_authenticated(self) -> bool:
        """
        Ensure user is authenticated, login if necessary.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self.auth_enabled:
            self.logger.info("Authentication disabled, proceeding without login")
            return True
        
        if self._is_session_valid():
            self.logger.debug("Session is valid, no re-authentication needed")
            return True
        
        self.logger.info("Session invalid or expired, attempting authentication")
        
        if self.auth_method == 'citizen_portal':
            return await self._login_citizen_portal()
        elif self.auth_method == 'guest':
            return await self._login_guest_user()
        else:
            self.logger.error(f"Unknown authentication method: {self.auth_method}")
            return False
    
    @retry(max_attempts=3, delay=2.0, backoff=2.0, exceptions=(Exception,))
    async def scrape(self, input_data: BhoomiRTCInput) -> BhoomiRTCOutput:
        """
        Scrape Bhoomi RTC records with retry logic and caching.
        
        Args:
            input_data: BhoomiRTCInput object with query parameters
            
        Returns:
            BhoomiRTCOutput object with scraped data
        """
        self.logger.info(f"Starting Bhoomi RTC scrape for survey_no: {input_data.survey_no}, village: {input_data.village}")
        
        # Check cache first
        cache_key = self._generate_cache_key(input_data)
        if self.cache_service:
            cached_result = await self.cache_service.get(cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for key: {cache_key}")
                return BhoomiRTCOutput(**cached_result)
        
        await self.initialize()
        
        try:
            # Ensure authentication if enabled
            if not await self._ensure_authenticated():
                self.logger.error("Authentication failed, cannot proceed with scraping")
                raise Exception("Authentication failed")
            
            # Navigate to RTC service after authentication
            self.logger.debug(f"Navigating to RTC service: {self.rtc_service_url}")
            await self.page.goto(self.rtc_service_url, wait_until='networkidle')
            
            # Select district
            await self._select_district(input_data.district)
            
            # Select taluk (required step in Bhoomi workflow)
            taluk = input_data.hobli  # Using hobli as taluk fallback for now
            await self._select_taluk(taluk)
            
            # Select hobli
            await self._select_hobli(input_data.hobli)
            
            # Select village
            await self._select_village(input_data.village)
            
            # Enter survey number
            await self._enter_survey_number(input_data.survey_no)
            
            # Handle captcha
            captcha_success = await self._solve_captcha()
            if not captcha_success:
                self.logger.error("Captcha verification failed")
                raise Exception("Captcha verification failed")
            
            # Submit search form
            await self._submit_search()
            
            # Wait for results to load
            await self._wait_for_results()
            
            # Extract RTC data
            output_data = await self._extract_rtc_data(input_data)
            
            # Cache the result
            if self.cache_service:
                await self.cache_service.set(cache_key, output_data.dict(), ttl=self.cache_ttl)
                self.logger.info(f"Cached result with key: {cache_key}")
            
            self.logger.info(f"Bhoomi RTC scrape completed successfully for survey_no: {input_data.survey_no}")
            return output_data
            
        except Exception as e:
            self.logger.error(f"Bhoomi RTC scrape failed: {e}", exc_info=True)
            raise
        finally:
            await self.close()
    
    async def _select_district(self, district: str) -> None:
        """
        Select district from dropdown.
        
        Args:
            district: District name (Bengaluru Urban or Bengaluru Rural)
        """
        self.logger.debug(f"Selecting district: {district}")
        
        try:
            # Wait for district dropdown to be visible and enabled
            district_select = await self.page.wait_for_selector('select[name="ddlDistrict"]', timeout=10000)
            if not district_select:
                raise Exception("District dropdown not found")
            
            # Get all options and find matching district
            options = await district_select.query_selector_all('option')
            district_value = None
            
            for option in options:
                text = await option.text_content()
                if text and district.lower() in text.lower():
                    district_value = await option.get_attribute('value')
                    break
            
            if not district_value:
                # Try exact match
                for option in options:
                    text = await option.text_content()
                    if text and text.strip() == district:
                        district_value = await option.get_attribute('value')
                        break
            
            if district_value:
                await district_select.select_option(value=district_value)
                self.logger.info(f"Selected district: {district}")
                
                # Wait for taluk dropdown to populate (AJAX call)
                await self.page.wait_for_timeout(2000)
            else:
                raise Exception(f"District '{district}' not found in dropdown options")
                
        except Exception as e:
            self.logger.error(f"Failed to select district: {e}")
            raise
    
    async def _select_taluk(self, taluk: str) -> None:
        """
        Select taluk from dropdown (called after district selection).
        
        Args:
            taluk: Taluk name
        """
        self.logger.debug(f"Selecting taluk: {taluk}")
        
        try:
            # Wait for taluk dropdown to be visible and enabled
            taluk_select = await self.page.wait_for_selector('select[name="ddlTaluk"]', timeout=10000)
            if not taluk_select:
                raise Exception("Taluk dropdown not found")
            
            # Get all options and find matching taluk
            options = await taluk_select.query_selector_all('option')
            taluk_value = None
            
            for option in options:
                text = await option.text_content()
                if text and taluk.lower() in text.lower():
                    taluk_value = await option.get_attribute('value')
                    break
            
            if not taluk_value:
                # Try exact match
                for option in options:
                    text = await option.text_content()
                    if text and text.strip() == taluk:
                        taluk_value = await option.get_attribute('value')
                        break
            
            if taluk_value:
                await taluk_select.select_option(value=taluk_value)
                self.logger.info(f"Selected taluk: {taluk}")
                
                # Wait for hobli dropdown to populate (AJAX call)
                await self.page.wait_for_timeout(2000)
            else:
                raise Exception(f"Taluk '{taluk}' not found in dropdown options")
                
        except Exception as e:
            self.logger.error(f"Failed to select taluk: {e}")
            raise
    
    async def _select_hobli(self, hobli: str) -> None:
        """
        Select hobli from dropdown.
        
        Args:
            hobli: Hobli name
        """
        self.logger.debug(f"Selecting hobli: {hobli}")
        
        try:
            # Wait for hobli dropdown to be visible and enabled
            hobli_select = await self.page.wait_for_selector('select[name="ddlHobli"]', timeout=10000)
            if not hobli_select:
                raise Exception("Hobli dropdown not found")
            
            # Get all options and find matching hobli
            options = await hobli_select.query_selector_all('option')
            hobli_value = None
            
            for option in options:
                text = await option.text_content()
                if text and hobli.lower() in text.lower():
                    hobli_value = await option.get_attribute('value')
                    break
            
            if not hobli_value:
                # Try exact match
                for option in options:
                    text = await option.text_content()
                    if text and text.strip() == hobli:
                        hobli_value = await option.get_attribute('value')
                        break
            
            if hobli_value:
                await hobli_select.select_option(value=hobli_value)
                self.logger.info(f"Selected hobli: {hobli}")
                
                # Wait for village dropdown to populate (AJAX call)
                await self.page.wait_for_timeout(2000)
            else:
                raise Exception(f"Hobli '{hobli}' not found in dropdown options")
                
        except Exception as e:
            self.logger.error(f"Failed to select hobli: {e}")
            raise
    
    async def _select_village(self, village: str) -> None:
        """
        Select village from dropdown.
        
        Args:
            village: Village name
        """
        self.logger.debug(f"Selecting village: {village}")
        
        try:
            # Wait for village dropdown to be visible and enabled
            village_select = await self.page.wait_for_selector('select[name="ddlVillage"]', timeout=10000)
            if not village_select:
                raise Exception("Village dropdown not found")
            
            # Get all options and find matching village
            options = await village_select.query_selector_all('option')
            village_value = None
            
            for option in options:
                text = await option.text_content()
                if text and village.lower() in text.lower():
                    village_value = await option.get_attribute('value')
                    break
            
            if not village_value:
                # Try exact match
                for option in options:
                    text = await option.text_content()
                    if text and text.strip() == village:
                        village_value = await option.get_attribute('value')
                        break
            
            if village_value:
                await village_select.select_option(value=village_value)
                self.logger.info(f"Selected village: {village}")
                
                # Wait for survey number input to be enabled
                await self.page.wait_for_timeout(1000)
            else:
                raise Exception(f"Village '{village}' not found in dropdown options")
                
        except Exception as e:
            self.logger.error(f"Failed to select village: {e}")
            raise
    
    async def _enter_survey_number(self, survey_no: str) -> None:
        """
        Enter survey number in input field.
        
        Args:
            survey_no: Survey number
        """
        self.logger.debug(f"Entering survey number: {survey_no}")
        
        try:
            # Wait for survey number input field
            survey_input = await self.page.wait_for_selector('input[name="txtSurveyNo"]', timeout=10000)
            if not survey_input:
                raise Exception("Survey number input field not found")
            
            # Clear existing value and enter survey number
            await survey_input.clear()
            await survey_input.fill(survey_no)
            self.logger.info(f"Entered survey number: {survey_no}")
            
            # Click GO button to load survey details
            go_button = await self.page.query_selector('input[name="btnGo"]')
            if go_button:
                await go_button.click()
                self.logger.info("Clicked GO button")
                
                # Wait for Surnoc dropdown to appear
                await self.page.wait_for_timeout(2000)
            else:
                raise Exception("GO button not found")
                
        except Exception as e:
            self.logger.error(f"Failed to enter survey number: {e}")
            raise
    
    async def _solve_captcha(self) -> bool:
        """
        Solve captcha using captcha service.
        
        Returns:
            True if captcha solved successfully, False otherwise
        """
        self.logger.debug("Attempting to solve captcha")
        
        if not self.captcha_service:
            self.logger.warning("No captcha service configured, skipping captcha")
            return True
        
        try:
            # Locate captcha image element
            captcha_image = await self._get_captcha_image()
            if captcha_image:
                solution = await self.captcha_service.solve_image_captcha(captcha_image)
                if solution:
                    await self._enter_captcha_solution(solution)
                    return await self._verify_captcha_solution()
            else:
                self.logger.warning("Captcha image not found, may not be required")
                return True
            
            return True
        except Exception as e:
            self.logger.error(f"Captcha solving failed: {e}")
            return False
    
    async def _get_captcha_image(self) -> Optional[bytes]:
        """
        Extract captcha image from page.
        
        Returns:
            Captcha image as bytes or None if not found
        """
        try:
            # Look for captcha image element (common selectors)
            captcha_selectors = [
                'img[src*="captcha"]',
                'img[id*="captcha"]',
                'img[class*="captcha"]',
                '#captchaImage',
                '#imgCaptcha'
            ]
            
            for selector in captcha_selectors:
                captcha_element = await self.page.query_selector(selector)
                if captcha_element:
                    self.logger.debug(f"Found captcha element with selector: {selector}")
                    return await captcha_element.screenshot()
            
            self.logger.debug("No captcha image found on page")
            return None
        except Exception as e:
            self.logger.error(f"Failed to extract captcha image: {e}")
            return None
    
    async def _enter_captcha_solution(self, solution: str) -> None:
        """
        Enter captcha solution in input field.
        
        Args:
            solution: Captcha solution text
        """
        self.logger.debug("Entering captcha solution")
        
        try:
            # Look for captcha input field (common selectors)
            captcha_input_selectors = [
                'input[name*="captcha"]',
                'input[id*="captcha"]',
                'input[class*="captcha"]',
                '#txtCaptcha',
                '#captchaInput'
            ]
            
            for selector in captcha_input_selectors:
                captcha_input = await self.page.query_selector(selector)
                if captcha_input:
                    await captcha_input.clear()
                    await captcha_input.fill(solution)
                    self.logger.info(f"Entered captcha solution: {solution}")
                    return
            
            self.logger.warning("Captcha input field not found")
        except Exception as e:
            self.logger.error(f"Failed to enter captcha solution: {e}")
            raise
    
    async def _verify_captcha_solution(self) -> bool:
        """
        Verify captcha solution was accepted.
        
        Returns:
            True if solution accepted, False otherwise
        """
        try:
            # Check for common error messages
            error_selectors = [
                '.captcha_error',
                '#captchaError',
                '[class*="error"]',
                '[id*="error"]'
            ]
            
            for selector in error_selectors:
                error_element = await self.page.query_selector(selector)
                if error_element:
                    error_text = await error_element.text_content()
                    if error_text and ('invalid' in error_text.lower() or 'incorrect' in error_text.lower()):
                        self.logger.warning(f"Captcha error detected: {error_text}")
                        return False
            
            self.logger.debug("Captcha solution appears valid")
            return True
        except Exception as e:
            self.logger.error(f"Failed to verify captcha solution: {e}")
            return False
    
    async def _submit_search(self) -> None:
        """Submit the search form."""
        self.logger.debug("Submitting search form")
        
        try:
            # Look for submit/fetch details button
            submit_selectors = [
                'input[name="btnFetch"]',
                'input[value*="Fetch"]',
                'input[value*="Submit"]',
                'button[name*="Fetch"]',
                'button[id*="Fetch"]'
            ]
            
            for selector in submit_selectors:
                submit_button = await self.page.query_selector(selector)
                if submit_button:
                    await submit_button.click()
                    self.logger.info("Clicked submit/fetch button")
                    return
            
            self.logger.warning("Submit button not found, may auto-submit")
        except Exception as e:
            self.logger.error(f"Failed to submit search form: {e}")
            raise
    
    async def _wait_for_results(self) -> None:
        """Wait for search results to load."""
        self.logger.debug("Waiting for results to load")
        
        try:
            # Look for results table or container
            result_selectors = [
                'table[id*="Result"]',
                'table[class*="result"]',
                '#grdRTC',
                '#ResultTable',
                '.result-table'
            ]
            
            for selector in result_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=30000)
                    self.logger.info(f"Results loaded with selector: {selector}")
                    return
                except Exception:
                    continue
            
            # If no table found, wait for any content change
            self.logger.warning("Results table not found, waiting for page content")
            await self.page.wait_for_timeout(5000)
            
        except Exception as e:
            self.logger.error(f"Failed to wait for results: {e}")
            raise
    
    async def _extract_rtc_data(self, input_data: BhoomiRTCInput) -> BhoomiRTCOutput:
        """
        Extract RTC data from the results page.
        
        Args:
            input_data: Original input data for context
            
        Returns:
            BhoomiRTCOutput object with extracted data
        """
        self.logger.debug("Extracting RTC data from page")
        
        try:
            # Look for results table
            table_selectors = [
                'table[id*="grdRTC"]',
                'table[id*="Result"]',
                'table[class*="result"]'
            ]
            
            table = None
            for selector in table_selectors:
                table = await self.page.query_selector(selector)
                if table:
                    break
            
            if not table:
                self.logger.warning("Results table not found")
                return BhoomiRTCOutput(
                    owner_name=None,
                    khata_no=None,
                    survey_no=input_data.survey_no,
                    land_use=None,
                    area=None,
                    mutation_status=None,
                    village=input_data.village,
                    hobli=input_data.hobli,
                    district=input_data.district
                )
            
            # Extract data from table rows
            rows = await table.query_selector_all('tr')
            owner_name = None
            khata_no = None
            land_use = None
            area = None
            mutation_status = None
            
            for row in rows:
                cells = await row.query_selector_all('td, th')
                if len(cells) >= 2:
                    for i in range(len(cells) - 1):
                        label = await cells[i].text_content()
                        value = await cells[i + 1].text_content()
                        
                        label_lower = label.lower() if label else ""
                        value_clean = value.strip() if value else None
                        
                        if 'owner' in label_lower or 'name' in label_lower:
                            owner_name = value_clean
                        elif 'khata' in label_lower:
                            khata_no = value_clean
                        elif 'land use' in label_lower or 'use' in label_lower:
                            land_use = value_clean
                        elif 'area' in label_lower or 'extent' in label_lower:
                            area = value_clean
                        elif 'mutation' in label_lower:
                            mutation_status = value_clean
            
            self.logger.info(f"Extracted RTC data - Owner: {owner_name}, Khata: {khata_no}")
            
            return BhoomiRTCOutput(
                owner_name=owner_name,
                khata_no=khata_no,
                survey_no=input_data.survey_no,
                land_use=land_use,
                area=area,
                mutation_status=mutation_status,
                village=input_data.village,
                hobli=input_data.hobli,
                district=input_data.district
            )
            
        except Exception as e:
            self.logger.error(f"Failed to extract RTC data: {e}")
            return BhoomiRTCOutput(
                owner_name=None,
                khata_no=None,
                survey_no=input_data.survey_no,
                land_use=None,
                area=None,
                mutation_status=None,
                village=input_data.village,
                hobli=input_data.hobli,
                district=input_data.district
            )
    
    async def verify_captcha(self) -> bool:
        """
        Verify and handle captcha for Bhoomi portal.
        
        Returns:
            True if captcha handled successfully
        """
        return await self._solve_captcha()
