"""
Main entry point for the Bengaluru Land Verification System scraping service.
"""

import asyncio
import sys
from typing import Dict, Any, Optional

from config.settings import get_settings
from utils.logger import setup_default_logging, get_default_logger
from database.connection import get_database, close_database
from services.cache_service import CacheService
from services.proxy_service import ProxyService
from services.captcha_service import CaptchaService
from scrapers.bhoomi import BhoomiRTCScraper
from scrapers.kaveri import KaveriECScraper
from scrapers.legal import ECourtsScraper
from scrapers.bbmp import BBMPScraper
from scrapers.bescom import BESCOMScraper
from scrapers.bwssb import BWSSBScraper
from services.property_verification_service import (
    PropertyVerificationOrchestrator,
    PropertyVerificationRequest,
    RiskLevel
)


class ScrapingService:
    """Main scraping service orchestrator."""
    
    def __init__(self):
        """Initialize the scraping service."""
        self.settings = get_settings()
        self.logger = None
        self.db_connection = None
        self.cache_service = None
        self.proxy_service = None
        self.captcha_service = None
        
        # Property verification scrapers
        self.bhoomi_scraper = None
        self.kaveri_scraper = None
        self.bbmp_scraper = None
        self.bescom_scraper = None
        self.bwssb_scraper = None
        self.ecourts_scraper = None
        
        # Property verification orchestrator
        self.verification_orchestrator = None
    
    async def initialize(self) -> None:
        """Initialize all services and connections."""
        # Setup logging
        setup_default_logging(self.settings.LOGGING)
        self.logger = get_default_logger()
        self.logger.info(f"Starting {self.settings.APP_NAME} v{self.settings.APP_VERSION}")
        self.logger.info(f"Region Scope: {self.settings.REGION_SCOPE}")
        self.logger.info(f"Supported Districts: {', '.join(self.settings.SUPPORTED_DISTRICTS)}")
        self.logger.info(f"Supported Portals: {', '.join(self.settings.SUPPORTED_PORTALS)}")
        
        # Initialize database (optional for demo)
        try:
            self.db_connection = await get_database()
            await self.db_connection.create_tables()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.warning(f"Database initialization failed (continuing without database): {e}")
            self.db_connection = None
        
        # Initialize cache service
        if self.settings.CACHE['enabled']:
            self.cache_service = CacheService(self.settings.REDIS)
            await self.cache_service.connect()
            self.logger.info("Cache service initialized")
        
        # Initialize proxy service
        if self.settings.PROXY['enabled']:
            self.proxy_service = ProxyService(self.settings.PROXY)
            self.logger.info("Proxy service initialized")
        
        # Initialize captcha service
        if self.settings.CAPTCHA['enabled']:
            self.captcha_service = CaptchaService(self.settings.CAPTCHA)
            self.logger.info("Captcha service initialized")
        
        # Initialize property verification scrapers
        scraper_config = {
            **self.settings.PORTALS,
            **self.settings.SCRAPER,
            'headless': self.settings.SCRAPER.get('headless', True),
            'screenshot_dir': self.settings.SCRAPER.get('screenshot_dir', 'logs/screenshots')
        }
        
        self.bhoomi_scraper = BhoomiRTCScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("BhoomiRTC scraper initialized")
        
        self.kaveri_scraper = KaveriECScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("KaveriEC scraper initialized")
        
        self.bbmp_scraper = BBMPScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("BBMP scraper initialized")
        
        self.bescom_scraper = BESCOMScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("BESCOM scraper initialized")
        
        self.bwssb_scraper = BWSSBScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("BWSSB scraper initialized")
        
        self.ecourts_scraper = ECourtsScraper(
            scraper_config,
            cache_service=self.cache_service,
            proxy_service=self.proxy_service,
            captcha_service=self.captcha_service
        )
        self.logger.info("ECourts scraper initialized")
        
        # Initialize property verification orchestrator
        self.verification_orchestrator = PropertyVerificationOrchestrator(
            bhoomi_scraper=self.bhoomi_scraper,
            kaveri_scraper=self.kaveri_scraper,
            bbmp_scraper=self.bbmp_scraper,
            bescom_scraper=self.bescom_scraper,
            bwssb_scraper=self.bwssb_scraper,
            ecourts_scraper=self.ecourts_scraper,
            logger=self.logger
        )
        self.logger.info("PropertyVerificationOrchestrator initialized")
    
    async def shutdown(self) -> None:
        """Cleanup and close all connections."""
        self.logger.info("Shutting down scraping service...")
        
        if self.cache_service:
            await self.cache_service.disconnect()
        
        if self.db_connection:
            await close_database()
        
        self.logger.info("Service shutdown complete")
    
    async def verify_property(
        self,
        survey_no: str,
        village: str,
        hobli: str,
        district: str,
        owner_name: str,
        property_id: Optional[str] = None,
        khata_no: Optional[str] = None,
        rr_number: Optional[str] = None,
        connection_number: Optional[str] = None,
        property_address: Optional[str] = None
    ) -> None:
        """
        Execute complete property verification workflow.
        
        Args:
            survey_no: Survey number of the land
            village: Village name
            hobli: Hobli name
            district: District name (Bengaluru Urban or Rural)
            owner_name: Name of the property owner
            property_id: Property ID for BBMP (optional)
            khata_no: Khata number for BBMP (optional)
            rr_number: RR number for BESCOM (optional)
            connection_number: Connection number for BWSSB (optional)
            property_address: Property address for legal verification (optional)
        """
        self.logger.info("Starting property verification workflow")
        
        # Create verification request
        request = PropertyVerificationRequest(
            survey_no=survey_no,
            village=village,
            hobli=hobli,
            district=district,
            owner_name=owner_name,
            property_id=property_id,
            khata_no=khata_no,
            rr_number=rr_number,
            connection_number=connection_number,
            property_address=property_address
        )
        
        # Execute verification
        summary = await self.verification_orchestrator.verify_property(request)
        
        # Print formatted report
        self._print_verification_report(summary)
    
    def _print_verification_report(self, summary) -> None:
        """
        Print formatted verification report.
        
        Args:
            summary: VerificationSummary from orchestrator
        """
        print("\n" + "=" * 80)
        print("PROPERTY VERIFICATION REPORT")
        print("=" * 80)
        print(f"Request ID: {summary.request_id}")
        print(f"Verification Timestamp: {summary.verification_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Survey Number: {summary.request.survey_no}")
        print(f"Village: {summary.request.village}")
        print(f"Hobli: {summary.request.hobli}")
        print(f"District: {summary.request.district}")
        print(f"Owner Name: {summary.request.owner_name}")
        print("-" * 80)
        
        # Print individual verification results
        print("\nVERIFICATION RESULTS")
        print("-" * 80)
        
        # Ownership Verification
        bhoomi_result = summary.results.get('bhoomi')
        if bhoomi_result:
            print(f"\n1. OWNERSHIP VERIFICATION (Bhoomi RTC)")
            print(f"   Status: {'✓ SUCCESS' if bhoomi_result.success else '✗ FAILED'}")
            if bhoomi_result.success and bhoomi_result.data:
                print(f"   Owner Name: {bhoomi_result.data.get('owner_name', 'N/A')}")
                print(f"   Khata Number: {bhoomi_result.data.get('khata_no', 'N/A')}")
                print(f"   Land Use: {bhoomi_result.data.get('land_use', 'N/A')}")
                print(f"   Area: {bhoomi_result.data.get('area', 'N/A')}")
                print(f"   Mutation Status: {bhoomi_result.data.get('mutation_status', 'N/A')}")
            if bhoomi_result.error:
                print(f"   Error: {bhoomi_result.error}")
            if bhoomi_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in bhoomi_result.risk_flags])}")
        else:
            print(f"\n1. OWNERSHIP VERIFICATION (Bhoomi RTC)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Encumbrance Verification
        kaveri_result = summary.results.get('kaveri')
        if kaveri_result:
            print(f"\n2. ENCUMBRANCE VERIFICATION (Kaveri EC)")
            print(f"   Status: {'✓ SUCCESS' if kaveri_result.success else '✗ FAILED'}")
            if kaveri_result.success and kaveri_result.data:
                print(f"   Document Number: {kaveri_result.data.get('document_number', 'N/A')}")
                print(f"   Registration Date: {kaveri_result.data.get('registration_date', 'N/A')}")
                print(f"   Document Type: {kaveri_result.data.get('document_type', 'N/A')}")
                print(f"   Encumbrance Type: {kaveri_result.data.get('encumbrance_type', 'N/A')}")
                print(f"   SRO Name: {kaveri_result.data.get('sro_name', 'N/A')}")
            if kaveri_result.error:
                print(f"   Error: {kaveri_result.error}")
            if kaveri_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in kaveri_result.risk_flags])}")
        else:
            print(f"\n2. ENCUMBRANCE VERIFICATION (Kaveri EC)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Property Tax Verification
        bbmp_result = summary.results.get('bbmp')
        if bbmp_result:
            print(f"\n3. PROPERTY TAX VERIFICATION (BBMP)")
            print(f"   Status: {'✓ SUCCESS' if bbmp_result.success else '✗ FAILED'}")
            if bbmp_result.success and bbmp_result.data:
                print(f"   Property ID: {bbmp_result.data.get('property_id', 'N/A')}")
                print(f"   Owner Name: {bbmp_result.data.get('owner_name', 'N/A')}")
                print(f"   Khata Status: {bbmp_result.data.get('khata_status', 'N/A')}")
                print(f"   Tax Status: {bbmp_result.data.get('property_tax_status', 'N/A')}")
                print(f"   Pending Tax Amount: {bbmp_result.data.get('pending_tax_amount', 'N/A')}")
                print(f"   Zone: {bbmp_result.data.get('zone_name', 'N/A')}")
                print(f"   Ward: {bbmp_result.data.get('ward_number', 'N/A')}")
            if bbmp_result.error:
                print(f"   Error: {bbmp_result.error}")
            if bbmp_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in bbmp_result.risk_flags])}")
        else:
            print(f"\n3. PROPERTY TAX VERIFICATION (BBMP)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Electricity Verification
        bescom_result = summary.results.get('bescom')
        if bescom_result:
            print(f"\n4. ELECTRICITY VERIFICATION (BESCOM)")
            print(f"   Status: {'✓ SUCCESS' if bescom_result.success else '✗ FAILED'}")
            if bescom_result.success and bescom_result.data:
                print(f"   RR Number: {bescom_result.data.get('rr_number', 'N/A')}")
                print(f"   Consumer Name: {bescom_result.data.get('consumer_name', 'N/A')}")
                print(f"   Connection Status: {bescom_result.data.get('connection_status', 'N/A')}")
                print(f"   Outstanding Amount: {bescom_result.data.get('outstanding_amount', 'N/A')}")
                print(f"   Payment Status: {bescom_result.data.get('payment_status', 'N/A')}")
            if bescom_result.error:
                print(f"   Error: {bescom_result.error}")
            if bescom_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in bescom_result.risk_flags])}")
        else:
            print(f"\n4. ELECTRICITY VERIFICATION (BESCOM)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Water Verification
        bwssb_result = summary.results.get('bwssb')
        if bwssb_result:
            print(f"\n5. WATER VERIFICATION (BWSSB)")
            print(f"   Status: {'✓ SUCCESS' if bwssb_result.success else '✗ FAILED'}")
            if bwssb_result.success and bwssb_result.data:
                print(f"   Connection Number: {bwssb_result.data.get('connection_number', 'N/A')}")
                print(f"   Consumer Name: {bwssb_result.data.get('consumer_name', 'N/A')}")
                print(f"   Water Bill Status: {bwssb_result.data.get('water_bill_status', 'N/A')}")
                print(f"   Outstanding Amount: {bwssb_result.data.get('outstanding_amount', 'N/A')}")
                print(f"   Connection Status: {bwssb_result.data.get('connection_status', 'N/A')}")
            if bwssb_result.error:
                print(f"   Error: {bwssb_result.error}")
            if bwssb_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in bwssb_result.risk_flags])}")
        else:
            print(f"\n5. WATER VERIFICATION (BWSSB)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Litigation Verification
        ecourts_result = summary.results.get('ecourts')
        if ecourts_result:
            print(f"\n6. LITIGATION VERIFICATION (eCourts)")
            print(f"   Status: {'✓ SUCCESS' if ecourts_result.success else '✗ FAILED'}")
            if ecourts_result.success and ecourts_result.data:
                total_cases = ecourts_result.data.get('total_cases', 0)
                print(f"   Total Cases Found: {total_cases}")
                if total_cases > 0:
                    cases = ecourts_result.data.get('cases', [])
                    for i, case in enumerate(cases, 1):
                        print(f"   Case {i}:")
                        print(f"     Case Number: {case.get('case_number', 'N/A')}")
                        print(f"     Case Type: {case.get('case_type', 'N/A')}")
                        print(f"     Status: {case.get('status', 'N/A')}")
                        print(f"     Court: {case.get('court_name', 'N/A')}")
            if ecourts_result.error:
                print(f"   Error: {ecourts_result.error}")
            if ecourts_result.risk_flags:
                print(f"   Risk Flags: {', '.join([flag.value for flag in ecourts_result.risk_flags])}")
        else:
            print(f"\n6. LITIGATION VERIFICATION (eCourts)")
            print(f"   Status: ✗ NOT EXECUTED")
        
        # Print summary
        print("\n" + "-" * 80)
        print("VERIFICATION SUMMARY")
        print("-" * 80)
        print(f"Total Sources Checked: {summary.total_sources_checked}")
        print(f"Successful Verifications: {summary.successful_verifications}")
        print(f"Failed Verifications: {summary.failed_verifications}")
        
        # Print risk flags
        print("\nRISK FLAGS")
        print("-" * 80)
        if summary.all_risk_flags:
            for flag in summary.all_risk_flags:
                print(f"  • {flag.value}")
        else:
            print("  No risk flags detected")
        
        # Print overall risk level
        print("\nOVERALL RISK LEVEL")
        print("-" * 80)
        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴"
        }
        print(f"  {risk_emoji.get(summary.overall_risk_level, '')} {summary.overall_risk_level.value}")
        
        print("\n" + "=" * 80)
        print("END OF REPORT")
        print("=" * 80 + "\n")

    async def scrape_bhoomi(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape Bhoomi land records.
        
        Args:
            query_params: Dictionary containing search parameters
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting Bhoomi scrape with params: {query_params}")
        
        scraper = BhoomiScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"Bhoomi scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Bhoomi scrape failed: {e}", exc_info=True)
            raise
    
    async def scrape_kaveri(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape Kaveri land records.
        
        Args:
            query_params: Dictionary containing search parameters
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting Kaveri scrape with params: {query_params}")
        
        scraper = KaveriScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"Kaveri scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Kaveri scrape failed: {e}", exc_info=True)
            raise
    
    async def scrape_legal(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape legal land records from eCourts.
        
        Args:
            query_params: Dictionary containing search parameters
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting eCourts scrape with params: {query_params}")
        
        scraper = LegalScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"eCourts scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"eCourts scrape failed: {e}", exc_info=True)
            raise
    
    async def scrape_bbmp(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape BBMP property records.
        
        Args:
            query_params: Dictionary containing PID, zone, ward, etc.
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting BBMP scrape with params: {query_params}")
        
        scraper = BbmpScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"BBMP scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"BBMP scrape failed: {e}", exc_info=True)
            raise
    
    async def scrape_bescom(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape BESCOM electricity records.
        
        Args:
            query_params: Dictionary containing RR number, circle, etc.
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting BESCOM scrape with params: {query_params}")
        
        scraper = BescomScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"BESCOM scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"BESCOM scrape failed: {e}", exc_info=True)
            raise
    
    async def scrape_bwssb(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape BWSSB water records.
        
        Args:
            query_params: Dictionary containing RR number, zone, etc.
            
        Returns:
            Scraped data dictionary
        """
        self.logger.info(f"Starting BWSSB scrape with params: {query_params}")
        
        scraper = BwssbScraper({
            **self.settings.PORTALS,
            **self.settings.SCRAPER
        })
        
        try:
            result = await scraper.scrape(query_params)
            self.logger.info(f"BWSSB scrape completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"BWSSB scrape failed: {e}", exc_info=True)
            raise
    
    def validate_district(self, district: str) -> bool:
        """
        Validate district against supported districts.
        
        Args:
            district: District name to validate
            
        Returns:
            True if district is supported, False otherwise
        """
        return district in self.settings.SUPPORTED_DISTRICTS
    
    def validate_portal(self, portal: str) -> bool:
        """
        Validate portal against supported portals.
        
        Args:
            portal: Portal name to validate
            
        Returns:
            True if portal is supported, False otherwise
        """
        return portal.lower() in [p.lower() for p in self.settings.SUPPORTED_PORTALS]
    
    async def run_health_check(self) -> Dict[str, bool]:
        """
        Run health checks on all services.
        
        Returns:
            Dictionary with health status of each service
        """
        health_status = {
            'database': False,
            'cache': False,
            'scraper': True
        }
        
        # Database health check
        if self.db_connection:
            health_status['database'] = await self.db_connection.health_check()
        
        # Cache health check
        if self.cache_service:
            try:
                await self.cache_service.set('health_check', 'ok', ttl=10)
                value = await self.cache_service.get('health_check')
                health_status['cache'] = value == 'ok'
            except Exception:
                health_status['cache'] = False
        
        return health_status


async def main():
    """Main entry point."""
    service = ScrapingService()
    
    try:
        await service.initialize()
        
        # Check if property verification mode is requested
        if len(sys.argv) > 1 and sys.argv[1] == 'verify':
            # Property verification mode
            # Usage: python main.py verify <survey_no> <village> <hobli> <district> <owner_name>
            # Optional: <property_id> <khata_no> <rr_number> <connection_number> <property_address>
            
            survey_no = sys.argv[2] if len(sys.argv) > 2 else '123'
            village = sys.argv[3] if len(sys.argv) > 3 else '示例村'
            hobli = sys.argv[4] if len(sys.argv) > 4 else '示例Hobli'
            district = sys.argv[5] if len(sys.argv) > 5 else 'Bengaluru Urban'
            owner_name = sys.argv[6] if len(sys.argv) > 6 else 'John Doe'
            
            # Optional parameters
            property_id = sys.argv[7] if len(sys.argv) > 7 else None
            khata_no = sys.argv[8] if len(sys.argv) > 8 else None
            rr_number = sys.argv[9] if len(sys.argv) > 9 else None
            connection_number = sys.argv[10] if len(sys.argv) > 10 else None
            property_address = sys.argv[11] if len(sys.argv) > 11 else None
            
            # Validate district
            if not service.validate_district(district):
                print(f"Unsupported district: {district}")
                print(f"Supported districts: {', '.join(service.settings.SUPPORTED_DISTRICTS)}")
                return
            
            # Execute property verification
            await service.verify_property(
                survey_no=survey_no,
                village=village,
                hobli=hobli,
                district=district,
                owner_name=owner_name,
                property_id=property_id,
                khata_no=khata_no,
                rr_number=rr_number,
                connection_number=connection_number,
                property_address=property_address
            )
            
        elif len(sys.argv) > 1:
            # Legacy single scraper mode
            source = sys.argv[1].lower()
            
            # Validate portal
            if not service.validate_portal(source):
                print(f"Unsupported portal: {source}")
                print(f"Supported portals: {', '.join(service.settings.SUPPORTED_PORTALS)}")
                return
            
            # Build query params based on portal
            query_params = {}
            
            # Set default district
            district = sys.argv[2] if len(sys.argv) > 2 else service.settings.DEFAULT_DISTRICT
            if not service.validate_district(district):
                print(f"Unsupported district: {district}")
                print(f"Supported districts: {', '.join(service.settings.SUPPORTED_DISTRICTS)}")
                return
            query_params['district'] = district
            
            # Portal-specific parameters
            if source in ['bhoomi', 'kaveri']:
                query_params['taluk'] = sys.argv[3] if len(sys.argv) > 3 else 'Bengaluru North'
                query_params['survey_number'] = sys.argv[4] if len(sys.argv) > 4 else '123'
            elif source == 'bbmp':
                query_params['zone'] = sys.argv[3] if len(sys.argv) > 3 else 'South'
                query_params['pid'] = sys.argv[4] if len(sys.argv) > 4 else ''
            elif source == 'bescom':
                query_params['circle'] = sys.argv[3] if len(sys.argv) > 3 else 'Bangalore East'
                query_params['rr_number'] = sys.argv[4] if len(sys.argv) > 4 else ''
            elif source == 'bwssb':
                query_params['zone'] = sys.argv[3] if len(sys.argv) > 3 else 'South'
                query_params['rr_number'] = sys.argv[4] if len(sys.argv) > 4 else ''
            elif source == 'ecourts':
                query_params['case_number'] = sys.argv[3] if len(sys.argv) > 3 else ''
            
            # Route to appropriate scraper
            if source == 'bhoomi':
                result = await service.scrape_bhoomi(query_params)
            elif source == 'kaveri':
                result = await service.scrape_kaveri(query_params)
            elif source == 'ecourts':
                result = await service.scrape_legal(query_params)
            elif source == 'bbmp':
                result = await service.scrape_bbmp(query_params)
            elif source == 'bescom':
                result = await service.scrape_bescom(query_params)
            elif source == 'bwssb':
                result = await service.scrape_bwssb(query_params)
            
            print(f"Scraping result: {result}")
        else:
            # Default: Run sample property verification
            print("Running sample property verification...\n")
            await service.verify_property(
                survey_no='123',
                village='示例村',
                hobli='示例Hobli',
                district='Bengaluru Urban',
                owner_name='John Doe',
                property_id='PID-2024-001234',
                khata_no='KHA-12345',
                rr_number='RR-123456789',
                connection_number='CONN-123456789',
                property_address='123 Main St, Bengaluru'
            )
    
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
