import asyncio
from scrapers.bhoomi_mutation_scraper import BhoomiMutationScraper, ScraperException

async def test_mutation_scraper():
    scraper = BhoomiMutationScraper()
    try:
        print("=== Testing Bhoomi Mutation Register Scraper ===")
        print("Input (plain text names from GIS API):")
        print("District: BENGALURU")
        print("Taluk: Bangalore North (Additional)")
        print("Hobli: YALAHANKA1")
        print("Village: KRUSHNASAGARA")
        print("Survey Number: 2")
        print()
        
        result = await scraper.fetch_mutation(
            district='BENGALURU',
            taluk='Bangalore North (Additional)',
            hobli='YALAHANKA1',
            village='KRUSHNASAGARA',
            survey_no='2'
        )
    except ScraperException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mutation_scraper())
