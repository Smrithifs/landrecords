"""
Utility functions for scrapers.
Common helper functions used across different scrapers.
"""

from typing import Dict, Any, List
import re


def clean_text(text: str) -> str:
    """
    Clean and normalize text data.
    
    Args:
        text: Raw text string
        
    Returns:
        Cleaned text string
    """
    if not text:
        return ''
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove special characters if needed
    text = re.sub(r'[^\w\s\-.,]', '', text)
    return text.strip()


def parse_extent(extent_str: str) -> Dict[str, float]:
    """
    Parse land extent string into structured data.
    
    Args:
        extent_str: String containing extent information (e.g., "2 acres 3 guntas")
        
    Returns:
        Dictionary with parsed extent values
    """
    extent = {'acres': 0.0, 'guntas': 0.0, 'sqft': 0.0}
    
    # Parse acres
    acres_match = re.search(r'(\d+\.?\d*)\s*acres?', extent_str, re.IGNORECASE)
    if acres_match:
        extent['acres'] = float(acres_match.group(1))
    
    # Parse guntas
    guntas_match = re.search(r'(\d+\.?\d*)\s*guntas?', extent_str, re.IGNORECASE)
    if guntas_match:
        extent['guntas'] = float(guntas_match.group(1))
    
    # Parse sqft
    sqft_match = re.search(r'(\d+\.?\d*)\s*sq\.?ft', extent_str, re.IGNORECASE)
    if sqft_match:
        extent['sqft'] = float(sqft_match.group(1))
    
    return extent


def validate_survey_number(survey_number: str) -> bool:
    """
    Validate survey number format.
    
    Args:
        survey_number: Survey number string
        
    Returns:
        True if valid, False otherwise
    """
    if not survey_number:
        return False
    # Basic validation - can be enhanced based on specific formats
    return bool(re.match(r'^[\d/\-A-Za-z]+$', survey_number))


def normalize_owner_name(name: str) -> str:
    """
    Normalize owner name for consistency.
    
    Args:
        name: Owner name string
        
    Returns:
        Normalized name string
    """
    if not name:
        return ''
    # Convert to title case
    name = name.title()
    # Remove extra spaces
    name = ' '.join(name.split())
    return name


def extract_encumbrance_details(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract and structure encumbrance details.
    
    Args:
        data: Raw data dictionary
        
    Returns:
        List of structured encumbrance records
    """
    encumbrances = []
    # Placeholder for extraction logic
    return encumbrances


def format_land_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format land record for consistent output.
    
    Args:
        record: Raw land record dictionary
        
    Returns:
        Formatted land record dictionary
    """
    formatted = {
        'survey_number': clean_text(record.get('survey_number', '')),
        'owner_name': normalize_owner_name(record.get('owner_name', '')),
        'extent': parse_extent(record.get('extent', '')),
        'land_type': clean_text(record.get('land_type', '')),
        'source': record.get('source', ''),
        'scraped_at': record.get('scraped_at', '')
    }
    return formatted
