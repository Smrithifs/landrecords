#!/usr/bin/env python3
"""
eSwathu ekatha runner
Site: https://eswathu.karnataka.gov.in/

What it does:
  1. Navigate to eSwathu URL
  2. Click "Existing Khata"
  3. Fill form with owner details
  4. Search for owner name
  5. If found, click "draft ekATHA"
  6. Extract and save details
"""
import sys, os, argparse, asyncio, json
sys.path.insert(0, '/Users/smrithis/Desktop/landrecords')
from scrapers.eswathu_ekatha_scraper import EswathuEkathaScraper, OWNER_NAMES_FROM_MUTATIONS


async def main():
    parser = argparse.ArgumentParser(description="eSwathu ekatha runner")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser hidden (not recommended)")
    parser.add_argument("--no-aliases", action="store_true",
                        help="Don't try alias variants of each owner name")
    parser.add_argument("--max-searches", type=int, default=1,
                        help="Stop after N searches. (default: 1)")
    parser.add_argument("--owner", action="append", dest="owners", metavar="NAME",
                        help="Run only these owner search-names. Repeat flag for multiple.")
    args = parser.parse_args()

    # Filter owners
    owners = OWNER_NAMES_FROM_MUTATIONS[:]
    if args.owners:
        want = [n.lower() for n in args.owners]
        filtered = []
        for o in owners:
            names_to_check = [o["search_name"]] + (o.get("aliases") or [])
            if any(w in n.lower() for n in names_to_check for w in want):
                filtered.append(o)
        owners = filtered

    max_flag = args.max_searches if args.max_searches > 0 else None

    print("=" * 70)
    print("  ESWATHU EKATHA SEARCH")
    print("=" * 70)
    print(f"  Max searches     : {max_flag or len(owners) * 3}")
    print()
    print(f"  Owners ({len(owners)}):")
    for o in owners:
        print(f"    • primary: {o['search_name']}")
        if not args.no_aliases and o.get("aliases"):
            print(f"        aliases: {', '.join(o['aliases'])}")
        print(f"        (Kannada source: {o['raw'][:70]})")
    print()
    print(f"  Output dir       : /Users/smrithis/Desktop/landrecords/logs/debug/eswathu_ekatha/")
    print("=" * 70)

    if not owners:
        print("\n❌ No owners selected. Aborting.")
        sys.exit(2)

    scraper = EswathuEkathaScraper()
    try:
        summary = await scraper.run(
            headless=args.headless,
            owners=owners,
            use_aliases=not args.no_aliases,
            max_searches=max_flag,
        )
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
