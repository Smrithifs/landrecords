"""
Property Verification Orchestrator Service.

Provides a unified workflow for Bengaluru property verification by integrating
multiple government portal scrapers (Bhoomi, Kaveri, BBMP, BESCOM, BWSSB, eCourts).

This service orchestrates property verification across multiple data sources,
aggregates results, generates risk flags, and provides an overall risk assessment.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator

from utils.logger import get_default_logger


class RiskFlag(Enum):
    """Risk flags for property verification."""
    OWNERSHIP_MISMATCH = "OWNERSHIP_MISMATCH"
    ENCUMBRANCE_MISSING = "ENCUMBRANCE_MISSING"
    PROPERTY_TAX_DUE = "PROPERTY_TAX_DUE"
    ELECTRICITY_DUE = "ELECTRICITY_DUE"
    WATER_DUE = "WATER_DUE"
    ACTIVE_LITIGATION = "ACTIVE_LITIGATION"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"


class RiskLevel(Enum):
    """Overall risk levels for property verification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PropertyVerificationRequest(BaseModel):
    """
    Unified request model for property verification.
    
    Contains all necessary parameters to verify a property across multiple sources.
    """
    # Bhoomi RTC parameters
    survey_no: str = Field(..., description="Survey number of the land")
    village: str = Field(..., description="Village name")
    hobli: str = Field(..., description="Hobli name")
    district: str = Field(..., description="District name (Bengaluru Urban or Rural)")
    
    # Owner information (used across multiple sources)
    owner_name: str = Field(..., description="Name of the property owner")
    
    # BBMP parameters
    property_id: Optional[str] = Field(None, description="Property ID for BBMP")
    khata_no: Optional[str] = Field(None, description="Khata number for BBMP")
    
    # BESCOM parameters
    rr_number: Optional[str] = Field(None, description="RR number for BESCOM")
    
    # BWSSB parameters
    connection_number: Optional[str] = Field(None, description="Connection number for BWSSB")
    
    # Property address (for eCourts)
    property_address: Optional[str] = Field(None, description="Property address for legal verification")
    
    @field_validator('district')
    @classmethod
    def validate_district(cls, v):
        """Validate district is within supported scope."""
        supported_districts = ["Bengaluru Urban", "Bengaluru Rural"]
        if v not in supported_districts:
            raise ValueError(f"District must be one of: {supported_districts}")
        return v
    
    @field_validator('survey_no')
    @classmethod
    def validate_survey_no(cls, v):
        """Validate survey number is not empty."""
        if not v or not v.strip():
            raise ValueError("Survey number cannot be empty")
        return v.strip()
    
    @field_validator('owner_name')
    @classmethod
    def validate_owner_name(cls, v):
        """Validate owner name is not empty."""
        if not v or not v.strip():
            raise ValueError("Owner name cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "survey_no": "123",
                "village": "示例村",
                "hobli": "示例Hobli",
                "district": "Bengaluru Urban",
                "owner_name": "John Doe",
                "property_id": "PID-2024-001234",
                "khata_no": "KHA-12345",
                "rr_number": "RR-123456789",
                "connection_number": "CONN-123456789",
                "property_address": "123 Main St, Bengaluru"
            }
        }


@dataclass
class VerificationResult:
    """
    Result from a single verification source.
    
    Contains the raw data from the scraper, success status, and any risk flags.
    """
    source: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    risk_flags: List[RiskFlag] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "risk_flags": [flag.value for flag in self.risk_flags],
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class VerificationSummary:
    """
    Aggregated summary of all verification results.
    
    Contains results from all sources, overall risk assessment, and recommendations.
    """
    request_id: str
    request: PropertyVerificationRequest
    results: Dict[str, VerificationResult] = field(default_factory=dict)
    overall_risk_level: RiskLevel = RiskLevel.LOW
    all_risk_flags: List[RiskFlag] = field(default_factory=list)
    verification_timestamp: datetime = field(default_factory=datetime.utcnow)
    total_sources_checked: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "request": self.request.dict(),
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "overall_risk_level": self.overall_risk_level.value,
            "all_risk_flags": [flag.value for flag in self.all_risk_flags],
            "verification_timestamp": self.verification_timestamp.isoformat(),
            "total_sources_checked": self.total_sources_checked,
            "successful_verifications": self.successful_verifications,
            "failed_verifications": self.failed_verifications
        }


