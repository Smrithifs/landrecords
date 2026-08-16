"""
Bhoomi Public Portal Scraper
No login required - uses public portal at https://landrecords.karnataka.gov.in/Service2/
"""

import re
import json
import os
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import pytesseract
from rapidfuzz import fuzz, process
from deep_translator import GoogleTranslator
from playwright.async_api import async_playwright
import google.genai as genai

# Bilingual dictionaries for RTC field translation
RTC_LABELS_KN_EN = {
    # Header
    "ಗ್ರಾಮ ನಮೂನೆ ೧": "Village Form No. 1",
    "ತಾಲ್ಲೂಕು ಮೊಹರು": "Taluk Seal",
    "ರೆಕಾರ್ಡ್ ಆಫ್ ರೈಟ್ಸ್, ಗೇಣಿ ಮತ್ತು ಪಹಣಿ ಪತ್ರಿಕೆ": "Record of Rights, Tenancy and Crops (R.T.C.) Form No. 1",
    "ತಾಲ್ಲೂಕು": "Taluk",
    "ಹೋಬಳಿ": "Hobli",
    "ಗ್ರಾಮ": "Village",
    "ಪುಟದ ಕ್ರಮ ಸಂಖ್ಯೆ": "Page Sl. No.",
    "ಸರ್ವೆ ನಂಬರು": "Survey Number",
    "ಹಿಸ್ಸಾ": "Hissa (Sub-division)",
    "ಪೀಸೆವಾರು": "Split-up Details (Pisewaru)",
    "ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ": "Total Area",
    "ಪೂಟ್ ಖರಾಬ್ (ಅ)": "Phut Kharab (A)",
    "ಪೂಟ್ ಖರಾಬ್ (ಬ)": "Phut Kharab (B)",
    "ಉಳಿದದ್ದು": "Remainder / Net Area",
    "ಎಕರೆ ಗುಂಟೆ ಆಣೆ": "Acre - Guntas - Aane",
    "ಕಂದಾಯ": "Land Revenue (Tax)",
    "ಭೂ ಕಂದಾಯ": "Land Revenue",
    "ಜೋಡಿ": "Jodi",
    "ಸೆಸ್ಸುಗಳು": "Cess",
    "ನೀರಿನ ದರ": "Water Rate",
    "ರೂ. ಪೈ": "Rs. - Paise",
    "ಒಟ್ಟು": "Total",
    "ಮಣ್ಣಿನ ನಮೂನೆ": "Soil Type",
    "ಪಟ್ಟಾ": "Patta (Land Title Type)",
    "ಮರಗಳ ಸಂಖ್ಯೆ": "Number of Trees",
    "ಹೆಸರು": "Name",
    "ಸಂಖ್ಯೆ": "Number",
    "ಬೇಸಾಯ ಪ್ರಕಾರ ಸೀರಾವರಿಯ ವಿಸ್ತೀರ್ಣ": "Area under Cultivation Type / Irrigation",
    "ಕ್ರ. ಸಂ": "Sl. No.",
    "ಸೀರಾವರಿ ಮೂಲ": "Source of Irrigation",
    "ಮುಂಗಾರು": "Kharif (Monsoon crop season)",
    "ಹಿಂಗಾರು": "Rabi (Winter crop season)",
    "ಬಾಗಾಯ್ತು": "Garden Land (Bagayat)",
    "ಕಟ್ಟೆ ಅಥವಾ ಸ್ವಾಧೀನದಾರನ ಹೆಸರು": "Name of Occupant/Kattedar",
    "ತಂದೆಯ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ": "Father's Name and Address",
    "ವಿಸ್ತೀರ್ಣ ಎ ಗುಂ": "Area (Acre-Guntas)",
    "ಖಾತೆ ನಂ": "Khata No.",
    "ಕಟ್ಟೆ ಅಥವಾ ಸ್ವಾಧೀನತೆಯ ರೀತಿ": "Nature of Occupation/Possession",
    "ಇತರೆ ಹಕ್ಕುಗಳು ಮತ್ತು ಋಣಗಳು": "Other Rights and Liabilities",
    "ಹಕ್ಕುಗಳು": "Rights",
    "ಋಣಗಳು": "Liabilities",
    "ಸಾಗುವಳಿ ವಿವರ": "Cultivation Details",
    "ವರ್ಷ ಮತ್ತು ಕಾಲ": "Year and Season",
    "ವ್ಯವಸಾಯಗಾರನ ಹೆಸರು ಮತ್ತು ವಾಸಸ್ಥಳ": "Cultivator's Name and Residence",
    "ಸಾಗುವಳಿ ಪದ್ಧತಿ": "Method of Cultivation",
    "ಗೇಣಿಯ ವಿವರ": "Tenancy/Rent Details",
    "ಗುತ್ತಿಗೆ": "Lease/Contract",
    "ವರ್ಗ": "Class",
    "ಭೂಮಿಯ ಉಪಯೋಗ": "Land Use",
    "ಮಿಶ್ರ, ತರಿ, ಬಾಗಾಯ್ತು": "Mixed, Dry Land, Garden Land",
    "ಬೆಳೆಯ ಹೆಸರು": "Crop Name",
    "ಬೆಳೆಯ ಉಪಯೋಗ ಮತ್ತು ಬೆಳೆಗಳ ವಿವರ": "Crop Use and Crop Details",
    "ಬೆಳೆಯ ವಿಸ್ತೀರ್ಣ": "Crop Area",
    "ಅಮಿಶ್ರ": "Non-mixed (Sole crop)",
    "ಮಿಶ್ರ": "Mixed crop",
    "ನೀರಾವರಿ ಮೂಲ": "Source of Irrigation",
    "ಎಕರೆಗೆ ಉತ್ಪತ್ತಿ": "Yield per Acre",
    "ಮಿತ್ರ, ಬೆಳಗಳ ಒಟ್ಟು": "Companion Crop, Total",
    "ಮಿತ್ರನ ಹೆಸರು": "Name of Companion (co-cultivator)",
    "ವಿಸ್ತೀರ್ಣ": "Area",
}

