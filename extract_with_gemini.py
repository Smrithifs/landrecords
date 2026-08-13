#!/usr/bin/env python3
"""
Extract RTC document details using Gemini Vision API.
Sends the RTC image to Gemini and requests structured JSON output with English translation.
"""

import google.genai as genai
import json
import base64
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.example", override=False)

# Configure Gemini API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
client = genai.Client(api_key=API_KEY)

# Path to RTC images (can be multiple)
IMAGE_PATHS = [
    "logs/debug/rtc_page.png",  # Default single image
    # Add more paths for multiple screenshots
]
OUTPUT_PATH = "logs/debug/gemini_extraction.json"

def extract_rtc_with_gemini(image_paths=None):
    """Extract RTC details using Gemini Vision API from one or more images."""
    
    if image_paths is None:
        image_paths = IMAGE_PATHS
    
    # Load all images
    images_data = []
    for img_path in image_paths:
        path = Path(img_path)
        if not path.exists():
            print(f"Error: Image not found at {img_path}")
            return None
        
        with open(path, "rb") as f:
            images_data.append(f.read())
    
    print(f"Loaded {len(images_data)} image(s)")
    
    # Prompt for extraction - comprehensive for both pages
    prompt = """
    Analyze this RTC (Record of Rights, Tenancy and Crops) document image and extract all the details.
    
    This could be either:
    1. Search/Results Page - showing district, taluk, hobli, village selection, survey number, owner table
    2. RTC Form Page (Village Form No. 1) - showing detailed land records
    
    Extract ALL information from the image and return the result as a JSON object with Kannada and English side by side.
    
    Here's the complete extraction with actual field values (not just labels) from both screenshots, in Kannada and English side by side.

    ## Image 1 — Search / Results Page

    | Field (KN → EN) | Value |
    |---|---|
    | ಜಿಲ್ಲೆ → District | BENGALURU (ಬೆಂಗಳೂರು) |
    | ತಾಲ್ಲೂಕು → Taluk | BANGALORE-NORTH (ಬೆಂಗಳೂರು ಉತ್ತರ) |
    | ಹೋಬಳಿ → Hobli | DASANAPURA1 (ದಾಸನಪುರ1) |
    | ಗ್ರಾಮ → Village | ADAKAMARANAHALLI (ಅಡಕಮಾರನಹಳ್ಳಿ) |
    | ಸರ್ವೆ ನಂಬರು → Survey Number | 2 |
    | ಸರ್ನಾಕ್ → Surnoc | * |
    | ಹಿಸ್ಸಾ ನಂ → Hissa No | * |
    | ಅವಧಿ → Period | 2001-10-18 00:00:00 To Till Date (2026-2027) |
    | ಭೂಮಿ ಐಡಿ → Land ID | 6127 7900 0003 |
    | ಪ್ರಗತಿಯಲ್ಲಿರುವ ಮ್ಯುಟೇಶನ್ → OnGoing Mutation | No |
    | PYKI | No |

    **Owner Table:**

    | Owner (ಹೆಸರು) | Extent (ವಿಸ್ತೀರ್ಣ) | Category (ವರ್ಗ) | Gov Restriction | Court Stay | Alienated |
    |---|---|---|---|---|---|
    | ತಳವಾಳ ಇನಾಂತಿದಾರ್ ದಾಸ ದಾಸ → Talawala Inamdar Dasa Dasa | 0.1.0 | Private | No | No | No |
    | ಮಾರಹನುಮ ಹನುಮಂತ → Marahanuma Hanumantha | 0.0.0 | Private | No | No | No |

    ## Image 2 — RTC Form (Village Form No. 1)

    | Header | Value |
    |---|---|
    | ತಾಲ್ಲೂಕು → Taluk | ಬೆಂಗಳೂರು ಉತ್ತರ → Bengaluru North |
    | ಹೋಬಳಿ → Hobli | ದಾಸನಪುರ1 → Dasanapura1 |
    | ಗ್ರಾಮ → Village | ಅಡಕಮಾರನಹಳ್ಳಿ → Adakamaranahalli |
    | Print Page No | 1/1, Village Account Form No. 2 |
    | ಮಾನ್ಯತೆ → Valid from | 18-10-2001 00:00:00 To Till Date |

    | # | Field (KN → EN) | Value (KN) | Value (EN) |
    |---|---|---|---|
    | 1 | ಸರ್ವೆ ನಂಬರು → Survey Number | 2 * | 2 * |
    | 2 | ಹಿಸ್ಸಾ → Hissa | * | * |
    | 3 | ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ → Total Area | 0.01.00.00 | 0 acre, 1 gunta, 00, 00 |
    | — | ಪೂಟ್ ಖರಾಬ್ (ಅ) → Phut Kharab (A) | (blank) | (blank) |
    | — | ಪೂಟ್ ಖರಾಬ್ (ಬ) → Phut Kharab (B) | (blank) | (blank) |
    | — | ಉಳಿದದ್ದು → Remainder | 0.01.00.00 | 0.01.00.00 |
    | 4 | ಭೂ ಕಂದಾಯ → Land Revenue (a) | ₹0.06 | Rs. 0.06 |
    | — | ಜೋಡಿ → Jodi (b) | ₹0.00 | Rs. 0.00 |
    | — | ಸೆಸ್ಸುಗಳು → Cess (c) | ₹0.00 | Rs. 0.00 |
    | — | ನೀರಿನ ದರ → Water Rate (d) | ₹0.00 | Rs. 0.00 |
    | — | ಒಟ್ಟು → Total | ₹0.06 | Rs. 0.06 |
    | 5 | ಮಣ್ಣಿನ ನಮೂನೆ → Soil Type | ಕಪ್ಪು | Black |
    | 6 | ಪಟ್ಟಾ → Patta | ಇನಾಂ | Inam (land grant) |
    | 7 | ಮರಗಳ ಸಂಖ್ಯೆ → Number of Trees | (blank) | (blank) |
    | 8 | ಸೀರಾವರಿ ವಿಸ್ತೀರ್ಣ → Irrigation Area | (blank) | (blank) |
    | 9 | ಕಟ್ಟೆದಾರನ ಹೆಸರು → Occupant Name | ತಳವಾಳ ಇನಾಂತಿದಾರ್ ದಾಸ ಬಿನ್ ದಾಸ | Talawala Inamdar Dasa Bin Dasa |
    | — | ವಿಸ್ತೀರ್ಣ → Area | 0.01.00.00 | 0.01.00.00 |
    | — | ಖಾತೆ ನಂ → Khata No. | 3 | 3 |
    | — | ಜಂಟಿ ಮಾಲೀಕ → Joint Owner | ಮಾರಹನುಮ ಬಿನ್ ಹನುಮಂತ (ಮೇಲಿನ ಜಂಟಿ) | Marahanuma Bin Hanumantha (Joint, as above) |
    | 10 | ಸ್ವಾಧೀನತೆಯ ರೀತಿ → Nature of Possession | RR 5, RR 4 | RR 5, RR 4 |
    | 11 | ಹಕ್ಕುಗಳು / ಋಣಗಳು → Rights / Liabilities | (blank) | (blank) |

    **Section 12–13: Cultivation Details, Year 2026-2027, ಮುಂಗಾರು (Kharif season)**

    | Cultivator (KN → EN) | Method (ಪದ್ಧತಿ) | Non-mixed Area | Mixed Area | Total Area | Yield/Acre |
    |---|---|---|---|---|---|
    | ತಳವಾಳ ಇನಾಂತಿದಾರ್ ದಾಸ ಬಿನ್ ದಾಸ → Talawala Inamdar Dasa Bin Dasa | ಸ್ವಂತ → Self | 0.00.00.00 | 0.00.00.00 | 0.00.00.00 | 0.00 |
    | ಮಾರಹನುಮ ಬಿನ್ ಹನುಮಂತ → Marahanuma Bin Hanumantha | ಸ್ವಂತ → Self | 0.00.00.00 | 0.00.00.00 | 0.00.00.00 | 0.00 |
    | ಮಾರಹನುಮ-೦ → Marahanuma-0 | ಸ್ವಂತ → Self | 0.00.00.00 | 0.00.00.00 | 0.00.00.00 | 0.00 |

    Watermark: ಫಾರ್ ವಿಯಿಂಗ್ ಓನ್ಲಿ → "For Viewing Only"

    IMPORTANT:
    - Extract ALL text from the image, including Kannada text
    - Provide both Kannada and English values side by side
    - For names, provide transliteration to English
    - For numerical values, keep them as-is
    - Extract ALL fields from both search/results page and RTC form page
    - Return ONLY valid JSON, no additional text
    - If a field is empty or not found, use empty string ""
    - The variables remain same for other places user tries to search but value changes so generalize it too
    """
    
    try:
        # First, try to list available models to see what's accessible
        print("Listing available models...")
        try:
            models = client.models.list()
            print(f"Available models: {[m.name for m in models]}")
        except Exception as e:
            print(f"Could not list models: {e}")
        
        # Try different model names (using available models from the list)
        model_names = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-image", "gemini-3.1-flash-image"]
        
        for model_name in model_names:
            try:
                print(f"Trying model: {model_name}")
                
                # Build contents with prompt and all images
                contents = [prompt]
                for img_data in images_data:
                    contents.append(
                        genai.types.Part.from_bytes(
                            data=img_data,
                            mime_type="image/png"
                        )
                    )
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                print(f"Success with model: {model_name}")
                break
            except Exception as e:
                print(f"Failed with model {model_name}: {e}")
                continue
        else:
            raise Exception("All model attempts failed")
        
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
        output_path = Path(OUTPUT_PATH)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)
        
        print(f"Extraction complete. Results saved to {OUTPUT_PATH}")
        print(json.dumps(result_json, indent=2, ensure_ascii=False))
        
        return result_json
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    extract_rtc_with_gemini()
