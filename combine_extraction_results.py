#!/usr/bin/env python3
"""
Combine scraper output and Gemini extraction results.
Merges the structured kn/en format from scraper with the complete data from Gemini.
"""

import json
from pathlib import Path

# Input files
SCRAPER_OUTPUT = "logs/debug/bhoomi_public_result.json"
GEMINI_OUTPUT = "logs/debug/gemini_extraction.json"
COMBINED_OUTPUT = "logs/debug/combined_rtc_result.json"

def combine_results():
    """Combine scraper and Gemini extraction results."""
    
    # Load both files
    with open(SCRAPER_OUTPUT, 'r', encoding='utf-8') as f:
        scraper_data = json.load(f)
    
    with open(GEMINI_OUTPUT, 'r', encoding='utf-8') as f:
        gemini_data = json.load(f)
    
    # Get the rtc_document from scraper
    rtc_doc = scraper_data.get('rtc_document', {})
    
    # Merge Gemini data into scraper structure
    # Helper function to update a field with Gemini data
    def update_field(field_path, gemini_value):
        """Update a nested field in rtc_doc with Gemini value."""
        current = rtc_doc
        keys = field_path.split('.')
        
        # Navigate to the parent of the target field
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Update the target field
        last_key = keys[-1]
        if last_key in current:
            # If field exists and is empty, fill it
            if isinstance(current[last_key], dict):
                if not current[last_key].get('en'):
                    current[last_key]['en'] = gemini_value
                    current[last_key]['kn'] = gemini_value
            elif not current[last_key]:
                current[last_key] = gemini_value
        else:
            # Field doesn't exist, add it
            current[last_key] = gemini_value
    
    # Merge basic fields
    field_mappings = {
        'split_up_details.total_area': 'total_area',
        'split_up_details.phut_kharab_a': 'phut_kharab_a',
        'split_up_details.phut_kharab_b': 'phut_kharab_b',
        'split_up_details.remainder': 'remainder',
        'land_revenue.land_revenue': 'land_revenue',
        'land_revenue.jodi': 'jodi',
        'land_revenue.cess': 'cess',
        'land_revenue.water_rate': 'water_rate',
        'land_revenue.total': 'total_revenue',
        'soil_type': 'soil_type',
        'patta': 'patta',
        'occupant.name': 'occupant_name',
        'occupant.area': 'occupant_area',
        'occupant.khata_no': 'khata_no',
        'possession_nature': 'possession_nature',
    }
    
    for scraper_field, gemini_field in field_mappings.items():
        if gemini_field in gemini_data and gemini_data[gemini_field]:
            update_field(scraper_field, gemini_data[gemini_field])
    
    # Merge cultivation details
    if 'cultivation_details' in gemini_data and gemini_data['cultivation_details']:
        # Convert Gemini cultivation details to scraper format
        cultivation_rows = []
        for detail in gemini_data['cultivation_details']:
            row_text = f"{detail.get('year_season', '')} - {detail.get('cultivator_name', '')} - {detail.get('cultivation_method', '')} - {detail.get('land_use', '')}"
            cultivation_rows.append({
                "kn": row_text,
                "en": row_text,
                "needs_review": False
            })
        rtc_doc['cultivation_rows'] = cultivation_rows
    
    # Add source metadata
    rtc_doc['_metadata'] = {
        "scraper_source": "bhoomi_public_scraper.py",
        "gemini_source": "gemini-2.5-flash API",
        "merge_timestamp": "2026-08-09"
    }
    
    # Create combined result
    combined_result = {
        "rtc_document": rtc_doc,
        "full_rtc_html": scraper_data.get('full_rtc_html', ''),
        "gemini_extraction": gemini_data
    }
    
    # Save combined result
    output_path = Path(COMBINED_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined_result, f, indent=2, ensure_ascii=False)
    
    print(f"Combined results saved to {COMBINED_OUTPUT}")
    print(json.dumps(combined_result, indent=2, ensure_ascii=False))
    
    return combined_result

if __name__ == "__main__":
    combine_results()
