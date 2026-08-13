"""
Test script to parse RTC HTML using updated bilingual scraper.
"""

from scrapers.bhoomi_public_scraper import BhoomiPublicScraper
import json
import asyncio

def test_rtc_html_parsing():
    """Test parsing of RTC HTML with bilingual support."""
    
    # Load the English translation HTML
    html_file = "/Users/smrithis/Downloads/RTC_Document_English_Translation.html"
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print("HTML loaded successfully")
        
        # Test the updated scraper with bilingual support
        scraper = BhoomiPublicScraper()
        print("\n=== PARSING RTC HTML WITH BILINGUAL SUPPORT ===")
        rtc_data = scraper._parse_rtc_html(html_content)
        
        print(f"\n=== PARSED RTC DATA ===")
        print(json.dumps(rtc_data, indent=2, ensure_ascii=False))
        
        # Save to JSON
        output_file = "/Users/smrithis/Desktop/landrecords/logs/debug/rtc_parsed_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rtc_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def test_with_kannada_html():
    """Test parsing with Kannada HTML if available."""
    kannada_file = "/Users/smrithis/Downloads/RTC_Document_Kannada_Translation.html"
    
    try:
        with open(kannada_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        print("\n=== KANNADA HTML LOADED ===")
        
        scraper = BhoomiPublicScraper()
        print("\n=== PARSING KANNADA RTC HTML ===")
        rtc_data = scraper._parse_rtc_html(html_content)
        
        print(f"\n=== PARSED KANNADA RTC DATA ===")
        print(json.dumps(rtc_data, indent=2, ensure_ascii=False))
        
        # Save to JSON
        output_file = "/Users/smrithis/Desktop/landrecords/logs/debug/rtc_parsed_kannada_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rtc_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nKannada results saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"Kannada HTML file not found at {kannada_file}")
    except Exception as e:
        print(f"Error parsing Kannada HTML: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rtc_html_parsing()
    asyncio.run(test_with_kannada_html())
