import asyncio
import json
from scrapers.bhoomi_mutation_status_scraper import BhoomiMutationStatusScraper, ScraperException

async def test_mutation_status_scraper():
    scraper = BhoomiMutationStatusScraper()
    try:
        print("=== Testing Bhoomi Mutation Status Scraper ===")
        print("Input:")
        print("District: BENGALURU")
        print("Taluk: BANGALORE-NORTH")
        print("Hobli: DASANAPURA1")
        print("Village: ADAKAMARANAHALLI")
        print("Survey Number: 3")
        print()
        
        result = await scraper.fetch_mutation_status(
            district='BENGALURU',
            taluk='BANGALORE-NORTH',
            hobli='DASANAPURA1',
            village='ADAKAMARANAHALLI',
            survey_no='3'
        )
        
        print("\n=== MUTATION STATUS DATA ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except ScraperException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mutation_status_scraper())