RTC_VALUES_KN_EN = {
    # Common recurring VALUES (not labels) - dictionary lookup, not translation
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


def translate_label(kn_text: str, threshold: int = 80) -> str | None:
    """Exact match first, then fuzzy match against known labels."""
    if kn_text in RTC_LABELS_KN_EN:
        return RTC_LABELS_KN_EN[kn_text]
    match, score, _ = process.extractOne(
        kn_text, RTC_LABELS_KN_EN.keys(), scorer=fuzz.ratio
    )
    return RTC_LABELS_KN_EN[match] if score >= threshold else None


def translate_value(kn_text: str, threshold: int = 80) -> dict:
    """
    Returns {'kn': original, 'en': translated_or_same, 'needs_review': bool}
    Numbers pass through unchanged. Known values are dictionary-matched.
    Unmatched text (likely names) is flagged for review, never guessed.
    """
    if re.fullmatch(r'[\d.\-/]+', kn_text.strip()):
        return {"kn": kn_text, "en": kn_text, "needs_review": False}
    if kn_text in RTC_VALUES_KN_EN:
        return {"kn": kn_text, "en": RTC_VALUES_KN_EN[kn_text], "needs_review": False}
    match, score, _ = process.extractOne(
        kn_text, RTC_VALUES_KN_EN.keys(), scorer=fuzz.ratio
    )
    if score >= threshold:
        return {"kn": kn_text, "en": RTC_VALUES_KN_EN[match], "needs_review": False}
    return {"kn": kn_text, "en": kn_text, "needs_review": True}


class BhoomiPublicScraper:
    def __init__(self):
        self.base_url = "https://landrecords.karnataka.gov.in/Service2/"
        self.rtc_url = "https://landrecords.karnataka.gov.in/Service2/RTC.aspx"
        self.translator = GoogleTranslator(source='kn', target='en')
        
        # Configure Gemini API
        try:
            from dotenv import load_dotenv
            load_dotenv()
            load_dotenv(".env.example", override=False)
        except Exception:
            pass
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_client = None
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            print("Warning: GEMINI_API_KEY environment variable is not set; Gemini extraction will be skipped.")
    
    def translate_text(self, text: str) -> str:
        """Translate Kannada text to English."""
        if not text or not text.strip():
            return text
        try:
            translated = self.translator.translate(text)
            return translated
        except Exception as e:
            print(f"Translation error for '{text}': {e}")
            return text
    
    def _extract_with_gemini(self, image_paths: list, output_path: str) -> dict:
        """Extract RTC data using Gemini Vision API from multiple screenshots."""
        try:
            if not self.gemini_client or not self.gemini_api_key:
                print("Gemini extraction skipped: GEMINI_API_KEY is not configured.")
                return None

            # Load all images
            images_data = []
            for img_path in image_paths:
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        images_data.append(f.read())
                    print(f"Loaded image: {img_path}")
                else:
                    print(f"Image not found: {img_path}")
            
            if not images_data:
                print("No valid images found for Gemini extraction")
                return None
            
            # Comprehensive prompt for RTC extraction from both pages
            prompt = """
            Analyze these RTC (Record of Rights, Tenancy and Crops) document screenshots and extract ALL details.
            
            You will see TWO images:
            1. Search/Results Page - showing district, taluk, hobli, village selection, survey number, owner table
            2. RTC Form Page (Village Form No. 1) - showing detailed land records
            
            Extract ALL information from BOTH images and return the result as a JSON object with Kannada and English side by side.
            
            Extract these fields with both Kannada and English values:
            
            From Search/Results Page:
            - District, Taluk, Hobli, Village
            - Survey Number, Surnoc, Hissa No
            - Period/Validity dates
            - Land ID
            - OnGoing Mutation status
            - PYKI status
            - Owner Table: Owner names, Extent, Category, Gov Restriction, Court Stay, Alienated
            
            From RTC Form Page:
            - Header: Taluk, Hobli, Village, Valid from date
            - Survey Number, Hissa
            - Total Area, Phut Kharab (A), Phut Kharab (B), Remainder
            - Land Revenue breakdown: Land Revenue (a), Jodi (b), Cess (c), Water Rate (d), Total
            - Soil Type, Patta
            - Number of Trees, Irrigation Area
            - Occupant Name, Area, Khata No, Joint Owner
            - Nature of Possession
            - Rights / Liabilities
            - Cultivation Details: Year, Season, Cultivator names, Method, Areas, Yield
            
            IMPORTANT:
            - Extract ALL text from BOTH images, including Kannada text
            - Provide both Kannada and English values side by side
            - For names, provide transliteration to English
            - For numerical values, keep them as-is
            - Return ONLY valid JSON, no additional text
            - If a field is empty or not found, use empty string ""
            - Combine information from both images into a complete result
            """
            
            # Try different model names
            model_names = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.0-flash"]
            response = None

            for model_name in model_names:
                try:
                    # Build contents with prompt and all images
                    contents = [prompt]
                    for img_data in images_data:
                        contents.append(
                            genai.types.Part.from_bytes(
                                data=img_data,
                                mime_type="image/png"
                            )
                        )
                    
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    print(f"Gemini extraction successful with model: {model_name}")
                    break
                except Exception as e:
                    print(f"Failed with model {model_name}: {e}")
                    continue
            else:
                raise Exception("All Gemini model attempts failed")
            
            # Parse response
            result_text = response.text
            
            # Clean up response (remove markdown code blocks if present)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            result_json = json.loads(result_text)
            
            # Save to file
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_json, f, indent=2, ensure_ascii=False)
            
            print(f"Gemini extraction saved to: {output_path}")
            return result_json
            
        except Exception as e:
            print(f"Gemini extraction failed: {e}")
            return None  # Return original if translation fails
    
    def _extract_rtc_fields_from_ocr(self, ocr_data: dict, image_width: int, image_height: int, survey_no: str = "") -> dict:
        """Extract RTC fields from OCR data using dynamic label-relative detection."""
        
        # Initialize result structure with kn/en side-by-side and needs_review flags
        result = {
            "survey_number": {"kn": survey_no, "en": survey_no, "needs_review": False},
            "hissa": {"kn": "", "en": "", "needs_review": False},
            "split_up_details": {
                "total_area": {"kn": "", "en": "", "needs_review": False},
                "phut_kharab_a": {"kn": "", "en": "", "needs_review": False},
                "phut_kharab_b": {"kn": "", "en": "", "needs_review": False},
                "remainder": {"kn": "", "en": "", "needs_review": False}
            },
            "land_revenue": {
                "land_revenue": {"kn": "", "en": "", "needs_review": False},
                "jodi": {"kn": "", "en": "", "needs_review": False},
                "cess": {"kn": "", "en": "", "needs_review": False},
                "water_rate": {"kn": "", "en": "", "needs_review": False},
                "total": {"kn": "", "en": "", "needs_review": False}
            },
            "soil_type": {"kn": "", "en": "", "needs_review": False},
            "patta": {"kn": "", "en": "", "needs_review": False},
            "occupant": {
                "name": {"kn": "", "en": "", "needs_review": False},
                "area": {"kn": "", "en": "", "needs_review": False},
                "khata_no": {"kn": "", "en": "", "needs_review": False}
            },
            "possession_nature": {"kn": "", "en": "", "needs_review": False},
            "cultivation_rows": []
        }
        
        # Build list of valid OCR words with their positions
        words_with_boxes = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = ocr_data['conf'][i]
            if text and conf > 0:  # Only use words with positive confidence
                words_with_boxes.append({
                    'text': text,
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i],
                    'conf': conf
                })
        
        print(f"Valid OCR words: {len(words_with_boxes)}")
        
        # Dynamic label detection function
        def find_label_position(label_text, threshold=60):
            """Find the position of a label using fuzzy matching."""
            best_match = None
            best_score = 0
            for word in words_with_boxes:
                score = fuzz.ratio(label_text, word['text'])
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = word
            return best_match, best_score
        
        # Survey number is now taken from input parameter, not extracted from OCR
        
        # Extract occupant name from top section (look for "ಸ್ವಾಧೀನದಾರನ ಹೆಸರು" label)
        occupant_label, _ = find_label_position('ಸ್ವಾಧೀನದಾರನ ಹೆಸರು', threshold=60)
        if occupant_label:
            # Look for data below the label on the right side
            start_y = occupant_label['top'] + 50
            end_y = start_y + 100
            occupant_words = []
            for word in words_with_boxes:
                x_percent = word['left'] / image_width
                if (word['top'] > start_y and word['top'] < end_y and x_percent > 0.40):
                    # Skip single digits and very short words
                    if len(word['text']) > 2 or not word['text'].isdigit():
                        occupant_words.append(word)
            
            if occupant_words:
                # Sort by confidence and pick the best match
                occupant_words.sort(key=lambda w: w['conf'], reverse=True)
                # Join multiple words in the same row to get full name
                row_text = ' '.join([w['text'] for w in occupant_words[:5]])  # Take top 5 words
                translation_result = translate_value(row_text)
                result['occupant']['name'] = {
                    "kn": translation_result["kn"],
                    "en": translation_result["en"],
                    "needs_review": translation_result["needs_review"]
                }
                print(f"Extracted occupant name: kn='{translation_result['kn']}' en='{translation_result['en']}' needs_review={translation_result['needs_review']}")
        
        # Extract cultivation rows (look for "ಸಾಗುವಳಿ" label)
        cultivation_label, _ = find_label_position('ಸಾಗುವಳಿ', threshold=60)
        if cultivation_label:
            # Extract all words below the cultivation label
            cultivation_words = []
            for word in words_with_boxes:
                if word['top'] > cultivation_label['top']:
                    cultivation_words.append(word)
            
            # Group by rows
            cultivation_words.sort(key=lambda w: w['top'])
            rows = []
            current_row = []
            current_y = None
            y_tolerance = 20
            
            for word in cultivation_words:
                if current_y is None or abs(word['top'] - current_y) > y_tolerance:
                    if current_row:
                        rows.append(current_row)
                    current_row = [word]
                    current_y = word['top']
                else:
                    current_row.append(word)
            
            if current_row:
                rows.append(current_row)
            
            # Extract cultivation rows (skip header rows, focus on data rows)
            for i, row in enumerate(rows[3:6]):  # Skip first 3 header rows, take next 3 data rows
                row_text = ' '.join([w['text'] for w in row])
                if row_text and len(row_text) > 5:  # Filter out empty or very short rows
                    translation_result = translate_value(row_text)
                    result['cultivation_rows'].append({
                        "kn": translation_result["kn"],
                        "en": translation_result["en"],
                        "needs_review": translation_result["needs_review"]
                    })
                    print(f"Extracted cultivation row {i+1}: kn='{translation_result['kn'][:50]}...' en='{translation_result['en'][:50]}...' needs_review={translation_result['needs_review']}")
        
        return result
    
    def _find_nearest_value(self, label_box: dict, words_with_boxes: list) -> str:
        """Find the nearest value text to the right or below a label."""
        label_left = label_box['left']
        label_top = label_box['top']
        label_right = label_left + label_box['width']
        label_bottom = label_top + label_box['height']
        
        # Words that are likely labels, not values
        label_words = {'ಎಕರೆ', 'ಗುಂಟೆ', 'ಆಣೆ', 'ರೂ', 'ಪೈ', 'ವಿಸ್ತೀರ್ಣ', 'ಎ', 'ಗುಂ', 'ಖರಾಬ್', 'ಕಂದಾಯ', 'ಜೋಡಿ', 'ಸೆಸ್ಸು', 'ನೀರಿನ', 'ದರ', 'ಒಟ್ಟು', 'ಮಣ್ಣಿನ', 'ನಮೂನೆ', 'ಪಟ್ಟಾ', 'ಹೆಸರು', 'ಸಂಖ್ಯೆ', 'ಕ್ರ', 'ಸಂ', 'ಮೂಲ', 'ಮುಂಗಾರು', 'ಹಿಂಗಾರು', 'ಬಾಗಾಯ್ತು', 'ವಿಳಾಸ', 'ವಿವರ', 'ಪದ್ಧತಿ', 'ಗೇಣಿಯ', 'ಗುತ್ತಿಗೆ', 'ವರ್ಗ', 'ಭೂಮಿಯ', 'ಉಪಯೋಗ', 'ಬೆಳೆಯ', 'ನೀರಾವರಿ', 'ಉತ್ಪತ್ತಿ', 'ಮಿತ್ರ', 'ಬೆಳಗಳ', 'ಒಟ್ಟು', 'ಮಿತ್ರನ', 'ನಮೂದಿಸಿರುವುದಿಲ್ಲ'}
        
        # Look for text to the right (same row, slightly to the right)
        candidates = []
        for word_box in words_with_boxes:
            word_left = word_box['left']
            word_top = word_box['top']
            word_text = word_box['text']
            
            # Skip if this is the same word as the label
            if word_box == label_box:
                continue
                
            # Check if word is to the right and on same row (within vertical tolerance)
            if word_left > label_right and abs(word_top - label_top) < 30:
                # Check if it's not another label word
                if word_text not in label_words and not any(lw in word_text for lw in label_words):
                    distance = word_left - label_right
                    if distance < 200:  # Within reasonable horizontal distance
                        candidates.append((distance, word_text))
        
        # Sort by distance and return the closest
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        
        # If nothing to the right, look below
        candidates = []
        for word_box in words_with_boxes:
            word_left = word_box['left']
            word_top = word_box['top']
            word_text = word_box['text']
            
            # Skip if this is the same word as the label
            if word_box == label_box:
                continue
                
            # Check if word is below and horizontally aligned
            if word_top > label_bottom and abs(word_left - label_left) < 100:
                if word_text not in label_words and not any(lw in word_text for lw in label_words):
                    distance = word_top - label_bottom
                    if distance < 100:  # Within reasonable vertical distance
                        candidates.append((distance, word_text))
        
        # Sort by distance and return the closest
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        
        return ""
    
    
    
    async def fetch_rtc(self, district: str, taluk: str, hobli: str, village: str, survey_no: str, surnoc: str = '*', hissa_no: str = '*'):
        """
        Fetch RTC data from public Bhoomi portal.
        
        Args:
            district: District name (e.g., "BENGALURU")
            taluk: Taluk name (e.g., "BANGALORE-NORTH")
            hobli: Hobli name (e.g., "DASANAPURA1")
            village: Village name (e.g., "ADAKAMARANAHALLI")
            survey_no: Survey number (e.g., "3")
            surnoc: Surnoc number (default: "*")
            hissa_no: Hissa number (default: "*")
        
        Returns:
            dict: Extracted RTC data
        """
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # Navigate directly to RTC.aspx page
                    print(f"Navigating to {self.rtc_url}")
                    await page.goto(self.rtc_url)
                    await page.wait_for_load_state("networkidle")
                    print("RTC page loaded")
                    
                    # Set language to English ONCE at the beginning
                    print("Setting language to English...")
                    english_locator = page.locator('a:has-text("English"), a[href*="en"], button:has-text("English")')
                    if await english_locator.count() > 0:
                        await english_locator.first.click()
                        await page.wait_for_timeout(1000)
                        print("Language set to English")
                    else:
                        print("English link not found, may already be in English")
                    
                    # Select District using locator
                    print(f"Selecting District: {district}")
                    await page.wait_for_selector('select[name*="District"], select[id*="District"]', timeout=10000)
                    await page.locator('select[name*="District"], select[id*="District"]').select_option(label=district)
                    await page.wait_for_timeout(2000)
                    print(f"District selected: {district}")
                    
                    # Select Taluk using locator
                    print(f"Selecting Taluk: {taluk}")
                    await page.wait_for_selector('select[name*="Taluk"], select[id*="Taluk"]', timeout=10000)
                    await page.locator('select[name*="Taluk"], select[id*="Taluk"]').select_option(label=taluk)
                    await page.wait_for_timeout(2000)
                    print(f"Taluk selected: {taluk}")
                    
                    # Select Hobli using locator
                    print(f"Selecting Hobli: {hobli}")
                    await page.wait_for_selector('select[name*="Hobli"], select[id*="Hobli"]', timeout=10000)
                    await page.locator('select[name*="Hobli"], select[id*="Hobli"]').select_option(label=hobli)
                    await page.wait_for_timeout(2000)
                    print(f"Hobli selected: {hobli}")
                    
                    # Select Village using locator
                    print(f"Selecting Village: {village}")
                    await page.wait_for_selector('select[name*="Village"], select[id*="Village"]', timeout=10000)
                    await page.locator('select[name*="Village"], select[id*="Village"]').select_option(label=village)
                    await page.wait_for_timeout(2000)
                    print(f"Village selected: {village}")
                    
                    # Enter Survey Number using exact ID with locator
                    print(f"Entering Survey Number: {survey_no}")
                    survey_locator = page.locator('#ctl00_MainContent_txtSurvey')
                    if await survey_locator.count() > 0:
                        await survey_locator.fill(survey_no)
                        await page.wait_for_timeout(500)
                        print(f"Survey number entered: {survey_no}")
                    else:
                        print("Survey input not found with exact ID, trying generic selector...")
                        survey_locator = page.locator('input[name*="Survey"], input[id*="Survey"]')
                        if await survey_locator.count() > 0:
                            await survey_locator.fill(survey_no)
                            await page.wait_for_timeout(500)
                            print(f"Survey number entered: {survey_no}")
                    
                    # Click Go button using exact ID - this is a standard ASP.NET submit button (form.submit)
                    print("Clicking Go button (ID: ctl00_MainContent_btnCGo)...")
                    print("GO button mechanism: Standard HTML <input type=\"submit\"> triggering form.submit postback")
                    await page.locator('#ctl00_MainContent_btnCGo').click()
                    print("Go button clicked, waiting for postback to complete...")
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(3000)
                    print("Postback complete")
                    
                    # DO NOT change language after Go - let it stay in Kannada to avoid interrupting ASP.NET lifecycle
                    
                    # Take screenshot after GO
                    log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
                    os.makedirs(log_dir, exist_ok=True)
                    await page.screenshot(path=f'{log_dir}/bhoomi_public_after_go.png')
                    print(f"Screenshot saved: {log_dir}/bhoomi_public_after_go.png")
                    
                    # Wait for Surnoc dropdown to become enabled using locator
                    print("Waiting for Surnoc dropdown to enable...")
                    try:
                        await page.wait_for_function(
                            """() => {
                                const el = document.querySelector('#ctl00_MainContent_ddlCSurnocNo');
                                return el && !el.disabled && el.options.length > 1;
                            }""",
                            timeout=15000
                        )
                        print("Surnoc dropdown enabled")
                    except Exception as e:
                        print(f"Surnoc not enabled after timeout: {e}")
                    
                    # Take screenshot to debug current state
                    await page.screenshot(path=f'{log_dir}/bhoomi_public_before_surnoc.png')
                    print(f"Screenshot saved: {log_dir}/bhoomi_public_before_surnoc.png")
                    
                    # Check if surnoc dropdown exists and its state using locator
                    print("Checking surnoc dropdown state...")
                    surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                    if await surnoc_locator.count() > 0:
                        is_disabled = await surnoc_locator.get_attribute('disabled')
                        option_count = await surnoc_locator.evaluate('el => el.options.length')
                        print(f"Surnoc exists: True, disabled: {is_disabled}, options: {option_count}")
                        
                        # Check for error messages
                        error_text = await page.locator('text=/error|invalid|not found/i').all_text_contents()
                        if error_text:
                            print(f"Error messages found: {error_text}")
                        
                        # If still disabled, try pressing Enter on survey field using locator
                        if is_disabled or option_count <= 1:
                            print("Surnoc still disabled, trying Enter key on survey field...")
                            survey_locator = page.locator('#ctl00_MainContent_txtSurvey')
                            if await survey_locator.count() > 0:
                                await survey_locator.focus()
                                await page.keyboard.press('Enter')
                                await page.wait_for_timeout(5000)
                                print("Enter key pressed")
                                
                                # Check again using fresh locator
                                surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                                is_disabled = await surnoc_locator.evaluate('el => el.disabled')
                                option_count = await surnoc_locator.evaluate('el => el.options.length')
                                print(f"After Enter - disabled: {is_disabled}, options: {option_count}")
                                
                                # If still disabled after Enter, try clicking Go again
                                if is_disabled or option_count <= 1:
                                    print("Surnoc still disabled after Enter, trying Go button again...")
                                    go_locator = page.locator('#ctl00_MainContent_btnCGo')
                                    await go_locator.click()
                                    await page.wait_for_timeout(3000)
                                    
                                    # Check once more
                                    surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                                    is_disabled = await surnoc_locator.evaluate('el => el.disabled')
                                    option_count = await surnoc_locator.evaluate('el => el.options.length')
                                    print(f"After second Go - disabled: {is_disabled}, options: {option_count}")
                                
                                # If still disabled after second Go, skip Surnoc selection
                                if is_disabled or option_count <= 1:
                                    print("Surnoc still disabled after all attempts, skipping Surnoc selection")
                                    print("Proceeding with Fetch Details anyway...")
                    else:
                        print("Surnoc dropdown not found on page")
                    
                    # Select Surnoc using fresh locator after postback - only if enabled
                    print(f"Selecting Surnoc {surnoc}")
                    surnoc_locator = page.locator('#ctl00_MainContent_ddlCSurnocNo')
                    if await surnoc_locator.count() > 0:
                        is_disabled = await surnoc_locator.evaluate('el => el.disabled')
                        if not is_disabled:
                            # Try selecting by value first, then label if value fails
                            try:
                                await surnoc_locator.select_option(value=surnoc)
                            except:
                                await surnoc_locator.select_option(label=surnoc)
                            await page.wait_for_timeout(2000)
                            print(f"Surnoc {surnoc} selected")
                        else:
                            print("Surnoc dropdown is disabled, skipping selection")
                    
                    # Select Hissa using locator - only if enabled
                    print(f"Selecting Hissa {hissa_no}")
                    hissa_locator = page.locator('#ctl00_MainContent_ddlCHissaNo')
                    if await hissa_locator.count() > 0:
                        is_disabled = await hissa_locator.evaluate('el => el.disabled')
                        if not is_disabled:
                            # Try selecting by value first, then label if value fails
                            try:
                                await hissa_locator.select_option(value=hissa_no)
                            except:
                                await hissa_locator.select_option(label=hissa_no)
                            await page.wait_for_timeout(2000)
                            print(f"Hissa {hissa_no} selected")
                        else:
                            print("Hissa dropdown is disabled, skipping selection")
                    
                    # Click Fetch Details using exact ID
                    print("Clicking Fetch Details button (ID: ctl00_MainContent_btnCFetchDetails)...")
                    fetch_locator = page.locator('#ctl00_MainContent_btnCFetchDetails')
                    if await fetch_locator.count() > 0:
                        await fetch_locator.click()
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(5000)
                        print("Fetch Details clicked")
                    
                    # Take screenshot after Fetch
                    await page.screenshot(path=f'{log_dir}/bhoomi_public_after_fetch.png')
                    print(f"Screenshot saved: {log_dir}/bhoomi_public_after_fetch.png")
                    
                    # Extract data from results table
                    page_content = await page.content()
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    rtc_data = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no": survey_no,
                        "surnoc": surnoc,
                        "hissa_no": hissa_no,
                        "OnGoing Mutation": "",
                        "PYKI": "",
                        "Owners": [],
                        "raw_html": page_content
                    }
                    
                    # Extract OnGoing Mutation and PYKI fields
                    # These are typically displayed as labels above the table
                    text_content = soup.get_text()
                    if "OnGoing Mutation" in text_content:
                        # Extract value after "OnGoing Mutation"
                        import re
                        ongoing_match = re.search(r'OnGoing Mutation\s*:\s*(\w+)', text_content)
                        if ongoing_match:
                            rtc_data["OnGoing Mutation"] = ongoing_match.group(1)
                    
                    if "PYKI" in text_content:
                        # Extract value after "PYKI"
                        pyki_match = re.search(r'PYKI\s*:\s*(\w+)', text_content)
                        if pyki_match:
                            rtc_data["PYKI"] = pyki_match.group(1)
                    
                    # Extract ownership table
                    tables = soup.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')
                        if len(rows) < 2:
                            continue
                        
                        # Check if this is the ownership table by looking for column headers
                        header_cells = rows[0].find_all(['td', 'th'])
                        header_text = ' '.join([cell.get_text(strip=True) for cell in header_cells])
                        
                        # Check if this table has the expected columns
                        if any(keyword in header_text for keyword in ['Owner', 'Extent', 'Category', 'Restriction', 'Court', 'Alienated']):
                            print(f"Found ownership table with headers: {header_text}")
                            
                            # Extract data rows (skip header)
                            for i, row in enumerate(rows[1:], start=1):
                                cells = row.find_all(['td', 'th'])
                                if len(cells) >= 6:  # Expecting 6 columns
                                    owner_data = {
                                        "Owner": cells[0].get_text(strip=True),
                                        "Extent": cells[1].get_text(strip=True),
                                        "Owner Category": cells[2].get_text(strip=True),
                                        "Gov Restriction": cells[3].get_text(strip=True),
                                        "Court stay": cells[4].get_text(strip=True),
                                        "Alienated": cells[5].get_text(strip=True)
                                    }
                                    
                                    # Only add if it has meaningful data
                                    if owner_data["Owner"] and owner_data["Owner"] not in ['', 'Owner']:
                                        rtc_data["Owners"].append(owner_data)
                                        print(f"Extracted owner: {owner_data}")
                    
                    print(f"Total owners extracted: {len(rtc_data['Owners'])}")
                    print(f"OnGoing Mutation: {rtc_data['OnGoing Mutation']}")
                    print(f"PYKI: {rtc_data['PYKI']}")
                    
                    # Click View/Preview button for full RTC
                    print("Waiting for View/Preview button to be visible and enabled...")
                    
                    # Robust selector list for View/Preview button
                    view_selectors = [
                        '#ctl00_MainContent_btnCPreview',
                        'input[value*="View"]',
                        'input[value*="Preview"]',
                        'button:has-text("View")',
                        'button:has-text("Preview")',
                        'a:has-text("View")',
                        'a:has-text("Preview")',
                        'text=View',
                        'text=Preview'
                    ]
                    
                    view_locator = None
                    for selector in view_selectors:
                        try:
                            locator = page.locator(selector)
                            if await locator.count() > 0 and await locator.is_visible():
                                view_locator = locator
                                print(f"Found View/Preview button with selector: {selector}")
                                break
                        except Exception:
                            continue
                            
                    if not view_locator:
                        print("View/Preview button not found with standard selectors, trying generic input[type=submit] in the results area...")
                        view_locator = page.locator('input[type="submit"]:has-text("View"), input[type="submit"]:has-text("Preview")')
                    
                    if await view_locator.count() > 0:
                        # Check if button is enabled
                        is_disabled = await view_locator.get_attribute('disabled')
                        if is_disabled:
                            print(f"View button is disabled: {is_disabled}")
                        else:
                            print("View button is enabled")
                        
                        print("Clicking View button...")
                        
                        # Detect navigation type and handle accordingly
                        try:
                            async with context.expect_page(timeout=15000) as popup_info:
                                await view_locator.click()
                            
                            page = await popup_info.value
                            print("Popup detected - switching to new page")
                            await page.wait_for_load_state("networkidle")
                            await page.wait_for_timeout(3000)
                        except Exception as e:
                            print(f"No popup detected or error: {e}")
                            print("Checking for same-page navigation...")
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            print("Stayed on same page or navigation complete")
                    else:
                        print("View/Preview button NOT FOUND. Cannot proceed to full RTC.")
                        # Save screenshot for debugging
                        await page.screenshot(path=f'{log_dir}/view_button_missing.png')
                        raise Exception("View/Preview button not found on page")
                    
                    print("RTC document loaded")
                    
                    # Take full-page screenshot
                    await page.screenshot(path=f'{log_dir}/full_rtc_document.png', full_page=True)
                    print(f"Screenshot saved: {log_dir}/full_rtc_document.png")
                    
                    # Save full RTC HTML
                    full_rtc_html = await page.content()
                    with open(f"{log_dir}/full_rtc_document.html", "w", encoding="utf-8") as f:
                        f.write(full_rtc_html)
                    print(f"HTML saved: {log_dir}/full_rtc_document.html")
                    
                    # Extract RTC image URL from HTML using BeautifulSoup
                    soup = BeautifulSoup(full_rtc_html, 'html.parser')
                    rtc_image = soup.find('img', id='ImgSketchPage')
                    if rtc_image and rtc_image.get('src'):
                        rtc_image_url = rtc_image['src']
                        print(f"RTC Image URL found: {rtc_image_url}")
                        
                        # Download the image
                        print("Downloading RTC image...")
                        try:
                            if not rtc_image_url.startswith('http'):
                                rtc_image_url = f"https://landrecords.karnataka.gov.in/{rtc_image_url}"
                            
                            response = requests.get(rtc_image_url)
                            if response.status_code == 200:
                                image = Image.open(io.BytesIO(response.content))
                                image_path = f'{log_dir}/rtc_page.png'
                                image.save(image_path)
                                print(f"RTC image saved: {image_path}")
                                
                                # Run OCR with word-level bounding boxes
                                print("Running OCR with word-level bounding boxes...")
                                try:
                                    ocr_data = pytesseract.image_to_data(image, lang='kan', output_type=Output.DICT)
                                    
                                    # Calculate statistics
                                    num_words = len(ocr_data['text'])
                                    confidences = [conf for conf in ocr_data['conf'] if conf > 0]
                                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                                    
                                    print(f"OCR detected {num_words} words")
                                    print(f"Average confidence: {avg_conf:.2f}")
                                    
                                    # Save raw OCR boxes to JSON for inspection
                                    with open(f"{log_dir}/rtc_ocr_boxes.json", "w", encoding="utf-8") as f:
                                        json.dump(ocr_data, f, indent=2, ensure_ascii=False)
                                    print(f"OCR boxes saved to: {log_dir}/rtc_ocr_boxes.json")
                                    
                                    # Extract fields using bilingual glossary and bounding boxes
                                    rtc_document = self._extract_rtc_fields_from_ocr(ocr_data, image.width, image.height, survey_no=survey_no)
                                    print(f"Extracted RTC document fields: {list(rtc_document.keys())}")
                                    
                                    # Log unmatched fields for debugging
                                    unmatched_fields = []
                                    for field, value in rtc_document.items():
                                        if isinstance(value, dict):
                                            if not any(v.get('kn', '') for v in value.values() if isinstance(v, dict)):
                                                unmatched_fields.append(field)
                                        elif isinstance(value, str) and not value:
                                            unmatched_fields.append(field)
                                    if unmatched_fields:
                                        print(f"Fields with no OCR match: {unmatched_fields}")
                                    
                                    rtc_data['rtc_document'] = rtc_document
                                    
                                except Exception as ocr_error:
                                    print(f"OCR failed: {ocr_error}")
                                    # Initialize empty rtc_document structure even if OCR fails
                                    rtc_data['rtc_document'] = {
                                        "survey_number": {"kn": survey_no, "en": survey_no, "needs_review": False},
                                        "hissa": {"kn": "", "en": "", "needs_review": False},
                                        "split_up_details": {
                                            "total_area": {"kn": "", "en": "", "needs_review": False},
                                            "phut_kharab_a": {"kn": "", "en": "", "needs_review": False},
                                            "phut_kharab_b": {"kn": "", "en": "", "needs_review": False},
                                            "remainder": {"kn": "", "en": "", "needs_review": False}
                                        },
                                        "land_revenue": {
                                            "land_revenue": {"kn": "", "en": "", "needs_review": False},
                                            "jodi": {"kn": "", "en": "", "needs_review": False},
                                            "cess": {"kn": "", "en": "", "needs_review": False},
                                            "water_rate": {"kn": "", "en": "", "needs_review": False},
                                            "total": {"kn": "", "en": "", "needs_review": False}
                                        },
                                        "soil_type": {"kn": "", "en": "", "needs_review": False},
                                        "patta": {"kn": "", "en": "", "needs_review": False},
                                        "occupant": {
                                            "name": {"kn": "", "en": "", "needs_review": False},
                                            "area": {"kn": "", "en": "", "needs_review": False},
                                            "khata_no": {"kn": "", "en": "", "needs_review": False}
                                        },
                                        "possession_nature": {"kn": "", "en": "", "needs_review": False},
                                        "cultivation_rows": []
                                    }
                        except Exception as e:
                            print(f"Error during image processing: {e}")
                            # Initialize empty rtc_document structure even if download fails
                            rtc_data['rtc_document'] = {
                                "survey_number": {"kn": survey_no, "en": survey_no, "needs_review": False},
                                "hissa": {"kn": "", "en": "", "needs_review": False},
                                "split_up_details": {
                                    "total_area": {"kn": "", "en": "", "needs_review": False},
                                    "phut_kharab_a": {"kn": "", "en": "", "needs_review": False},
                                    "phut_kharab_b": {"kn": "", "en": "", "needs_review": False},
                                    "remainder": {"kn": "", "en": "", "needs_review": False}
                                },
                                "land_revenue": {
                                    "land_revenue": {"kn": "", "en": "", "needs_review": False},
                                    "jodi": {"kn": "", "en": "", "needs_review": False},
                                    "cess": {"kn": "", "en": "", "needs_review": False},
                                    "water_rate": {"kn": "", "en": "", "needs_review": False},
                                    "total": {"kn": "", "en": "", "needs_review": False}
                                },
                                "soil_type": {"kn": "", "en": "", "needs_review": False},
                                "patta": {"kn": "", "en": "", "needs_review": False},
                                "occupant": {
                                    "name": {"kn": "", "en": "", "needs_review": False},
                                    "area": {"kn": "", "en": "", "needs_review": False},
                                    "khata_no": {"kn": "", "en": "", "needs_review": False}
                                },
                                "possession_nature": {"kn": "", "en": "", "needs_review": False},
                                "cultivation_rows": []
                            }
                    else:
                        print("No RTC image found in HTML")
                        # Initialize empty rtc_document structure if no image found
                        rtc_data['rtc_document'] = {
                            "survey_number": {"kn": survey_no, "en": survey_no, "needs_review": False},
                            "hissa": {"kn": "", "en": "", "needs_review": False},
                            "split_up_details": {
                                "total_area": {"kn": "", "en": "", "needs_review": False},
                                "phut_kharab_a": {"kn": "", "en": "", "needs_review": False},
                                "phut_kharab_b": {"kn": "", "en": "", "needs_review": False},
                                "remainder": {"kn": "", "en": "", "needs_review": False}
                            },
                            "land_revenue": {
                                "land_revenue": {"kn": "", "en": "", "needs_review": False},
                                "jodi": {"kn": "", "en": "", "needs_review": False},
                                "cess": {"kn": "", "en": "", "needs_review": False},
                                "water_rate": {"kn": "", "en": "", "needs_review": False},
                                "total": {"kn": "", "en": "", "needs_review": False}
                            },
                            "soil_type": {"kn": "", "en": "", "needs_review": False},
                            "patta": {"kn": "", "en": "", "needs_review": False},
                            "occupant": {
                                "name": {"kn": "", "en": "", "needs_review": False},
                                "area": {"kn": "", "en": "", "needs_review": False},
                                "khata_no": {"kn": "", "en": "", "needs_review": False}
                            },
                            "possession_nature": {"kn": "", "en": "", "needs_review": False},
                            "cultivation_rows": []
                        }
                    
                    # Run Gemini extraction for comprehensive field data using both screenshots (always run, outside image processing block)
                    print("Running Gemini extraction for comprehensive field data...")
                    gemini_output_path = f"{log_dir}/gemini_extraction.json"
                    
                    # Use both search page screenshot and RTC form screenshot
                    search_page_screenshot = f"{log_dir}/bhoomi_public_after_fetch.png"
                    rtc_form_screenshot = f"{log_dir}/full_rtc_document.png"
                    
                    gemini_images = []
                    if os.path.exists(search_page_screenshot):
                        gemini_images.append(search_page_screenshot)
                    if os.path.exists(rtc_form_screenshot):
                        gemini_images.append(rtc_form_screenshot)
                    
                    if gemini_images:
                        gemini_data = self._extract_with_gemini(gemini_images, gemini_output_path)
                        if gemini_data:
                            rtc_data['gemini_extraction'] = gemini_data
                            print("Gemini extraction completed and added to results")
                    else:
                        print("No screenshots found for Gemini extraction")
                    
                    # Store in rtc_data
                    rtc_data["full_rtc_html"] = full_rtc_html
                    
                    # Save to JSON (single output file only)
                    os.makedirs(log_dir, exist_ok=True)
                    with open(f"{log_dir}/bhoomi_public_result.json", "w", encoding="utf-8") as f:
                        json.dump(rtc_data, f, indent=2, ensure_ascii=False)
                    print(f"Results saved to {log_dir}/bhoomi_public_result.json")
                    
                    print("\n=== EXTRACTED DATA ===")
                    print(json.dumps(rtc_data, indent=2, ensure_ascii=False))
                    
                    return rtc_data
                    
                except Exception as e:
                    print(f"Error during scraping: {e}")
                    raise
                finally:
                    await browser.close()
        
        return await _fetch()


async def test_public_scraper():
    scraper = BhoomiPublicScraper()
    try:
        result = await scraper.fetch_rtc(
            district='BENGALURU',
            taluk='BANGALORE-NORTH',
            hobli='DASANAPURA1',
            village='ADAKAMARANAHALLI',
            survey_no='2'
        )
        print("\nTest completed successfully!")
        return result
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_public_scraper())
