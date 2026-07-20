#!/usr/bin/env python3
"""Test OCR extraction on existing RTC PNG"""

import pytesseract
from PIL import Image
import re

# Load the existing RTC PNG
png_path = "logs/debug/rtc_full_document.png"
print(f"Loading RTC PNG from: {png_path}")

try:
    image = Image.open(png_path)
    print(f"Image size: {image.size}")
    
    # Run OCR with Kannada + English
    print("Running OCR...")
    ocr_text = pytesseract.image_to_string(image, lang='kan+eng')
    print(f"OCR text extracted (length: {len(ocr_text)})")
    
    # Save raw OCR output
    with open("logs/debug/rtc_ocr_test.txt", "w", encoding="utf-8") as f:
        f.write(ocr_text)
    print("Raw OCR output saved to: logs/debug/rtc_ocr_test.txt")
    
    # Parse for RTC Validity
    ocr_lines = ocr_text.split('\n')
    
    # First pass: collect all dates and times with their line indices
    dates = []
    times = []
    for i, line in enumerate(ocr_lines):
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
        if date_match:
            dates.append((i, date_match.group(1), line.lower()))
        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        if time_match:
            times.append((i, time_match.group(1), line.lower()))
    
    print(f"\nFound {len(dates)} dates and {len(times)} times")
    for idx, date_str, line in dates:
        print(f"  Date at line {idx}: {date_str} - '{line.strip()[:50]}'")
    for idx, time_str, line in times:
        print(f"  Time at line {idx}: {time_str} - '{line.strip()[:50]}'")
    
    # Try to match dates and times that are close together (within 5 lines)
    rtc_validity = None
    for date_idx, date_str, date_line in dates:
        for time_idx, time_str, time_line in times:
            if abs(date_idx - time_idx) <= 5:
                # Check if "valid" or "from" is nearby
                if 'valid' in date_line or 'from' in date_line or 'valid' in time_line or 'till' in time_line:
                    rtc_validity = f"Valid from {date_str} {time_str} Till Date"
                    print(f"\n✓ Matched date and time near 'valid' keyword")
                    print(f"  Date line {date_idx}: '{date_line.strip()[:60]}'")
                    print(f"  Time line {time_idx}: '{time_line.strip()[:60]}'")
                    break
        if rtc_validity:
            break
    
    # If still not found, look for date with "valid" keyword
    if not rtc_validity:
        for date_idx, date_str, date_line in dates:
            if 'valid' in date_line or 'from' in date_line:
                rtc_validity = f"Valid from {date_str} Till Date"
                print(f"\n✓ Matched date near 'valid' keyword (no time)")
                print(f"  Date line {date_idx}: '{date_line.strip()[:60]}'")
                break
    
    print(f"\n=== EXTRACTION RESULT ===")
    if rtc_validity:
        print(f"RTC Validity: {rtc_validity}")
    else:
        print("RTC Validity: null (not found)")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
