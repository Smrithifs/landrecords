"""
SRO (Sub-Registrar Office) Mapping for Bengaluru.
Provides mapping between villages, hoblis, and SRO offices for property registration.
Supports Bengaluru Urban and Bengaluru Rural districts with future Karnataka expansion.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from enum import Enum

from database.models import Base
from database.connection import get_database
from utils.logger import get_default_logger


class DistrictEnum(str, Enum):
    """Supported districts for SRO mapping."""
    BENGALURU_URBAN = "Bengaluru Urban"
    BENGALURU_RURAL = "Bengaluru Rural"
    # Future Karnataka expansion
    # MYSORE = "Mysore"
    # HUBBALLI = "Hubballi"


class SROOffice(Base):
    """
    SQLAlchemy model for Sub-Registrar Office.
    
    Represents a Sub-Registrar Office where property registrations are conducted.
    """
    
    __tablename__ = 'sro_offices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sro_code = Column(String(20), unique=True, nullable=False, index=True, comment="Unique SRO code")
    sro_name = Column(String(255), nullable=False, comment="Name of the SRO office")
    district = Column(String(100), nullable=False, index=True, comment="District name")
    taluk = Column(String(100), nullable=True, comment="Taluk name")
    address = Column(Text, nullable=True, comment="Office address")
    pincode = Column(String(10), nullable=True, comment="PIN code")
    phone = Column(String(20), nullable=True, comment="Office phone number")
    email = Column(String(255), nullable=True, comment="Office email")
    jurisdiction_area = Column(Text, nullable=True, comment="Description of jurisdiction area")
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether SRO is active")
    latitude = Column(String(20), nullable=True, comment="Latitude for geolocation")
    longitude = Column(String(20), nullable=True, comment="Longitude for geolocation")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    village_mappings = relationship("VillageSROMapping", back_populates="sro_office", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SROOffice(code='{self.sro_code}', name='{self.sro_name}', district='{self.district}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SRO office to dictionary."""
        return {
            'id': self.id,
            'sro_code': self.sro_code,
            'sro_name': self.sro_name,
            'district': self.district,
            'taluk': self.taluk,
            'address': self.address,
            'pincode': self.pincode,
            'phone': self.phone,
            'email': self.email,
            'jurisdiction_area': self.jurisdiction_area,
            'is_active': self.is_active,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class VillageSROMapping(Base):
    """
    SQLAlchemy model for Village to SRO mapping.
    
    Maps villages and hoblis to their respective SRO offices for property registration.
    """
    
    __tablename__ = 'village_sro_mappings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sro_office_id = Column(Integer, ForeignKey('sro_offices.id'), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True, comment="District name")
    taluk = Column(String(100), nullable=True, index=True, comment="Taluk name")
    hobli = Column(String(100), nullable=True, index=True, comment="Hobli name")
    village = Column(String(255), nullable=False, index=True, comment="Village name")
    village_code = Column(String(20), nullable=True, comment="Village code")
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether mapping is active")
    effective_from = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Effective date from")
    effective_to = Column(DateTime, nullable=True, comment="Effective date to")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sro_office = relationship("SROOffice", back_populates="village_mappings")
    
    # Composite indexes for efficient lookups
    __table_args__ = (
        Index('idx_district_village', 'district', 'village'),
        Index('idx_hobli_village', 'hobli', 'village'),
        Index('idx_taluk_village', 'taluk', 'village'),
    )
    
    def __repr__(self):
        return f"<VillageSROMapping(village='{self.village}', hobli='{self.hobli}', sro_id={self.sro_office_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert village mapping to dictionary."""
        return {
            'id': self.id,
            'sro_office_id': self.sro_office_id,
            'district': self.district,
            'taluk': self.taluk,
            'hobli': self.hobli,
            'village': self.village,
            'village_code': self.village_code,
            'is_active': self.is_active,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class SROMappingService:
    """
    Service for managing SRO (Sub-Registrar Office) mappings.
    
    Provides CRUD operations and lookup functions for village-to-SRO mappings
    with cache integration for performance optimization.
    """
    
    def __init__(self, cache_service: Optional[Any] = None):
        """
        Initialize SRO mapping service.
        
        Args:
            cache_service: Optional cache service instance
        """
        self.cache_service = cache_service
        self.logger = get_default_logger()
        self.cache_ttl = 86400  # 24 hours
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """
        Generate cache key for SRO lookups.
        
        Args:
            prefix: Cache key prefix
            **kwargs: Key-value pairs for cache key
            
        Returns:
            Cache key string
        """
        parts = [prefix]
        for key, value in sorted(kwargs.items()):
            if value:
                parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    async def create_sro_office(
        self,
        sro_code: str,
        sro_name: str,
        district: str,
        taluk: Optional[str] = None,
        address: Optional[str] = None,
        pincode: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        jurisdiction_area: Optional[str] = None,
        latitude: Optional[str] = None,
        longitude: Optional[str] = None
    ) -> SROOffice:
        """
        Create a new SRO office.
        
        Args:
            sro_code: Unique SRO code
            sro_name: Name of the SRO office
            district: District name
            taluk: Optional taluk name
            address: Optional office address
            pincode: Optional PIN code
            phone: Optional office phone
            email: Optional office email
            jurisdiction_area: Optional jurisdiction description
            latitude: Optional latitude
            longitude: Optional longitude
            
        Returns:
            Created SROOffice instance
        """
        db = await get_database()
        
        async with db.get_session() as session:
            sro_office = SROOffice(
                sro_code=sro_code,
                sro_name=sro_name,
                district=district,
                taluk=taluk,
                address=address,
                pincode=pincode,
                phone=phone,
                email=email,
                jurisdiction_area=jurisdiction_area,
                latitude=latitude,
                longitude=longitude
            )
            
            session.add(sro_office)
            await session.commit()
            await session.refresh(sro_office)
            
            self.logger.info(f"Created SRO office: {sro_code} - {sro_name}")
            
            # Invalidate relevant cache
            cache_key = self._generate_cache_key("sro", district=district)
            if self.cache_service:
                await self.cache_service.delete(cache_key)
            
            return sro_office
    
    async def get_sro_office(self, sro_code: str) -> Optional[SROOffice]:
        """
        Get SRO office by code.
        
        Args:
            sro_code: SRO code
            
        Returns:
            SROOffice instance or None
        """
        db = await get_database()
        
        cache_key = self._generate_cache_key("sro_office", code=sro_code)
        
        # Check cache first
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                return cached
        
        async with db.get_session() as session:
            sro_office = await session.query(SROOffice).filter(
                SROOffice.sro_code == sro_code
            ).first()
            
            if sro_office and self.cache_service:
                await self.cache_service.set(cache_key, sro_office, ttl=self.cache_ttl)
            
            return sro_office
    
    async def create_village_mapping(
        self,
        sro_office_id: int,
        district: str,
        village: str,
        taluk: Optional[str] = None,
        hobli: Optional[str] = None,
        village_code: Optional[str] = None
    ) -> VillageSROMapping:
        """
        Create a village to SRO mapping.
        
        Args:
            sro_office_id: ID of the SRO office
            district: District name
            village: Village name
            taluk: Optional taluk name
            hobli: Optional hobli name
            village_code: Optional village code
            
        Returns:
            Created VillageSROMapping instance
        """
        db = await get_database()
        
        async with db.get_session() as session:
            mapping = VillageSROMapping(
                sro_office_id=sro_office_id,
                district=district,
                taluk=taluk,
                hobli=hobli,
                village=village,
                village_code=village_code
            )
            
            session.add(mapping)
            await session.commit()
            await session.refresh(mapping)
            
            self.logger.info(f"Created village mapping: {village} -> SRO ID {sro_office_id}")
            
            # Invalidate relevant caches
            cache_keys = [
                self._generate_cache_key("sro_by_village", district=district, village=village),
                self._generate_cache_key("sro_by_hobli", district=district, hobli=hobli),
                self._generate_cache_key("sro_by_taluk", district=district, taluk=taluk)
            ]
            
            if self.cache_service:
                for key in cache_keys:
                    await self.cache_service.delete(key)
            
            return mapping
    
    async def get_sro_by_village(self, district: str, village: str) -> Optional[Dict[str, Any]]:
        """
        Get SRO office by village name.
        
        Args:
            district: District name
            village: Village name
            
        Returns:
            Dictionary with SRO office details or None
        """
        db = await get_database()
        
        cache_key = self._generate_cache_key("sro_by_village", district=district, village=village)
        
        # Check cache first
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                self.logger.debug(f"Cache hit for village lookup: {village}")
                return cached
        
        async with db.get_session() as session:
            mapping = await session.query(VillageSROMapping).filter(
                VillageSROMapping.district == district,
                VillageSROMapping.village == village,
                VillageSROMapping.is_active == True
            ).first()
            
            if mapping:
                sro_office = await session.query(SROOffice).filter(
                    SROOffice.id == mapping.sro_office_id,
                    SROOffice.is_active == True
                ).first()
                
                if sro_office:
                    result = sro_office.to_dict()
                    result['mapping'] = mapping.to_dict()
                    
                    if self.cache_service:
                        await self.cache_service.set(cache_key, result, ttl=self.cache_ttl)
                    
                    self.logger.info(f"Found SRO for village {village}: {sro_office.sro_name}")
                    return result
            
            self.logger.warning(f"No SRO found for village: {village} in district: {district}")
            return None
    
    async def get_sro_by_hobli(self, district: str, hobli: str) -> Optional[Dict[str, Any]]:
        """
        Get SRO office by hobli name.
        
        Args:
            district: District name
            hobli: Hobli name
            
        Returns:
            Dictionary with SRO office details or None
        """
        db = await get_database()
        
        cache_key = self._generate_cache_key("sro_by_hobli", district=district, hobli=hobli)
        
        # Check cache first
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                self.logger.debug(f"Cache hit for hobli lookup: {hobli}")
                return cached
        
        async with db.get_session() as session:
            mapping = await session.query(VillageSROMapping).filter(
                VillageSROMapping.district == district,
                VillageSROMapping.hobli == hobli,
                VillageSROMapping.is_active == True
            ).first()
            
            if mapping:
                sro_office = await session.query(SROOffice).filter(
                    SROOffice.id == mapping.sro_office_id,
                    SROOffice.is_active == True
                ).first()
                
                if sro_office:
                    result = sro_office.to_dict()
                    result['mapping'] = mapping.to_dict()
                    
                    if self.cache_service:
                        await self.cache_service.set(cache_key, result, ttl=self.cache_ttl)
                    
                    self.logger.info(f"Found SRO for hobli {hobli}: {sro_office.sro_name}")
                    return result
            
            self.logger.warning(f"No SRO found for hobli: {hobli} in district: {district}")
            return None
    
    async def get_sro_by_property(
        self,
        district: str,
        village: str,
        survey_no: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get SRO office by property details (village and survey number).
        
        Args:
            district: District name
            village: Village name
            survey_no: Optional survey number for validation
            
        Returns:
            Dictionary with SRO office details or None
        """
        # For now, use village-based lookup
        # Survey number validation can be added in future
        return await self.get_sro_by_village(district, village)
    
    async def get_all_sro_offices(self, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all SRO offices, optionally filtered by district.
        
        Args:
            district: Optional district filter
            
        Returns:
            List of SRO office dictionaries
        """
        db = await get_database()
        
        cache_key = self._generate_cache_key("all_sro", district=district or "all")
        
        # Check cache first
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                self.logger.debug(f"Cache hit for all SRO offices")
                return cached
        
        async with db.get_session() as session:
            query = session.query(SROOffice).filter(SROOffice.is_active == True)
            
            if district:
                query = query.filter(SROOffice.district == district)
            
            sro_offices = await query.all()
            result = [sro.to_dict() for sro in sro_offices]
            
            if self.cache_service:
                await self.cache_service.set(cache_key, result, ttl=self.cache_ttl)
            
            return result
    
    async def update_sro_office(
        self,
        sro_code: str,
        **kwargs
    ) -> Optional[SROOffice]:
        """
        Update SRO office details.
        
        Args:
            sro_code: SRO code
            **kwargs: Fields to update
            
        Returns:
            Updated SROOffice instance or None
        """
        db = await get_database()
        
        async with db.get_session() as session:
            sro_office = await session.query(SROOffice).filter(
                SROOffice.sro_code == sro_code
            ).first()
            
            if sro_office:
                for key, value in kwargs.items():
                    if hasattr(sro_office, key):
                        setattr(sro_office, key, value)
                
                sro_office.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(sro_office)
                
                self.logger.info(f"Updated SRO office: {sro_code}")
                
                # Invalidate cache
                cache_key = self._generate_cache_key("sro_office", code=sro_code)
                if self.cache_service:
                    await self.cache_service.delete(cache_key)
                
                return sro_office
            
            return None
    
    async def delete_sro_office(self, sro_code: str) -> bool:
        """
        Soft delete SRO office (mark as inactive).
        
        Args:
            sro_code: SRO code
            
        Returns:
            True if deleted, False otherwise
        """
        db = await get_database()
        
        async with db.get_session() as session:
            sro_office = await session.query(SROOffice).filter(
                SROOffice.sro_code == sro_code
            ).first()
            
            if sro_office:
                sro_office.is_active = False
                sro_office.updated_at = datetime.utcnow()
                await session.commit()
                
                self.logger.info(f"Deactivated SRO office: {sro_code}")
                
                # Invalidate cache
                cache_key = self._generate_cache_key("sro_office", code=sro_code)
                if self.cache_service:
                    await self.cache_service.delete(cache_key)
                
                return True
            
            return False


# Bengaluru SRO office metadata for initialization
BENGALURU_SRO_OFFICES = [
    {
        "sro_code": "SRO-BLR-RAJ",
        "sro_name": "SRO Rajajinagar",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru North",
        "address": "Rajajinagar, Bengaluru",
        "pincode": "560010",
        "jurisdiction_area": "Rajajinagar, Malleshwaram, Yeshwanthpur areas"
    },
    {
        "sro_code": "SRO-BLR-JAY",
        "sro_name": "SRO Jayanagar",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru South",
        "address": "Jayanagar, Bengaluru",
        "pincode": "560041",
        "jurisdiction_area": "Jayanagar, Basavanagudi, JP Nagar areas"
    },
    {
        "sro_code": "SRO-BLR-SHI",
        "sro_name": "SRO Shivajinagar",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru Central",
        "address": "Shivajinagar, Bengaluru",
        "pincode": "560051",
        "jurisdiction_area": "Shivajinagar, Cantonment, Vasanth Nagar areas"
    },
    {
        "sro_code": "SRO-BLR-IND",
        "sro_name": "SRO Indiranagar",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru East",
        "address": "Indiranagar, Bengaluru",
        "pincode": "560038",
        "jurisdiction_area": "Indiranagar, Domlur, Koramangala areas"
    },
    {
        "sro_code": "SRO-BLR-YEL",
        "sro_name": "SRO Yelahanka",
        "district": "Bengaluru Urban",
        "taluk": "Yelahanka",
        "address": "Yelahanka, Bengaluru",
        "pincode": "560063",
        "jurisdiction_area": "Yelahanka, Doddaballapur, Devanahalli areas"
    },
    {
        "sro_code": "SRO-BLR-KEN",
        "sro_name": "SRO Kengeri",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru West",
        "address": "Kengeri, Bengaluru",
        "pincode": "560060",
        "jurisdiction_area": "Kengeri, Rajarajeshwari Nagar, Nagarbhavi areas"
    },
    {
        "sro_code": "SRO-BLR-ANE",
        "sro_name": "SRO Anekal",
        "district": "Bengaluru Urban",
        "taluk": "Anekal",
        "address": "Anekal, Bengaluru",
        "pincode": "562106",
        "jurisdiction_area": "Anekal, Jigani, Electronic City areas"
    },
    {
        "sro_code": "SRO-BLR-ELE",
        "sro_name": "SRO Electronic City",
        "district": "Bengaluru Urban",
        "taluk": "Anekal",
        "address": "Electronic City, Bengaluru",
        "pincode": "560100",
        "jurisdiction_area": "Electronic City, Chandapura, Attibele areas"
    },
    {
        "sro_code": "SRO-BLR-DEV",
        "sro_name": "SRO Devanahalli",
        "district": "Bengaluru Rural",
        "taluk": "Devanahalli",
        "address": "Devanahalli, Bengaluru Rural",
        "pincode": "562110",
        "jurisdiction_area": "Devanahalli, Doddaballapur, Nelamangala areas"
    },
    {
        "sro_code": "SRO-BLR-HOS",
        "sro_name": "SRO Hoskote",
        "district": "Bengaluru Rural",
        "taluk": "Hoskote",
        "address": "Hoskote, Bengaluru Rural",
        "pincode": "562114",
        "jurisdiction_area": "Hoskote, Whitefield, K R Puram areas"
    },
    {
        "sro_code": "SRO-BLR-WHI",
        "sro_name": "SRO Whitefield",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru East",
        "address": "Whitefield, Bengaluru",
        "pincode": "560066",
        "jurisdiction_area": "Whitefield, Kadugodi, Hoodi areas"
    },
    {
        "sro_code": "SRO-BLR-KRP",
        "sro_name": "SRO K R Puram",
        "district": "Bengaluru Urban",
        "taluk": "Bengaluru East",
        "address": "K R Puram, Bengaluru",
        "pincode": "560016",
        "jurisdiction_area": "K R Puram, Mahadevapura, Ramamurthy Nagar areas"
    }
]


async def initialize_bengaluru_sro_data(service: SROMappingService) -> None:
    """
    Initialize Bengaluru SRO office data.
    
    Args:
        service: SROMappingService instance
    """
    logger = get_default_logger()
    logger.info("Initializing Bengaluru SRO office data...")
    
    for sro_data in BENGALURU_SRO_OFFICES:
        try:
            existing = await service.get_sro_office(sro_data['sro_code'])
            if not existing:
                await service.create_sro_office(**sro_data)
                logger.info(f"Created SRO office: {sro_data['sro_code']}")
            else:
                logger.debug(f"SRO office already exists: {sro_data['sro_code']}")
        except Exception as e:
            logger.error(f"Error creating SRO office {sro_data['sro_code']}: {e}")
    
    logger.info("Bengaluru SRO office data initialization completed")
