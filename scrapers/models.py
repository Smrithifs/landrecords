"""
Pydantic models for scraper output validation.
Structured data models for land record scrapers.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class BhoomiRTCInput(BaseModel):
    """Input model for Bhoomi RTC scraper."""
    
    survey_no: str = Field(..., description="Survey number of the land")
    village: str = Field(..., description="Village name")
    hobli: str = Field(..., description="Hobli name")
    district: str = Field(..., description="District name")
    
    @field_validator('district')
    @classmethod
    def validate_district(cls, v):
        """Validate district is within supported scope."""
        supported_districts = ["Bengaluru Urban", "Bengaluru Rural"]
        if v not in supported_districts:
            raise ValueError(f"District must be one of: {supported_districts}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "survey_no": "123",
                "village": "示例村",
                "hobli": "示例Hobli",
                "district": "Bengaluru Urban"
            }
        }


class BhoomiRTCOutput(BaseModel):
    """Output model for Bhoomi RTC scraper."""
    
    owner_name: Optional[str] = Field(None, description="Name of the land owner")
    khata_no: Optional[str] = Field(None, description="Khata number")
    survey_no: str = Field(..., description="Survey number of the land")
    land_use: Optional[str] = Field(None, description="Land use classification")
    area: Optional[str] = Field(None, description="Land area with units")
    mutation_status: Optional[str] = Field(None, description="Mutation status of the land")
    village: str = Field(..., description="Village name")
    hobli: str = Field(..., description="Hobli name")
    district: str = Field(..., description="District name")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BhoomiRTC", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "owner_name": "John Doe",
                "khata_no": "KHA-12345",
                "survey_no": "123",
                "land_use": "Agricultural",
                "area": "2.5 acres",
                "mutation_status": "Completed",
                "village": "示例村",
                "hobli": "示例Hobli",
                "district": "Bengaluru Urban",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "BhoomiRTC"
            }
        }


class BbmpPropertyInput(BaseModel):
    """Input model for BBMP property scraper."""
    
    pid: str = Field(..., description="Property Identification Number")
    zone: str = Field(..., description="BBMP zone")
    ward: Optional[str] = Field(None, description="Ward number")
    
    @field_validator('zone')
    @classmethod
    def validate_zone(cls, v):
        """Validate zone is within BBMP zones."""
        valid_zones = ["North", "South", "East", "West", "Mahadevapura", "Bommanahalli", "Yelahanka"]
        if v not in valid_zones:
            raise ValueError(f"Zone must be one of: {valid_zones}")
        return v


class BbmpPropertyOutput(BaseModel):
    """Output model for BBMP property scraper."""
    
    pid: str = Field(..., description="Property Identification Number")
    owner_name: Optional[str] = Field(None, description="Name of the property owner")
    property_address: Optional[str] = Field(None, description="Property address")
    zone: str = Field(..., description="BBMP zone")
    ward: Optional[str] = Field(None, description="Ward number")
    property_type: Optional[str] = Field(None, description="Property type")
    built_up_area: Optional[str] = Field(None, description="Built-up area")
    tax_amount: Optional[str] = Field(None, description="Current tax amount")
    arrears: Optional[str] = Field(None, description="Tax arrears")
    assessment_year: Optional[str] = Field(None, description="Assessment year")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BBMP", description="Data source")


class BBMPPropertyInput(BaseModel):
    """Input model for BBMP property tax scraper."""
    
    property_id: str = Field(..., description="Property ID")
    khata_no: str = Field(..., description="Khata number")
    owner_name: str = Field(..., description="Owner name")
    
    @field_validator('property_id')
    @classmethod
    def validate_property_id(cls, v):
        """Validate property ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Property ID cannot be empty")
        return v.strip()
    
    @field_validator('khata_no')
    @classmethod
    def validate_khata_no(cls, v):
        """Validate khata number is not empty."""
        if not v or not v.strip():
            raise ValueError("Khata number cannot be empty")
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
                "property_id": "PID-2024-001234",
                "khata_no": "KHA-12345",
                "owner_name": "John Doe"
            }
        }


