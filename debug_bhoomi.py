"""
Debug script for BhoomiRTCScraper with screenshot capture.
Tests the scraper with real Bengaluru property data.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings
from scrapers.bhoomi import BhoomiRTCScraper
from scrapers.models import BhoomiRTCInput, BhoomiRTCOutput
from utils.logger import get_default_logger
from utils.retry import retry


class DebugBhoomiScraper(BhoomiRTCScraper):
    """Debug wrapper for BhoomiRTCScraper with screenshot capture."""
    
    def __init__(self, config: Dict[str, Any], cache_service=None, proxy_service=None, captcha_service=None):
        super().__init__(config, cache_service, proxy_service, captcha_service)
        self.debug_dir = Path("logs/debug")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_count = 0
        self.execution_log = []
    
    @retry(max_attempts=1, delay=1.0, backoff=1.0, exceptions=(Exception,))
    async def scrape(self, input_data: BhoomiRTCInput) -> BhoomiRTCOutput:
        """Override scrape to capture screenshots at key points."""
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
            # Capture screenshot after initialization
            await self.capture_screenshot("after_initialization")
            
            # Navigate to Bhoomi RTC portal
            self.logger.debug(f"Navigating to: {self.rtc_url}")
            await self.page.goto(self.rtc_url, wait_until='networkidle')
            
            # Capture screenshot after navigation
            await self.capture_screenshot("after_navigation")
            
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
            # Capture screenshot on error
            await self.capture_screenshot("error_state")
            raise
        finally:
            await self.close()
    
    async def capture_screenshot(self, step_name: str) -> str:
        """Capture screenshot with step name."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{step_name}_{timestamp}.png"
            filepath = self.debug_dir / filename
            
            if self.page:
                await self.page.screenshot(path=str(filepath))
                self.screenshot_count += 1
                self.logger.info(f"Screenshot captured: {filename}")
                self.execution_log.append({
                    'step': step_name,
                    'screenshot': filename,
                    'timestamp': datetime.now().isoformat()
                })
                return str(filepath)
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}")
        return None
    
    async def _select_district(self, district: str) -> None:
        """Override to capture screenshot after selection."""
        # Capture screenshot before selection to see page state
        await self.capture_screenshot("before_district_selection")
        await super()._select_district(district)
        await self.capture_screenshot("after_district_selection")
    
    async def _select_taluk(self, taluk: str) -> None:
        """Override to capture screenshot after selection."""
        await super()._select_taluk(taluk)
        await self.capture_screenshot("after_taluk_selection")
    
    async def _select_hobli(self, hobli: str) -> None:
        """Override to capture screenshot after selection."""
        await super()._select_hobli(hobli)
        await self.capture_screenshot("after_hobli_selection")
    
    async def _select_village(self, village: str) -> None:
        """Override to capture screenshot after selection."""
        await super()._select_village(village)
        await self.capture_screenshot("after_village_selection")
    
    async def _enter_survey_number(self, survey_no: str) -> None:
        """Override to capture screenshot after entry."""
        await super()._enter_survey_number(survey_no)
        await self.capture_screenshot("after_survey_entry")
    
    async def _solve_captcha(self) -> bool:
        """Override to capture screenshot after captcha detection."""
        # Capture before solving
        await self.capture_screenshot("before_captcha_solve")
        result = await super()._solve_captcha()
        await self.capture_screenshot("after_captcha_solve")
        return result
    
    async def _wait_for_results(self) -> None:
        """Override to capture screenshot after results load."""
        await super()._wait_for_results()
        await self.capture_screenshot("after_results_load")


async def main():
    """Main debug execution."""
    # Setup logging
    settings = get_settings()
    logger = get_default_logger()
    
    logger.info("=" * 80)
    logger.info("BHOOMI RTC SCRAPER DEBUG MODE")
    logger.info("=" * 80)
    
    # Real Bengaluru test data
    # Using known test data for Bengaluru Urban district
    test_input = BhoomiRTCInput(
        survey_no="123",  # Test survey number
        village="示例村",  # Test village
        hobli="示例Hobli",  # Test hobli
        district="Bengaluru Urban"  # Bengaluru Urban district
    )
    
    logger.info(f"Test Input:")
    logger.info(f"  District: {test_input.district}")
    logger.info(f"  Hobli: {test_input.hobli}")
    logger.info(f"  Village: {test_input.village}")
    logger.info(f"  Survey No: {test_input.survey_no}")
    logger.info("-" * 80)
    
    # Initialize debug scraper
    config = {
        'bhoomi_url': settings.PORTALS.get('bhoomi_url', 'https://landrecords.karnataka.gov.in'),
        'headless': False,  # Run in visible mode for debugging
        'page_load_timeout': 60000,
        'cache_ttl': 86400
    }
    
    debug_scraper = DebugBhoomiScraper(config)
    debug_scraper.logger = logger
    
    try:
        logger.info("Starting debug scrape...")
        start_time = datetime.now()
        
        result = await debug_scraper.scrape(test_input)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("SCRAPE RESULTS")
        logger.info("=" * 80)
        logger.info(f"Execution Time: {duration:.2f} seconds")
        logger.info(f"Screenshots Captured: {debug_scraper.screenshot_count}")
        logger.info("-" * 80)
        logger.info(f"Owner Name: {result.owner_name}")
        logger.info(f"Khata No: {result.khata_no}")
        logger.info(f"Survey No: {result.survey_no}")
        logger.info(f"Land Use: {result.land_use}")
        logger.info(f"Area: {result.area}")
        logger.info(f"Mutation Status: {result.mutation_status}")
        logger.info(f"Village: {result.village}")
        logger.info(f"Hobli: {result.hobli}")
        logger.info(f"District: {result.district}")
        logger.info("=" * 80)
        
        # Generate execution report
        report_path = debug_scraper.debug_dir / "execution_report.txt"
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("BHOOMI RTC SCRAPER DEBUG EXECUTION REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Execution Time: {datetime.now().isoformat()}\n")
            f.write(f"Duration: {duration:.2f} seconds\n")
            f.write(f"Screenshots Captured: {debug_scraper.screenshot_count}\n")
            f.write("-" * 80 + "\n")
            f.write("TEST INPUT:\n")
            f.write(f"  District: {test_input.district}\n")
            f.write(f"  Hobli: {test_input.hobli}\n")
            f.write(f"  Village: {test_input.village}\n")
            f.write(f"  Survey No: {test_input.survey_no}\n")
            f.write("-" * 80 + "\n")
            f.write("RESULTS:\n")
            f.write(f"  Owner Name: {result.owner_name}\n")
            f.write(f"  Khata No: {result.khata_no}\n")
            f.write(f"  Survey No: {result.survey_no}\n")
            f.write(f"  Land Use: {result.land_use}\n")
            f.write(f"  Area: {result.area}\n")
            f.write(f"  Mutation Status: {result.mutation_status}\n")
            f.write(f"  Village: {result.village}\n")
            f.write(f"  Hobli: {result.hobli}\n")
            f.write(f"  District: {result.district}\n")
            f.write("-" * 80 + "\n")
            f.write("EXECUTION LOG:\n")
            for log_entry in debug_scraper.execution_log:
                f.write(f"  [{log_entry['timestamp']}] {log_entry['step']}: {log_entry['screenshot']}\n")
            f.write("=" * 80 + "\n")
        
        logger.info(f"Execution report saved to: {report_path}")
        
    except Exception as e:
        logger.error(f"Debug scrape failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
