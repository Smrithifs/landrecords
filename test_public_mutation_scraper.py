import asyncio
import json
from scrapers.bhoomi_public_mutation_scraper import BhoomiPublicMutationScraper, ScraperException

async def test_public_mutation_scraper():
    scraper = BhoomiPublicMutationScraper()
    try:
        print("=== Testing Bhoomi Public Mutation Register Scraper ===")
        print("Input:")
        print("District: BENGALURU")
        print("Taluk: BANGALORE-NORTH")
        print("Hobli: DASANAPURA1")
        print("Village: ADAKAMARANAHALLI")
        print("Survey Number: 3")
        print()
        
        result = await scraper.fetch_mutation(
            district='BENGALURU',
            taluk='BANGALORE-NORTH',
            hobli='DASANAPURA1',
            village='ADAKAMARANAHALLI',
            survey_no='3',
            max_mutations=None,  # Process all mutations
            headless=False,
            extract_details=False  # Only get status/summary, not detailed previews
        )
        
        print("\n=== MUTATION DATA ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except ScraperException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_public_mutation_scraper())