class BBMPPropertyOutput(BaseModel):
    """Output model for BBMP property tax scraper."""
    
    property_id: str = Field(..., description="Property ID")
    owner_name: Optional[str] = Field(None, description="Owner name")
    khata_status: Optional[str] = Field(None, description="Khata status")
    property_tax_status: Optional[str] = Field(None, description="Property tax status")
    pending_tax_amount: Optional[str] = Field(None, description="Pending tax amount")
    ward_number: Optional[str] = Field(None, description="Ward number")
    zone_name: Optional[str] = Field(None, description="Zone name")
    last_payment_date: Optional[str] = Field(None, description="Last payment date")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BBMP", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "property_id": "PID-2024-001234",
                "owner_name": "John Doe",
                "khata_status": "Active",
                "property_tax_status": "Paid",
                "pending_tax_amount": "0",
                "ward_number": "45",
                "zone_name": "East",
                "last_payment_date": "2024-01-15",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "BBMP"
            }
        }


class BescomElectricityInput(BaseModel):
    """Input model for BESCOM electricity scraper."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    circle: str = Field(..., description="BESCOM circle")
    
    @field_validator('circle')
    @classmethod
    def validate_circle(cls, v):
        """Validate circle is within BESCOM circles."""
        valid_circles = ["Bangalore East", "Bangalore West", "Bangalore South", "Bangalore North"]
        if v not in valid_circles:
            raise ValueError(f"Circle must be one of: {valid_circles}")
        return v


class BescomElectricityOutput(BaseModel):
    """Output model for BESCOM electricity scraper."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    consumer_name: Optional[str] = Field(None, description="Consumer name")
    address: Optional[str] = Field(None, description="Service address")
    circle: str = Field(..., description="BESCOM circle")
    division: Optional[str] = Field(None, description="Division")
    sub_division: Optional[str] = Field(None, description="Sub-division")
    tariff: Optional[str] = Field(None, description="Tariff category")
    connected_load: Optional[str] = Field(None, description="Connected load")
    current_bill_amount: Optional[str] = Field(None, description="Current bill amount")
    due_date: Optional[str] = Field(None, description="Payment due date")
    payment_status: Optional[str] = Field(None, description="Payment status")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BESCOM", description="Data source")


class BESCOMInput(BaseModel):
    """Input model for BESCOM electricity scraper (Bengaluru)."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    owner_name: str = Field(..., description="Owner name")
    
    @field_validator('rr_number')
    @classmethod
    def validate_rr_number(cls, v):
        """Validate RR number is not empty."""
        if not v or not v.strip():
            raise ValueError("RR number cannot be empty")
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
                "rr_number": "RR-123456789",
                "owner_name": "John Doe"
            }
        }


class BESCOMOutput(BaseModel):
    """Output model for BESCOM electricity scraper (Bengaluru)."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    consumer_name: Optional[str] = Field(None, description="Consumer name")
    connection_status: Optional[str] = Field(None, description="Connection status")
    outstanding_amount: Optional[str] = Field(None, description="Outstanding amount")
    last_bill_date: Optional[str] = Field(None, description="Last bill date")
    payment_status: Optional[str] = Field(None, description="Payment status")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BESCOM", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "rr_number": "RR-123456789",
                "consumer_name": "John Doe",
                "connection_status": "Active",
                "outstanding_amount": "1500.00",
                "last_bill_date": "2024-01-15",
                "payment_status": "Paid",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "BESCOM"
            }
        }


