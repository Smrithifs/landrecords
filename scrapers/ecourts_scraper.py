"""
eCourts legal case scraper for Bengaluru.
Searches for cases by party name across multiple years.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from playwright.async_api import async_playwright

from .base import BaseScraper
from .models import ECourtsInput, ECourtsOutput
from utils.logger import get_default_logger


class ECourtsScraper(BaseScraper):
    """
    eCourts legal case scraper for Bengaluru courts.
    Searches cases by party name across multiple years (2015-2024).
    """
    
    def __init__(self, config: Dict[str, Any], **kwargs) -> None:
        """Initialize eCourts scraper."""
        super().__init__(config, **kwargs)
        self.base_url = "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus/index"
        self.state = "Karnataka"
        self.district = "Bengaluru Urban"
        self.years = [2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015]
        self.logger = get_default_logger()
    
    async def scrape(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search eCourts by party name across multiple years.
        
        Args:
            query_params: Dictionary containing owner_name
            
        Returns:
            Dictionary containing all case results across years
        """
        owner_name = query_params.get('owner_name', '')
        
        if not owner_name:
            raise ValueError("owner_name is required")
        
        self.logger.info(f"Starting eCourts search for owner: {owner_name}")
        
        all_cases = []
        
        for year in self.years:
            self.logger.info(f"Searching year: {year}")
            year_cases = await self.search_by_year(owner_name, year)
            
            if year_cases:
                all_cases.extend(year_cases)
                self.logger.info(f"Found {len(year_cases)} cases for year {year}")
            else:
                self.logger.info(f"No cases found for year {year}")
            
            # Small delay between years to avoid rate limiting
            await asyncio.sleep(2)
        
        # Save combined results
        result = {
            'owner_name': owner_name,
            'total_cases_found': len(all_cases),
            'years_searched': self.years,
            'cases': all_cases,
            'scraped_at': datetime.utcnow().isoformat(),
            'source': 'eCourts'
        }
        
        # Save to file
        debug_dir = Path('logs/debug')
        debug_dir.mkdir(parents=True, exist_ok=True)
        result_file = debug_dir / 'ecourts_result.json'
        
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        self.logger.info(f"Results saved to {result_file}")
        self.logger.info(f"Total cases found across all years: {len(all_cases)}")
        
        return result
    
    async def search_by_year(self, owner_name: str, year: int) -> List[Dict[str, Any]]:
        """
        Search eCourts for a specific year.
        
        Args:
            owner_name: Party name to search for
            year: Year to search
            
        Returns:
            List of case dictionaries for the year
        """
        if not self.page:
            await self.initialize()
        
        try:
            # Navigate to eCourts
            await self.navigate(self.base_url)
            await asyncio.sleep(2)
            
            # Take screenshot for debugging
            await self.capture_screenshot(f"ecourts_page_{year}.png")
            
            # Select State
            await self.select_state()
            
            # Select District
            await self.select_district()
            
            # Select Court Complex (All)
            await self.select_court_complex()
            
            # Click Party Name tab
            await self.click_party_name_tab()
            
            # Fill petitioner name
            await self.fill_petitioner_name(owner_name)
            
            # Fill year
            await self.fill_year(year)
            
            # Select Both (pending + disposed)
            await self.select_case_status()
            
            # Read and fill captcha
            captcha_text = await self.read_captcha()
            await self.fill_captcha(captcha_text)
            
            # Click Go
            await self.click_search()
            
            # Wait for results
            await asyncio.sleep(3)
            
            # Extract case results
            cases = await self.extract_case_results(year)
            
            return cases
            
        except Exception as e:
            self.logger.error(f"Error searching year {year}: {e}")
            await self.capture_screenshot(f"ecourts_error_{year}.png")
            return []
    
    async def select_state(self) -> None:
        """Select Karnataka state."""
        try:
            # Wait for state dropdown
            await self.page.wait_for_selector('#sess_state_code', timeout=10000)
            
            # Select Karnataka
            await self.page.select_option('#sess_state_code', label='Karnataka')
            self.logger.info("Selected state: Karnataka")
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Error selecting state: {e}")
            raise
    
    async def select_district(self) -> None:
        """Select Bengaluru Urban district."""
        try:
            # Wait for district dropdown
            await self.page.wait_for_selector('#sess_dist_code', timeout=10000)
            
            # Select Bengaluru Urban
            await self.page.select_option('#sess_dist_code', label='Bengaluru Urban')
            self.logger.info("Selected district: Bengaluru Urban")
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Error selecting district: {e}")
            raise
    
    async def select_court_complex(self) -> None:
        """Select all court complexes."""
        try:
            # Wait for court complex dropdown
            await self.page.wait_for_selector('#court_complex_code', timeout=10000)
            
            # Select first available option (or "All" if available)
            await self.page.select_option('#court_complex_code', index=1)
            self.logger.info("Selected court complex")
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Error selecting court complex: {e}")
            raise
    
    async def click_party_name_tab(self) -> None:
        """Click on Party Name tab."""
        try:
            # Look for party name tab/button
            party_tab = await self.page.query_selector('a:has-text("Party Name"), button:has-text("Party Name"), input[value="Party Name"]')
            if party_tab:
                await party_tab.click()
                self.logger.info("Clicked Party Name tab")
                await asyncio.sleep(1)
            else:
                self.logger.warning("Party Name tab not found, may already be on correct tab")
        except Exception as e:
            self.logger.error(f"Error clicking Party Name tab: {e}")
    
    async def fill_petitioner_name(self, name: str) -> None:
        """Fill petitioner name field."""
        try:
            # Look for petitioner name input
            petitioner_input = await self.page.query_selector('#petres_name')
            if petitioner_input:
                await petitioner_input.fill(name)
                self.logger.info(f"Filled petitioner name: {name}")
                await asyncio.sleep(0.5)
            else:
                self.logger.error("Petitioner name input not found")
                raise
        except Exception as e:
            self.logger.error(f"Error filling petitioner name: {e}")
            raise
    
    async def fill_year(self, year: int) -> None:
        """Fill year field."""
        try:
            # Look for year input
            year_input = await self.page.query_selector('#rgyearP')
            if year_input:
                await year_input.fill(str(year))
                self.logger.info(f"Filled year: {year}")
                await asyncio.sleep(0.5)
            else:
                self.logger.error("Year input not found")
                raise
        except Exception as e:
            self.logger.error(f"Error filling year: {e}")
            raise
    
    async def select_case_status(self) -> None:
        """Select Both (pending + disposed) case status."""
        try:
            # Look for case status radio - radB is for Both
            both_option = await self.page.query_selector('#radB')
            if both_option:
                await both_option.check()
                self.logger.info("Selected case status: Both")
                await asyncio.sleep(0.5)
            else:
                self.logger.warning("Case status 'Both' option not found")
        except Exception as e:
            self.logger.error(f"Error selecting case status: {e}")
    
    async def read_captcha(self) -> str:
        """
        Read captcha text from DOM element.
        
        Returns:
            Captcha text string
        """
        try:
            # Try to read captcha from various possible elements
            captcha_selectors = [
                "#captcha_image",
                ".captext",
                "#cap_text",
                "[id*='captcha']",
                "[class*='captcha']"
            ]
            
            for selector in captcha_selectors:
                try:
                    captcha_element = await self.page.query_selector(selector)
                    if captcha_element:
                        captcha_text = await captcha_element.inner_text()
                        if captcha_text and captcha_text.strip():
                            self.logger.info(f"Read captcha: {captcha_text.strip()}")
                            return captcha_text.strip()
                except:
                    continue
            
            # If no text element found, try to get from image alt or title
            captcha_img = await self.page.query_selector('img[src*="captcha"], img[id*="captcha"]')
            if captcha_img:
                alt_text = await captcha_img.get_attribute('alt')
                if alt_text:
                    self.logger.info(f"Read captcha from alt: {alt_text}")
                    return alt_text
            
            self.logger.warning("Could not read captcha automatically")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error reading captcha: {e}")
            return ""
    
    async def fill_captcha(self, captcha_text: str) -> None:
        """Fill captcha input field."""
        try:
            # Look for captcha input - fcaptcha_code for party name search
            captcha_input = await self.page.query_selector('#fcaptcha_code')
            if captcha_input:
                await captcha_input.fill(captcha_text)
                self.logger.info(f"Filled captcha: {captcha_text}")
                await asyncio.sleep(0.5)
            else:
                self.logger.error("Captcha input not found")
                raise
        except Exception as e:
            self.logger.error(f"Error filling captcha: {e}")
            raise
    
    async def click_search(self) -> None:
        """Click Search/Go button."""
        try:
            # Look for search button - printbtn4 is the search button for party name
            search_button = await self.page.query_selector('#printbtn4')
            if search_button:
                await search_button.click()
                self.logger.info("Clicked Search button")
            else:
                self.logger.error("Search button not found")
                raise
        except Exception as e:
            self.logger.error(f"Error clicking search: {e}")
            raise
    
    async def extract_case_results(self, year: int) -> List[Dict[str, Any]]:
        """
        Extract case results from the results table.
        
        Args:
            year: Year being searched
            
        Returns:
            List of case dictionaries
        """
        cases = []
        
        try:
            # Look for results table
            table_selectors = [
                'table',
                '.table',
                '#result_table',
                '.result-table',
                'table[class*="table"]'
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    table = await self.page.query_selector(selector)
                    if table:
                        self.logger.info(f"Found results table using selector: {selector}")
                        break
                except:
                    continue
            
            if not table:
                self.logger.info("No results table found")
                return cases
            
            # Get all rows
            rows = await table.query_selector_all('tr')
            self.logger.info(f"Found {len(rows)} rows in table")
            
            if len(rows) <= 1:  # Only header row or empty
                return cases
            
            # Extract headers from first row
            headers = []
            header_cells = await rows[0].query_selector_all('th, td')
            for cell in header_cells:
                text = await cell.text_content()
                headers.append(text.strip() if text else "")
            
            self.logger.info(f"Headers: {headers}")
            
            # Extract data from remaining rows
            for row in rows[1:]:
                cells = await row.query_selector_all('td')
                if not cells:
                    continue
                
                row_data = {}
                for i, cell in enumerate(cells):
                    text = await cell.text_content()
                    if i < len(headers):
                        row_data[headers[i]] = text.strip() if text else ""
                    else:
                        row_data[f"column_{i}"] = text.strip() if text else ""
                
                # Map to standard fields
                case_data = self.map_case_fields(row_data, year)
                if case_data:
                    cases.append(case_data)
            
        except Exception as e:
            self.logger.error(f"Error extracting case results: {e}")
            import traceback
            traceback.print_exc()
        
        return cases
    
    def map_case_fields(self, row_data: Dict[str, str], year: int) -> Optional[Dict[str, Any]]:
        """
        Map raw table data to standard case fields.
        
        Args:
            row_data: Raw row data from table
            year: Year of search
            
        Returns:
            Mapped case dictionary or None
        """
        mapped = {}
        
        # Field mappings (case-insensitive)
        field_mappings = {
            'case_number': ['case no', 'case number', 'caseno', 'case_no', 'case no.'],
            'case_type': ['case type', 'casetype', 'case type'],
            'filing_date': ['filing date', 'file date', 'registration date', 'reg date'],
            'status': ['status', 'case status', 'disposal status'],
            'next_hearing_date': ['next hearing', 'next date', 'hearing date', 'next hearing date'],
            'court_name': ['court', 'court name', 'court complex'],
            'dispute_category': ['category', 'dispute category', 'case category'],
            'petitioner': ['petitioner', 'party name', 'petitioner name'],
            'respondent': ['respondent', 'respondent name']
        }
        
        # Map fields
        for target_field, possible_keys in field_mappings.items():
            for key, value in row_data.items():
                if any(pk in key.lower() for pk in possible_keys):
                    mapped[target_field] = value
                    break
        
        # Add year
        mapped['search_year'] = year
        
        # Add timestamp
        mapped['scraped_at'] = datetime.utcnow().isoformat()
        mapped['source'] = 'eCourts'
        
        # If no mapping found, use raw data
        if not mapped or len(mapped) <= 2:  # Only has scraped_at and source
            mapped = row_data
            mapped['search_year'] = year
            mapped['scraped_at'] = datetime.utcnow().isoformat()
            mapped['source'] = 'eCourts'
        
        return mapped
    
    async def verify_captcha(self) -> bool:
        """
        Verify and handle captcha if present.
        
        Returns:
            True if captcha handled successfully, False otherwise
        """
        # For eCourts, captcha is handled during search
        return True


async def main():
    """Test function for eCourts scraper."""
    config = {
        'headless': False,
        'screenshot_dir': 'logs/screenshots'
    }
    
    scraper = ECourtsScraper(config)
    
    try:
        result = await scraper.scrape({
            'owner_name': 'Chikkagowda'
        })
        
        print(f"\n=== Search Complete ===")
        print(f"Total cases found: {result['total_cases_found']}")
        print(f"Years searched: {result['years_searched']}")
        print(f"Results saved to: logs/debug/ecourts_result.json")
        
        if result['cases']:
            print(f"\nSample case:")
            print(json.dumps(result['cases'][0], indent=2))
        
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
