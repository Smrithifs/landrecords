import asyncio
from scrapers.bhoomi_scraper import BhoomiScraper, ScraperException

async def test_scraper():
    scraper = BhoomiScraper()
    try:
        print("=== Testing Bhoomi RTC Scraper ===")
        print("Input (plain text names from GIS API):")
        print("District: BENGALURU")
        print("Taluk: Bangalore North (Additional)")
        print("Hobli: YALAHANKA1")
        print("Village: KRUSHNASAGARA")
        print("Survey Number: 2")
        print()
        
        result = await scraper.fetch_rtc(
            district='BENGALURU',
            taluk='Bangalore North (Additional)',
            hobli='YALAHANKA1',
            village='KRUSHNASAGARA',
            survey_no='2'
        )
    except ScraperException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_scraper())