class BwssbWaterInput(BaseModel):
    """Input model for BWSSB water scraper."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    zone: str = Field(..., description="BWSSB zone")
    
    @field_validator('zone')
    @classmethod
    def validate_zone(cls, v):
        """Validate zone is within BWSSB zones."""
        valid_zones = ["Central", "East", "West", "South", "North", "Yelahanka", "Mahadevapura", "Bommanahalli"]
        if v not in valid_zones:
            raise ValueError(f"Zone must be one of: {valid_zones}")
        return v


class BwssbWaterOutput(BaseModel):
    """Output model for BWSSB water scraper."""
    
    rr_number: str = Field(..., description="Revenue Register number")
    consumer_name: Optional[str] = Field(None, description="Consumer name")
    address: Optional[str] = Field(None, description="Service address")
    zone: str = Field(..., description="BWSSB zone")
    sub_division: Optional[str] = Field(None, description="Sub-division")
    meter_number: Optional[str] = Field(None, description="Meter number")
    connection_type: Optional[str] = Field(None, description="Connection type")
    current_bill_amount: Optional[str] = Field(None, description="Current bill amount")
    due_date: Optional[str] = Field(None, description="Payment due date")
    payment_status: Optional[str] = Field(None, description="Payment status")
    water_consumption: Optional[str] = Field(None, description="Water consumption")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BWSSB", description="Data source")


class BWSSBInput(BaseModel):
    """Input model for BWSSB water scraper (Bengaluru)."""
    
    connection_number: str = Field(..., description="Connection number")
    owner_name: str = Field(..., description="Owner name")
    
    @field_validator('connection_number')
    @classmethod
    def validate_connection_number(cls, v):
        """Validate connection number is not empty."""
        if not v or not v.strip():
            raise ValueError("Connection number cannot be empty")
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
                "connection_number": "CONN-123456789",
                "owner_name": "John Doe"
            }
        }


class BWSSBOutput(BaseModel):
    """Output model for BWSSB water scraper (Bengaluru)."""
    
    connection_number: str = Field(..., description="Connection number")
    consumer_name: Optional[str] = Field(None, description="Consumer name")
    water_bill_status: Optional[str] = Field(None, description="Water bill status")
    outstanding_amount: Optional[str] = Field(None, description="Outstanding amount")
    last_payment_date: Optional[str] = Field(None, description="Last payment date")
    connection_status: Optional[str] = Field(None, description="Connection status")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="BWSSB", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "connection_number": "CONN-123456789",
                "consumer_name": "John Doe",
                "water_bill_status": "Paid",
                "outstanding_amount": "0",
                "last_payment_date": "2024-01-15",
                "connection_status": "Active",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "BWSSB"
            }
        }


class KaveriECInput(BaseModel):
    """Input model for Kaveri EC (Encumbrance Certificate) scraper."""
    
    survey_no: str = Field(..., description="Survey number of the land")
    village: str = Field(..., description="Village name")
    owner_name: str = Field(..., description="Name of the property owner")
    
    @field_validator('survey_no')
    @classmethod
    def validate_survey_no(cls, v):
        """Validate survey number is not empty."""
        if not v or not v.strip():
            raise ValueError("Survey number cannot be empty")
        return v.strip()
    
    @field_validator('village')
    @classmethod
    def validate_village(cls, v):
        """Validate village is not empty."""
        if not v or not v.strip():
            raise ValueError("Village cannot be empty")
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
                "owner_name": "John Doe"
            }
        }


class KaveriECOutput(BaseModel):
    """Output model for Kaveri EC (Encumbrance Certificate) scraper."""
    
    document_number: Optional[str] = Field(None, description="Document registration number")
    registration_date: Optional[str] = Field(None, description="Date of registration")
    document_type: Optional[str] = Field(None, description="Type of document (e.g., Sale, Gift, Mortgage)")
    seller: Optional[str] = Field(None, description="Name of the seller/transferor")
    buyer: Optional[str] = Field(None, description="Name of the buyer/transferee")
    transaction_amount: Optional[str] = Field(None, description="Transaction amount")
    encumbrance_type: Optional[str] = Field(None, description="Type of encumbrance")
    sro_name: Optional[str] = Field(None, description="Sub-Registrar Office name")
    survey_no: str = Field(..., description="Survey number of the land")
    village: str = Field(..., description="Village name")
    owner_name: str = Field(..., description="Name of the property owner")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="KaveriEC", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "document_number": "DOC-2024-001234",
                "registration_date": "2024-01-15",
                "document_type": "Sale",
                "seller": "Previous Owner",
                "buyer": "Current Owner",
                "transaction_amount": "5000000",
                "encumbrance_type": "Sale Deed",
                "sro_name": "SRO Bengaluru North",
                "survey_no": "123",
                "village": "示例村",
                "owner_name": "John Doe",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "KaveriEC"
            }
        }


class ECourtsInput(BaseModel):
    """Input model for eCourts legal case scraper (Bengaluru)."""
    
    owner_name: str = Field(..., description="Owner name")
    survey_no: str = Field(..., description="Survey number")
    property_address: str = Field(..., description="Property address")
    
    @field_validator('owner_name')
    @classmethod
    def validate_owner_name(cls, v):
        """Validate owner name is not empty."""
        if not v or not v.strip():
            raise ValueError("Owner name cannot be empty")
        return v.strip()
    
    @field_validator('survey_no')
    @classmethod
    def validate_survey_no(cls, v):
        """Validate survey number is not empty."""
        if not v or not v.strip():
            raise ValueError("Survey number cannot be empty")
        return v.strip()
    
    @field_validator('property_address')
    @classmethod
    def validate_property_address(cls, v):
        """Validate property address is not empty."""
        if not v or not v.strip():
            raise ValueError("Property address cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "owner_name": "John Doe",
                "survey_no": "123",
                "property_address": "123 Main St, Bengaluru"
            }
        }


class ECourtsOutput(BaseModel):
    """Output model for eCourts legal case scraper (Bengaluru)."""
    
    case_number: Optional[str] = Field(None, description="Case number")
    case_type: Optional[str] = Field(None, description="Case type")
    filing_date: Optional[str] = Field(None, description="Filing date")
    status: Optional[str] = Field(None, description="Case status")
    next_hearing_date: Optional[str] = Field(None, description="Next hearing date")
    court_name: Optional[str] = Field(None, description="Court name")
    dispute_category: Optional[str] = Field(None, description="Dispute category")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of scraping")
    source: str = Field(default="eCourts", description="Data source")
    
    class Config:
        schema_extra = {
            "example": {
                "case_number": "CASE-2024-001234",
                "case_type": "Civil Suit",
                "filing_date": "2024-01-15",
                "status": "Pending",
                "next_hearing_date": "2024-03-15",
                "court_name": "City Civil Court Bengaluru",
                "dispute_category": "Property Dispute",
                "scraped_at": "2024-01-01T00:00:00",
                "source": "eCourts"
            }
        }


class KarnatakaHCInput(BaseModel):
    """Input model for Karnataka High Court party-name search (Bengaluru Bench)."""
    
    owner_name: str = Field(..., description="Owner / party name to search (English)")
    bench: str = Field(default="B", description="Bench code: B=Bengaluru, D=Dharwad, K=Kalaburagi")
    case_types: List[str] = Field(default_factory=lambda: ["WP", "CP.KLRA", "LRRP", "RFA", "RSA", "CRP", "WA"],
                                  description="Case types to check (High Court of Karnataka case-type codes)")
    pet_res_code: str = Field(default="0", description="Party role code: 1=Petitioner, 2=Respondent, 0=Don't Know")
    filing_from: str = Field(default="01-08-2025", description="Filing date from (DD-MM-YYYY)")
    filing_to: str = Field(default="01-08-2026", description="Filing date to (DD-MM-YYYY)")
    aliases: Optional[List[str]] = Field(default=None, description="Optional alias variants of the owner name to try")
    survey_no: Optional[str] = Field(None, description="Optional survey number (metadata only, for risk reporting)")
    property_address: Optional[str] = Field(None, description="Optional property address (metadata only, for risk reporting)")

    @field_validator('owner_name')
    @classmethod
    def validate_owner_name(cls, v):
        if not v or not v.strip():
            raise ValueError("owner_name cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "owner_name": "Gali Hanumayya",
                "bench": "B",
                "case_types": ["WP", "RFA", "CRP"],
                "pet_res_code": "0",
                "filing_from": "01-08-2025",
                "filing_to": "01-08-2026",
                "aliases": ["Hanumayya Gali", "Hanumayya"],
                "survey_no": "123",
                "property_address": "Jayanagar, Bengaluru"
            }
        }


class KarnatakaHCCase(BaseModel):
    """Structured case row from Karnataka HC search results."""
    case_number: Optional[str] = Field(None, description="Case number (e.g. WP 12345/2025)")
    case_type: Optional[str] = Field(None, description="Case type code (WP, RFA, etc.)")
    filing_date: Optional[str] = Field(None, description="Date of filing")
    status: Optional[str] = Field(None, description="Current status / stage")
    next_hearing_date: Optional[str] = Field(None, description="Next date of hearing")
    bench: Optional[str] = Field(None, description="Bench / judge info")
    subject: Optional[str] = Field(None, description="Subject / category")
    petitioner: Optional[str] = Field(None, description="Petitioner name(s)")
    respondent: Optional[str] = Field(None, description="Respondent name(s)")
    advocate_petitioner: Optional[str] = Field(None, description="Petitioner advocate")
    advocate_respondent: Optional[str] = Field(None, description="Respondent advocate")
    raw_row: Dict[str, str] = Field(default_factory=dict, description="Raw key-value pairs from the HTML table row")


class KarnatakaHCOutput(BaseModel):
    """Aggregated output from Karnataka HC search for one owner."""
    owner_name: str = Field(..., description="Primary owner name that was searched")
    bench_code: str = Field(..., description="Bench code used")
    bench_label: str = Field(..., description="Bench label (e.g. Bengaluru Bench)")
    filing_from: str = Field(..., description="Filing date range start")
    filing_to: str = Field(..., description="Filing date range end")
    case_types_checked: List[str] = Field(default_factory=list, description="Case type codes checked")
    aliases_tried: List[str] = Field(default_factory=list, description="Alias variants searched")
    total_cases_found: int = Field(0, description="Total case rows detected across all searches")
    distinct_cases: List[KarnatakaHCCase] = Field(default_factory=list, description="Deduplicated structured case list")
    has_active_litigation: bool = Field(False, description="True if at least one case row found (not 'No Record')")
    no_record_case_types: List[str] = Field(default_factory=list, description="Case type searches that explicitly returned 'No Record'")
    per_case_type_summary: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Case counts per case_type code")
    search_summaries: List[Dict[str, Any]] = Field(default_factory=list, description="Raw per-search records from the scraper")
    extraction_errors: List[str] = Field(default_factory=list, description="Errors encountered during scraping")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when run finished")
    source: str = Field(default="KarnatakaHC", description="Data source label")

    class Config:
        schema_extra = {
            "example": {
                "owner_name": "Gali Hanumayya",
                "bench_code": "B",
                "bench_label": "Bengaluru Bench",
                "filing_from": "01-08-2025",
                "filing_to": "01-08-2026",
                "case_types_checked": ["WP"],
                "aliases_tried": ["Gali Hanumayya"],
                "total_cases_found": 1,
                "distinct_cases": [
                    {
                        "case_number": "WP 10001/2025",
                        "case_type": "WP",
                        "status": "Pending",
                        "next_hearing_date": "15-09-2025",
                    }
                ],
                "has_active_litigation": True,
                "no_record_case_types": [],
            }
        }
