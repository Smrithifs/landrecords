#!/usr/bin/env python3
"""
Flexible runner for Bhoomi Public Mutation Scraper.
Works for ANY district / taluk / hobli / village / survey number.
Automatically handles however many mutation entries the site returns.

Usage examples:
  # Default demo (BENGALURU / BANGALORE-NORTH / DASANAPURA1 / ADAKAMARANAHALLI / 3)
  python3 run_mutation_any.py

  # Same village, different survey number
  python3 run_mutation_any.py --survey 5

  # Full custom location + survey
  python3 run_mutation_any.py \
      --district BENGALURU \
      --taluk BANGALORE-SOUTH \
      --hobli JAYANAGARA \
      --village JAYANAGARA \
      --survey 12

  # Process only first 5 mutation entries
  python3 run_mutation_any.py --survey 3 --limit 5

  # Headless mode (no visible browser window)
  python3 run_mutation_any.py --survey 3 --headless
"""
import sys
import argparse
sys.path.insert(0, '/Users/smrithis/Desktop/landrecords')

import asyncio
import os
from scrapers.bhoomi_public_mutation_scraper import BhoomiPublicMutationScraper, ScraperException


async def main():
    parser = argparse.ArgumentParser(description="Bhoomi Mutation Scraper (any survey/village)")
    parser.add_argument("--district", default="BENGALURU", help="District name")
    parser.add_argument("--taluk", default="BANGALORE-NORTH", help="Taluk name")
    parser.add_argument("--hobli", default="DASANAPURA1", help="Hobli name")
    parser.add_argument("--village", default="ADAKAMARANAHALLI", help="Village name")
    parser.add_argument("--survey", default="3", help="Survey number")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Max number of mutation rows to process (default: all)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless (invisible) mode")
    args = parser.parse_args()

    scraper = BhoomiPublicMutationScraper()

    print("=" * 60)
    print("  BHOOMI PUBLIC MUTATION SCRAPER — Generalised Runner")
    print("=" * 60)
    print(f"  District : {args.district}")
    print(f"  Taluk    : {args.taluk}")
    print(f"  Hobli    : {args.hobli}")
    print(f"  Village  : {args.village}")
    print(f"  Survey   : {args.survey}")
    if args.limit:
        print(f"  Limit    : first {args.limit} entries only")
    print(f"  Headless : {'yes' if args.headless else 'no'}")
    print("=" * 60)
    print()

    try:
        result = await scraper.fetch_mutation(
            district=args.district,
            taluk=args.taluk,
            hobli=args.hobli,
            village=args.village,
            survey_no=args.survey,
            max_mutations=None,
            headless=args.headless,
            extract_details=True,
        )
        print()
        print("=" * 60)
        print("  DONE")
        print("=" * 60)
        print(f"  Total found        : {result.get('total_found')}")
        print(f"  Processed          : {result.get('total_processed')}")
        print(f"  Successful         : {result.get('successful_extractions')}")
        print(f"  Failed             : {result.get('failures')}")
        print(f"  Output directory   : {scraper.mutations_dir}")
        print(f"  Combined index     : "
              f"{os.path.join(scraper.mutations_dir, 'ALL_MUTATIONS_COMBINED.json')}")
        print("=" * 60)

    except ScraperException as e:
        print(f"\n[Scraper Error] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Unexpected Error] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
