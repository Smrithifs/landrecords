#!/usr/bin/env python3
"""
Test Bhoomi Public Scraper with Gemini extraction (No captcha required)
This tests the public portal scraper with integrated Gemini extraction
"""
import asyncio
import json
from scrapers.bhoomi_public_scraper import BhoomiPublicScraper

async def test_bhoomi_public_gemini():
    scraper = BhoomiPublicScraper()
    try:
        print("=== Testing Bhoomi Public Scraper with Gemini Extraction ===")
        print("Input:")
        print("District: BENGALURU")
        print("Taluk: BANGALORE-NORTH")
        print("Hobli: DASANAPURA1")
        print("Village: ADAKAMARANAHALLI")
        print("Survey Number: 3")
        print("Hissa Number: 1")
        print("Note: This uses the public portal (no captcha) with Gemini extraction")
        print()

        result = await scraper.fetch_rtc(
            district='BENGALURU',
            taluk='BANGALORE-NORTH',
            hobli='DASANAPURA1',
            village='ADAKAMARANAHALLI',
            survey_no='3',
            hissa_no='1'
        )

        print("\n=== RTC DATA WITH GEMINI EXTRACTION ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bhoomi_public_gemini())