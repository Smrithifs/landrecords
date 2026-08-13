"""
Test script for eCourts scraper.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.ecourts_scraper import ECourtsScraper

async def main():
    """Test eCourts scraper."""
    config = {
        'headless': False,
        'screenshot_dir': 'logs/screenshots'
    }
    
    scraper = ECourtsScraper(config)
    
    try:
        result = await scraper.scrape({
            'owner_name': 'Chikkagowda'
        })
        
        print(f"\n=== Search Complete ===")
        print(f"Total cases found: {result['total_cases_found']}")
        print(f"Years searched: {result['years_searched']}")
        print(f"Results saved to: logs/debug/ecourts_result.json")
        
        if result['cases']:
            print(f"\nSample case:")
            import json
            print(json.dumps(result['cases'][0], indent=2))
        
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
