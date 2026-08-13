#!/usr/bin/env python3
"""
Extract RTC data from uploaded screenshots using OCR.
Uses pytesseract to extract text and parse RTC fields.
"""

import pytesseract
from PIL import Image
import json
from pathlib import Path
import re

# Bilingual dictionaries (from reference)
RTC_LABELS_KN_EN = {
    "ಸರ್ವೆ ನಂಬರು": "Survey Number",
    "ಹಿಸ್ಸಾ": "Hissa (Sub-division)",
    "ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ": "Total Area",
    "ಪೂಟ್ ಖರಾಬ್ (ಅ)": "Phut Kharab (A)",
    "ಪೂಟ್ ಖರಾಬ್ (ಬ)": "Phut Kharab (B)",
    "ಉಳಿದದ್ದು": "Remainder / Net Area",
    "ಕಂದಾಯ": "Land Revenue (Tax)",
    "ಭೂ ಕಂದಾಯ": "Land Revenue",
    "ಜೋಡಿ": "Jodi",
    "ಸೆಸ್ಸುಗಳು": "Cess",
    "ನೀರಿನ ದರ": "Water Rate",
    "ಒಟ್ಟು": "Total",
    "ಮಣ್ಣಿನ ನಮೂನೆ": "Soil Type",
    "ಪಟ್ಟಾ": "Patta (Land Title Type)",
    "ಕಟ್ಟೆ ಅಥವಾ ಸ್ವಾಧೀನದಾರನ ಹೆಸರು": "Name of Occupant/Kattedar",
    "ವಿಸ್ತೀರ್ಣ ಎ ಗುಂ": "Area (Acre-Guntas)",
    "ಖಾತೆ ನಂ": "Khata No.",
    "ಕಟ್ಟೆ ಅಥವಾ ಸ್ವಾಧೀನತೆಯ ರೀತಿ": "Nature of Occupation/Possession",
    "ಸಾಗುವಳಿ ವಿವರ": "Cultivation Details",
    "ವರ್ಷ ಮತ್ತು ಕಾಲ": "Year and Season",
    "ವ್ಯವಸಾಯಗಾರನ ಹೆಸರು ಮತ್ತು ವಾಸಸ್ಥಳ": "Cultivator's Name and Residence",
    "ಸಾಗುವಳಿ ಪದ್ಧತಿ": "Method of Cultivation",
    "ಭೂಮಿಯ ಉಪಯೋಗ": "Land Use",
    "ಬೆಳೆಯ ಹೆಸರು": "Crop Name",
    "ಬೆಳೆಯ ವಿಸ್ತೀರ್ಣ": "Crop Area",
}

RTC_VALUES_KN_EN = {
    "ಸ್ವಂತ": "Self",
    "ಜಂಟಿ": "Joint",
    "ಮೇಲಿನ ಜಂಟಿ": "Joint (as above)",
    "ಬಿನ್": "Bin (son of)",
    "ಲೇಟ್": "Late",
    "ಲೇ": "Late",
    "ಹಕ್ಕು ಬಿಡುಗಡೆ": "Right Released",
    "ಕಪ್ಪು": "Black",
    "ಹಾಳು": "Fallow/Waste",
    "ಇನಾಂ": "Inam (land grant)",
    "ಸರ್ಕಾರಿ": "Government",
}

# Shape patterns
SURVEY_NUMBER_PATTERN = re.compile(r'^\d{1,4}\*?$')
AREA_VALUE_PATTERN = re.compile(r'^\d+(\.\d+){2,3}$')
RUPEE_AMOUNT_PATTERN = re.compile(r'^\d+\.\d{2}$')

def extract_from_screenshot(image_path: str, output_path: str):
    """Extract RTC data from screenshot using OCR."""
    
    # Load image
    img = Image.open(image_path)
    
    # Extract text using pytesseract with Kannada language
    text = pytesseract.image_to_string(img, lang='kan+eng')
    
    print("Extracted OCR text:")
    print(text)
    print("\n" + "="*50 + "\n")
    
    # Initialize result structure
    result = {
        "survey_number": "",
        "hissa": "",
        "total_area": "",
        "phut_kharab_a": "",
        "phut_kharab_b": "",
        "remainder": "",
        "land_revenue": "",
        "jodi": "",
        "cess": "",
        "water_rate": "",
        "total_revenue": "",
        "soil_type": "",
        "patta": "",
        "occupant_name": "",
        "occupant_area": "",
        "khata_no": "",
        "possession_nature": "",
        "cultivation_details": []
    }
    
    # Parse OCR text to extract fields
    lines = text.split('\n')
    
    # Simple pattern-based extraction
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Survey number (look for patterns like "2" or "40*")
        if SURVEY_NUMBER_PATTERN.match(line):
            result["survey_number"] = line
        
        # Area values (look for patterns like "0.06.00.00")
        if AREA_VALUE_PATTERN.match(line):
            # Heuristic: first area-like value is total area
            if not result["total_area"]:
                result["total_area"] = line
            elif not result["phut_kharab_a"]:
                result["phut_kharab_a"] = line
            elif not result["phut_kharab_b"]:
                result["phut_kharab_b"] = line
            elif not result["remainder"]:
                result["remainder"] = line
        
        # Look for Kannada labels and extract values after them
        for kn_label, en_label in RTC_LABELS_KN_EN.items():
            if kn_label in line:
                # Extract value after the label
                value = line.replace(kn_label, "").strip()
                if value:
                    # Map to result fields
                    if "Survey Number" in en_label:
                        result["survey_number"] = value
                    elif "Total Area" in en_label:
                        result["total_area"] = value
                    elif "Phut Kharab (A)" in en_label:
                        result["phut_kharab_a"] = value
                    elif "Phut Kharab (B)" in en_label:
                        result["phut_kharab_b"] = value
                    elif "Remainder" in en_label:
                        result["remainder"] = value
                    elif "Land Revenue" in en_label:
                        result["land_revenue"] = value
                    elif "Jodi" in en_label:
                        result["jodi"] = value
                    elif "Cess" in en_label:
                        result["cess"] = value
                    elif "Water Rate" in en_label:
                        result["water_rate"] = value
                    elif "Total" in en_label and "Revenue" not in en_label:
                        result["total_revenue"] = value
                    elif "Soil Type" in en_label:
                        result["soil_type"] = value
                    elif "Patta" in en_label:
                        result["patta"] = value
                    elif "Occupant" in en_label and "Name" in en_label:
                        result["occupant_name"] = value
                    elif "Area" in en_label and "Acre" in en_label:
                        result["occupant_area"] = value
                    elif "Khata" in en_label:
                        result["khata_no"] = value
                    elif "Possession" in en_label:
                        result["possession_nature"] = value
        
        # Look for cultivation details
        if "ಸಾಗುವಳಿ" in line or "Cultivation" in line:
            # Next lines might contain cultivation data
            pass
    
    # Translate Kannada values to English
    for key, value in result.items():
        if isinstance(value, str) and value in RTC_VALUES_KN_EN:
            result[key] = RTC_VALUES_KN_EN[value]
    
    # Save result
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Extraction complete. Results saved to {output_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result

if __name__ == "__main__":
    # Process uploaded screenshots
    # You'll need to provide the actual screenshot paths
    # For now, let's process the existing rtc_page.png as an example
    extract_from_screenshot("logs/debug/rtc_page.png", "logs/debug/screenshot_extraction.json")