class PropertyVerificationOrchestrator:
    """
    Orchestrator for Bengaluru property verification workflow.
    
    This service integrates multiple scrapers to provide comprehensive property
    verification including land ownership, encumbrance, property tax, utilities,
    and legal disputes.
    
    Features:
    - Async execution for parallel scraping where possible
    - Dependency injection for scrapers and services
    - Comprehensive logging at each step
    - Risk flag generation based on verification results
    - Overall risk level calculation
    - Production-ready error handling
    """
    
    def __init__(
        self,
        bhoomi_scraper: Optional[Any] = None,
        kaveri_scraper: Optional[Any] = None,
        bbmp_scraper: Optional[Any] = None,
        bescom_scraper: Optional[Any] = None,
        bwssb_scraper: Optional[Any] = None,
        ecourts_scraper: Optional[Any] = None,
        logger: Optional[Any] = None
    ) -> None:
        """
        Initialize the Property Verification Orchestrator.
        
        Args:
            bhoomi_scraper: BhoomiRTCScraper instance (optional)
            kaveri_scraper: KaveriECScraper instance (optional)
            bbmp_scraper: BBMPScraper instance (optional)
            bescom_scraper: BESCOMScraper instance (optional)
            bwssb_scraper: BWSSBScraper instance (optional)
            ecourts_scraper: ECourtsScraper instance (optional)
            logger: Logger instance (optional)
        """
        self.bhoomi_scraper = bhoomi_scraper
        self.kaveri_scraper = kaveri_scraper
        self.bbmp_scraper = bbmp_scraper
        self.bescom_scraper = bescom_scraper
        self.bwssb_scraper = bwssb_scraper
        self.ecourts_scraper = ecourts_scraper
        
        self.logger = logger or get_default_logger()
        self.logger.info("PropertyVerificationOrchestrator initialized")
    
    async def verify_property(
        self,
        request: PropertyVerificationRequest,
        request_id: Optional[str] = None
    ) -> VerificationSummary:
        """
        Execute the complete property verification workflow.
        
        This method orchestrates verification across all configured sources,
        aggregates results, generates risk flags, and calculates overall risk level.
        
        Args:
            request: PropertyVerificationRequest with verification parameters
            request_id: Optional unique identifier for this verification request
            
        Returns:
            VerificationSummary with aggregated results and risk assessment
        """
        if not request_id:
            request_id = f"VER-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.logger.info(f"Starting property verification: {request_id}")
        self.logger.info(f"Verification parameters: survey_no={request.survey_no}, "
                        f"village={request.village}, owner={request.owner_name}")
        
        summary = VerificationSummary(
            request_id=request_id,
            request=request
        )
        
        try:
            # Execute verification steps
            await self._verify_land_ownership(request, summary)
            await self._verify_encumbrance(request, summary)
            await self._verify_property_tax(request, summary)
            await self._verify_electricity(request, summary)
            await self._verify_water(request, summary)
            await self._verify_legal_disputes(request, summary)
            
            # Calculate overall risk level
            self._calculate_overall_risk(summary)
            
            # Update statistics
            summary.total_sources_checked = len(summary.results)
            summary.successful_verifications = sum(
                1 for r in summary.results.values() if r.success
            )
            summary.failed_verifications = summary.total_sources_checked - summary.successful_verifications
            
            self.logger.info(f"Property verification completed: {request_id}")
            self.logger.info(f"Overall risk level: {summary.overall_risk_level.value}")
            self.logger.info(f"Sources checked: {summary.total_sources_checked}, "
                            f"Successful: {summary.successful_verifications}, "
                            f"Failed: {summary.failed_verifications}")
            
        except Exception as e:
            self.logger.error(f"Property verification failed: {request_id}, error: {e}", exc_info=True)
            summary.results["orchestrator_error"] = VerificationResult(
                source="orchestrator",
                success=False,
                error=str(e)
            )
        
        return summary
    
    async def _verify_land_ownership(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify land ownership through Bhoomi RTC.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 1: Verifying land ownership through Bhoomi RTC")
        
        if not self.bhoomi_scraper:
            self.logger.warning("Bhoomi scraper not configured, skipping ownership verification")
            summary.results["bhoomi"] = VerificationResult(
                source="bhoomi",
                success=False,
                error="Scraper not configured",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        try:
            from scrapers.models import BhoomiRTCInput
            
            input_data = BhoomiRTCInput(
                survey_no=request.survey_no,
                village=request.village,
                hobli=request.hobli,
                district=request.district
            )
            
            result = await self.bhoomi_scraper.scrape(input_data)
            
            if result and result.owner_name:
                # Check for ownership mismatch
                risk_flags = []
                if result.owner_name.lower() != request.owner_name.lower():
                    risk_flags.append(RiskFlag.OWNERSHIP_MISMATCH)
                    self.logger.warning(f"Ownership mismatch: Bhoomi={result.owner_name}, "
                                       f"Request={request.owner_name}")
                
                summary.results["bhoomi"] = VerificationResult(
                    source="bhoomi",
                    success=True,
                    data=result.dict(),
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info("Bhoomi RTC verification completed successfully")
            else:
                summary.results["bhoomi"] = VerificationResult(
                    source="bhoomi",
                    success=False,
                    error="No ownership data found",
                    risk_flags=[RiskFlag.RECORD_NOT_FOUND]
                )
                summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
                self.logger.warning("Bhoomi RTC verification failed: No ownership data found")
                
        except Exception as e:
            self.logger.error(f"Bhoomi RTC verification error: {e}", exc_info=True)
            summary.results["bhoomi"] = VerificationResult(
                source="bhoomi",
                success=False,
                error=str(e),
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
    
    async def _verify_encumbrance(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify encumbrance through Kaveri EC.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 2: Verifying encumbrance through Kaveri EC")
        
        if not self.kaveri_scraper:
            self.logger.warning("Kaveri scraper not configured, skipping encumbrance verification")
            summary.results["kaveri"] = VerificationResult(
                source="kaveri",
                success=False,
                error="Scraper not configured",
                risk_flags=[RiskFlag.ENCUMBRANCE_MISSING]
            )
            summary.all_risk_flags.append(RiskFlag.ENCUMBRANCE_MISSING)
            return
        
        try:
            query_params = {
                "survey_no": request.survey_no,
                "village": request.village,
                "owner_name": request.owner_name
            }
            
            result = await self.kaveri_scraper.scrape(query_params)
            
            if result and not result.get('error'):
                # Check if encumbrance data is present
                risk_flags = []
                if not result.get('document_number'):
                    risk_flags.append(RiskFlag.ENCUMBRANCE_MISSING)
                    self.logger.warning("No encumbrance document found")
                
                summary.results["kaveri"] = VerificationResult(
                    source="kaveri",
                    success=True,
                    data=result,
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info("Kaveri EC verification completed successfully")
            else:
                summary.results["kaveri"] = VerificationResult(
                    source="kaveri",
                    success=False,
                    error=result.get('error', 'No encumbrance data found'),
                    risk_flags=[RiskFlag.ENCUMBRANCE_MISSING]
                )
                summary.all_risk_flags.append(RiskFlag.ENCUMBRANCE_MISSING)
                self.logger.warning(f"Kaveri EC verification failed: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Kaveri EC verification error: {e}", exc_info=True)
            summary.results["kaveri"] = VerificationResult(
                source="kaveri",
                success=False,
                error=str(e),
                risk_flags=[RiskFlag.ENCUMBRANCE_MISSING]
            )
            summary.all_risk_flags.append(RiskFlag.ENCUMBRANCE_MISSING)
    
    async def _verify_property_tax(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify property tax through BBMP.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 3: Verifying property tax through BBMP")
        
        if not self.bbmp_scraper:
            self.logger.warning("BBMP scraper not configured, skipping property tax verification")
            summary.results["bbmp"] = VerificationResult(
                source="bbmp",
                success=False,
                error="Scraper not configured",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        if not request.property_id or not request.khata_no:
            self.logger.warning("BBMP parameters missing, skipping property tax verification")
            summary.results["bbmp"] = VerificationResult(
                source="bbmp",
                success=False,
                error="Missing property_id or khata_no",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        try:
            from scrapers.models import BBMPPropertyInput
            
            input_data = BBMPPropertyInput(
                property_id=request.property_id,
                khata_no=request.khata_no,
                owner_name=request.owner_name
            )
            
            result = await self.bbmp_scraper.scrape(input_data)
            
            if result:
                # Check for property tax due
                risk_flags = []
                if result.pending_tax_amount and float(result.pending_tax_amount or 0) > 0:
                    risk_flags.append(RiskFlag.PROPERTY_TAX_DUE)
                    self.logger.warning(f"Property tax due: {result.pending_tax_amount}")
                
                summary.results["bbmp"] = VerificationResult(
                    source="bbmp",
                    success=True,
                    data=result.dict(),
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info("BBMP property tax verification completed successfully")
            else:
                summary.results["bbmp"] = VerificationResult(
                    source="bbmp",
                    success=False,
                    error="No property tax data found",
                    risk_flags=[RiskFlag.RECORD_NOT_FOUND]
                )
                summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
                self.logger.warning("BBMP property tax verification failed: No data found")
                
        except Exception as e:
            self.logger.error(f"BBMP property tax verification error: {e}", exc_info=True)
            summary.results["bbmp"] = VerificationResult(
                source="bbmp",
                success=False,
                error=str(e),
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
    
    async def _verify_electricity(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify electricity records through BESCOM.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 4: Verifying electricity records through BESCOM")
        
        if not self.bescom_scraper:
            self.logger.warning("BESCOM scraper not configured, skipping electricity verification")
            summary.results["bescom"] = VerificationResult(
                source="bescom",
                success=False,
                error="Scraper not configured",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        if not request.rr_number:
            self.logger.warning("BESCOM RR number missing, skipping electricity verification")
            summary.results["bescom"] = VerificationResult(
                source="bescom",
                success=False,
                error="Missing rr_number",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        try:
            from scrapers.models import BESCOMInput
            
            input_data = BESCOMInput(
                rr_number=request.rr_number,
                owner_name=request.owner_name
            )
            
            result = await self.bescom_scraper.scrape(input_data)
            
            if result:
                # Check for electricity dues
                risk_flags = []
                if result.outstanding_amount and float(result.outstanding_amount or 0) > 0:
                    risk_flags.append(RiskFlag.ELECTRICITY_DUE)
                    self.logger.warning(f"Electricity due: {result.outstanding_amount}")
                
                summary.results["bescom"] = VerificationResult(
                    source="bescom",
                    success=True,
                    data=result.dict(),
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info("BESCOM electricity verification completed successfully")
            else:
                summary.results["bescom"] = VerificationResult(
                    source="bescom",
                    success=False,
                    error="No electricity data found",
                    risk_flags=[RiskFlag.RECORD_NOT_FOUND]
                )
                summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
                self.logger.warning("BESCOM electricity verification failed: No data found")
                
        except Exception as e:
            self.logger.error(f"BESCOM electricity verification error: {e}", exc_info=True)
            summary.results["bescom"] = VerificationResult(
                source="bescom",
                success=False,
                error=str(e),
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
    
    async def _verify_water(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify water records through BWSSB.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 5: Verifying water records through BWSSB")
        
        if not self.bwssb_scraper:
            self.logger.warning("BWSSB scraper not configured, skipping water verification")
            summary.results["bwssb"] = VerificationResult(
                source="bwssb",
                success=False,
                error="Scraper not configured",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        if not request.connection_number:
            self.logger.warning("BWSSB connection number missing, skipping water verification")
            summary.results["bwssb"] = VerificationResult(
                source="bwssb",
                success=False,
                error="Missing connection_number",
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
            return
        
        try:
            from scrapers.models import BWSSBInput
            
            input_data = BWSSBInput(
                connection_number=request.connection_number,
                owner_name=request.owner_name
            )
            
            result = await self.bwssb_scraper.scrape(input_data)
            
            if result:
                # Check for water dues
                risk_flags = []
                if result.outstanding_amount and float(result.outstanding_amount or 0) > 0:
                    risk_flags.append(RiskFlag.WATER_DUE)
                    self.logger.warning(f"Water bill due: {result.outstanding_amount}")
                
                summary.results["bwssb"] = VerificationResult(
                    source="bwssb",
                    success=True,
                    data=result.dict(),
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info("BWSSB water verification completed successfully")
            else:
                summary.results["bwssb"] = VerificationResult(
                    source="bwssb",
                    success=False,
                    error="No water data found",
                    risk_flags=[RiskFlag.RECORD_NOT_FOUND]
                )
                summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
                self.logger.warning("BWSSB water verification failed: No data found")
                
        except Exception as e:
            self.logger.error(f"BWSSB water verification error: {e}", exc_info=True)
            summary.results["bwssb"] = VerificationResult(
                source="bwssb",
                success=False,
                error=str(e),
                risk_flags=[RiskFlag.RECORD_NOT_FOUND]
            )
            summary.all_risk_flags.append(RiskFlag.RECORD_NOT_FOUND)
    
    async def _verify_legal_disputes(
        self,
        request: PropertyVerificationRequest,
        summary: VerificationSummary
    ) -> None:
        """
        Verify legal disputes through eCourts.
        
        Args:
            request: PropertyVerificationRequest
            summary: VerificationSummary to update
        """
        self.logger.info("Step 6: Verifying legal disputes through eCourts")
        
        if not self.ecourts_scraper:
            self.logger.warning("eCourts scraper not configured, skipping legal verification")
            summary.results["ecourts"] = VerificationResult(
                source="ecourts",
                success=False,
                error="Scraper not configured"
            )
            return
        
        if not request.property_address:
            self.logger.warning("Property address missing, skipping legal verification")
            summary.results["ecourts"] = VerificationResult(
                source="ecourts",
                success=False,
                error="Missing property_address"
            )
            return
        
        try:
            from scrapers.models import ECourtsInput
            
            input_data = ECourtsInput(
                owner_name=request.owner_name,
                survey_no=request.survey_no,
                property_address=request.property_address
            )
            
            results = await self.ecourts_scraper.scrape(input_data)
            
            if results:
                # Check for active litigation
                risk_flags = []
                active_cases = [r for r in results if r.status and r.status.lower() in ['pending', 'active']]
                if active_cases:
                    risk_flags.append(RiskFlag.ACTIVE_LITIGATION)
                    self.logger.warning(f"Active litigation found: {len(active_cases)} cases")
                
                summary.results["ecourts"] = VerificationResult(
                    source="ecourts",
                    success=True,
                    data={"cases": [r.dict() for r in results], "total_cases": len(results)},
                    risk_flags=risk_flags
                )
                summary.all_risk_flags.extend(risk_flags)
                self.logger.info(f"eCourts legal verification completed successfully. "
                               f"Found {len(results)} cases")
            else:
                summary.results["ecourts"] = VerificationResult(
                    source="ecourts",
                    success=True,
                    data={"cases": [], "total_cases": 0},
                    risk_flags=[]
                )
                self.logger.info("eCourts legal verification completed successfully. No cases found")
                
        except Exception as e:
            self.logger.error(f"eCourts legal verification error: {e}", exc_info=True)
            summary.results["ecourts"] = VerificationResult(
                source="ecourts",
                success=False,
                error=str(e)
            )
    
    def _calculate_overall_risk(self, summary: VerificationSummary) -> None:
        """
        Calculate overall risk level based on aggregated risk flags.
        
        Risk level calculation:
        - HIGH: Ownership mismatch, active litigation, or 3+ critical flags
        - MEDIUM: 1-2 critical flags or 3+ moderate flags
        - LOW: No critical flags and fewer than 3 moderate flags
        
        Args:
            summary: VerificationSummary to update
        """
        critical_flags = {
            RiskFlag.OWNERSHIP_MISMATCH,
            RiskFlag.ACTIVE_LITIGATION
        }
        
        moderate_flags = {
            RiskFlag.ENCUMBRANCE_MISSING,
            RiskFlag.PROPERTY_TAX_DUE,
            RiskFlag.ELECTRICITY_DUE,
            RiskFlag.WATER_DUE
        }
        
        critical_count = sum(1 for flag in summary.all_risk_flags if flag in critical_flags)
        moderate_count = sum(1 for flag in summary.all_risk_flags if flag in moderate_flags)
        
        self.logger.info(f"Risk flag analysis: Critical={critical_count}, Moderate={moderate_count}")
        
        if critical_count >= 1 or (critical_count + moderate_count) >= 3:
            summary.overall_risk_level = RiskLevel.HIGH
            self.logger.warning("Overall risk level: HIGH")
        elif critical_count == 0 and moderate_count >= 1:
            summary.overall_risk_level = RiskLevel.MEDIUM
            self.logger.info("Overall risk level: MEDIUM")
        else:
            summary.overall_risk_level = RiskLevel.LOW
            self.logger.info("Overall risk level: LOW")
    
    async def verify_property_parallel(
        self,
        request: PropertyVerificationRequest,
        request_id: Optional[str] = None
    ) -> VerificationSummary:
        """
        Execute property verification with parallel execution where possible.
        
        This method runs independent verification steps in parallel to improve
        performance. Dependencies are still respected (e.g., ownership must be
        verified before checking for ownership mismatch in other sources).
        
        Args:
            request: PropertyVerificationRequest with verification parameters
            request_id: Optional unique identifier for this verification request
            
        Returns:
            VerificationSummary with aggregated results and risk assessment
        """
        if not request_id:
            request_id = f"VER-PARALLEL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.logger.info(f"Starting parallel property verification: {request_id}")
        
        summary = VerificationSummary(
            request_id=request_id,
            request=request
        )
        
        try:
            # Step 1: Verify ownership (must be done first)
            await self._verify_land_ownership(request, summary)
            
            # Steps 2-6: Run in parallel where independent
            tasks = [
                self._verify_encumbrance(request, summary),
                self._verify_property_tax(request, summary),
                self._verify_electricity(request, summary),
                self._verify_water(request, summary),
                self._verify_legal_disputes(request, summary)
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Calculate overall risk level
            self._calculate_overall_risk(summary)
            
            # Update statistics
            summary.total_sources_checked = len(summary.results)
            summary.successful_verifications = sum(
                1 for r in summary.results.values() if r.success
            )
            summary.failed_verifications = summary.total_sources_checked - summary.successful_verifications
            
            self.logger.info(f"Parallel property verification completed: {request_id}")
            self.logger.info(f"Overall risk level: {summary.overall_risk_level.value}")
            
        except Exception as e:
            self.logger.error(f"Parallel property verification failed: {request_id}, error: {e}", exc_info=True)
            summary.results["orchestrator_error"] = VerificationResult(
                source="orchestrator",
                success=False,
                error=str(e)
            )
        
        return summary
