"""
Database models for land records.
Defines SQLAlchemy models for storing scraped data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class LandRecord(Base):
    """Model for land record data."""
    
    __tablename__ = 'land_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_number = Column(String(100), nullable=False, index=True)
    owner_name = Column(String(255), nullable=False)
    district = Column(String(100), nullable=False)
    taluk = Column(String(100), nullable=False)
    hobli = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)
    extent_acres = Column(Float, nullable=True)
    extent_guntas = Column(Float, nullable=True)
    extent_sqft = Column(Float, nullable=True)
    land_type = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False)  # bhoomi, kaveri, legal
    raw_data = Column(JSON, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    encumbrances = relationship("Encumbrance", back_populates="land_record", cascade="all, delete-orphan")
    mutations = relationship("Mutation", back_populates="land_record", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<LandRecord(survey_number='{self.survey_number}', owner='{self.owner_name}')>"


class Encumbrance(Base):
    """Model for encumbrance details."""
    
    __tablename__ = 'encumbrances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    land_record_id = Column(Integer, ForeignKey('land_records.id'), nullable=False)
    encumbrance_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    date = Column(DateTime, nullable=True)
    amount = Column(Float, nullable=True)
    parties_involved = Column(JSON, nullable=True)
    document_number = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    land_record = relationship("LandRecord", back_populates="encumbrances")
    
    def __repr__(self):
        return f"<Encumbrance(type='{self.encumbrance_type}', date='{self.date}')>"


class Mutation(Base):
    """Model for mutation details."""
    
    __tablename__ = 'mutations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    land_record_id = Column(Integer, ForeignKey('land_records.id'), nullable=False)
    mutation_number = Column(String(100), nullable=False)
    mutation_type = Column(String(100), nullable=False)
    old_owner = Column(String(255), nullable=True)
    new_owner = Column(String(255), nullable=True)
    mutation_date = Column(DateTime, nullable=True)
    registration_date = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    land_record = relationship("LandRecord", back_populates="mutations")
    
    def __repr__(self):
        return f"<Mutation(number='{self.mutation_number}', type='{self.mutation_type}')>"


class LegalCase(Base):
    """Model for legal case records."""
    
    __tablename__ = 'legal_cases'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_number = Column(String(100), nullable=False, unique=True, index=True)
    case_type = Column(String(100), nullable=True)
    court_name = Column(String(255), nullable=True)
    district = Column(String(100), nullable=True)
    filing_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True)
    parties = Column(JSON, nullable=True)
    survey_numbers = Column(JSON, nullable=True)  # Linked survey numbers
    hearings = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<LegalCase(number='{self.case_number}', status='{self.status}')>"


class ScrapeLog(Base):
    """Model for logging scrape operations."""
    
    __tablename__ = 'scrape_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    query_params = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)  # success, failed, partial
    error_message = Column(Text, nullable=True)
    records_found = Column(Integer, default=0)
    records_saved = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ScrapeLog(source='{self.source}', status='{self.status}')>"


class ProxyUsage(Base):
    """Model for tracking proxy usage."""
    
    __tablename__ = 'proxy_usage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    proxy_host = Column(String(255), nullable=False)
    proxy_port = Column(Integer, nullable=False)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ProxyUsage(host='{self.proxy_host}', port={self.proxy_port})>"


class BhoomiRTC(Base):
    """Model for Bhoomi RTC records."""
    
    __tablename__ = 'bhoomi_rtc'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(100), nullable=False)
    taluk = Column(String(100), nullable=False)
    hobli = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)
    survey_no = Column(String(100), nullable=False, index=True)
    hissa_no = Column(String(50), nullable=True)
    owner_name = Column(String(255), nullable=True)
    khata_no = Column(String(100), nullable=True)
    land_use = Column(String(100), nullable=True)
    soil_type = Column(String(100), nullable=True)
    area_dryland_acres = Column(String(50), nullable=True)
    area_wetland_acres = Column(String(50), nullable=True)
    area_total_acres = Column(String(50), nullable=True)
    encumbrances_text = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<BhoomiRTC(survey_no='{self.survey_no}', owner='{self.owner_name}')>"


class ScraperHealth(Base):
    """Model for tracking scraper health metrics."""
    
    __tablename__ = 'scraper_health'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    portal = Column(String(50), nullable=False, unique=True, index=True)  # bhoomi, kaveri, bbmp
    total_attempts = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ScraperHealth(portal='{self.portal}', success_rate={self.success_rate})>"
    
    @property
    def success_rate(self):
        if self.total_attempts == 0:
            return 0.0
        return (self.success_count / self.total_attempts) * 100
