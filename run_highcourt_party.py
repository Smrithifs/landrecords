#!/usr/bin/env python3
"""
Karnataka High Court — Party Name search runner.
Site: https://judiciary.karnataka.gov.in/casemenu.php  (NOT the national eCourts portal)

What it does:
  1. Navigate to the Party Name search form.
  2. Fill:
       Bench              = Bengaluru  (code=B)
       Case Type          = WP, CP.KLRA, LRRP, RFA, RSA, CRP, WA  (loops all 7)
       Pet/Res/Don't know = Don't Know  (code=0)
       Party Name         = each owner name from mutation records
                            (English, Kannada names translated)
       Filing From        = 01-08-2025
       Filing To          = 01-08-2026
  3. ⚠️  Opens Chrome with the pre-filled form + captcha image.
       👉   YOU switch to the Chrome window, TYPE the 6-digit captcha IN CHROME,
            and CLICK the blue Submit button yourself.
       (if you'd prefer typing captcha in your terminal instead, use --captcha-mode terminal)
  4. Extracts whatever content appears in #det / #casedet into per-search JSON, HTML, PNG.
  5. Auto-resets the form (navigates back to casemenu.php) and proceeds to next search.
     By default stops after --max-searches searches.

First dry run (no browser) prints the full plan:
  python3 run_highcourt_party.py --dry-run

Actually run (10 searches):
  python3 run_highcourt_party.py                            # default: 10 searches, captcha in browser
  python3 run_highcourt_party.py --max-searches 20          # 20 searches
  python3 run_highcourt_party.py --max-searches 0           # run all planned searches (~112)
  python3 run_highcourt_party.py --case-type WP             # only WP
  python3 run_highcourt_party.py --no-aliases               # don't try name variants
  python3 run_highcourt_party.py --owner "Gali Hanumayya"   # only one name
  python3 run_highcourt_party.py --captcha-mode terminal    # prompts terminal for captcha digits
"""
import sys, os, argparse, asyncio, json
sys.path.insert(0, '/Users/smrithis/Desktop/landrecords')
from scrapers.karnataka_highcourt_party_scraper import (
    KarnatakaHCPartyScraper, OWNER_NAMES_FROM_MUTATIONS, CASE_TYPES_IN_ORDER,
    BENCH, BENCH_LABEL, FROM_DATE, TO_DATE, PET_RES_SELECTION, PET_RES_LABEL,
)


async def main():
    parser = argparse.ArgumentParser(description="Karnataka HC Party Name search runner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just print the search plan (no browser)")
    parser.add_argument("--case-type", action="append", dest="case_types", metavar="CT",
                        help="Run only these case types. Repeat flag for multiple. (default: all 7)")
    parser.add_argument("--owner", action="append", dest="owners", metavar="NAME",
                        help="Run only these owner search-names. Repeat flag for multiple.")
    parser.add_argument("--no-aliases", action="store_true",
                        help="Don't try alias variants of each owner name")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser hidden (not recommended — you need to see the captcha)")
    parser.add_argument("--captcha-mode", choices=["browser", "terminal"], default="browser",
                        help="Where captcha is entered: 'browser' = you type in Chrome (default), 'terminal' = you type digits in this terminal")
    parser.add_argument("--max-searches", type=int, default=10,
                        help="Stop after N searches. Use 0 to run all planned searches. (default: 10)")
    args = parser.parse_args()

    # Filter case_types
    case_types = args.case_types or CASE_TYPES_IN_ORDER[:]
    unknown_ct = [c for c in case_types if c.upper() not in [x.upper() for x in CASE_TYPES_IN_ORDER]]
    if unknown_ct:
        print(f"[WARN] Unknown case type(s): {unknown_ct}. Known: {CASE_TYPES_IN_ORDER}")

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

    total_searches = len(owners) * len(case_types) * (1 if args.no_aliases else (
        1 + max(len(o.get("aliases") or []) for o in owners) if owners else 1)
    )
    max_flag = args.max_searches if args.max_searches > 0 else None
    cap_mode_label = {
        "browser": "👉  YOU type captcha digits IN THE CHROME WINDOW and click Submit",
        "terminal": "👉  YOU type captcha digits in THIS TERMINAL (type r=refresh, s=skip)",
    }[args.captcha_mode]

    print("=" * 70)
    print("  KARNATAKA HIGH COURT — PARTY NAME SEARCH PLAN")
    print("=" * 70)
    print(f"  Site             : https://judiciary.karnataka.gov.in/casemenu.php")
    print(f"  Bench            : {BENCH_LABEL}  (code={BENCH})")
    print(f"  Pet/Res/Don't know : {PET_RES_LABEL}  (code={PET_RES_SELECTION})")
    print(f"  Filing date range: {FROM_DATE}  →  {TO_DATE}")
    print(f"  Captcha mode     : {cap_mode_label}")
    print(f"  Max searches     : {max_flag or total_searches}  (planned ~{total_searches})")
    print()
    print(f"  Case types ({len(case_types)})  : {', '.join(case_types)}")
    print()
    print(f"  Owners ({len(owners)}):")
    for o in owners:
        print(f"    • primary: {o['search_name']}")
        if not args.no_aliases and o.get("aliases"):
            print(f"        aliases: {', '.join(o['aliases'])}")
        print(f"        (Kannada source: {o['raw'][:70]})")
    print()
    print(f"  Output dir       : /Users/smrithis/Desktop/landrecords/logs/debug/karnataka_highcourt/")
    print("=" * 70)

    if args.dry_run:
        plan = {
            "bench_code": BENCH,
            "bench_label": BENCH_LABEL,
            "filing_from": FROM_DATE,
            "filing_to": TO_DATE,
            "pet_res_code": PET_RES_SELECTION,
            "pet_res_label": PET_RES_LABEL,
            "case_types": case_types,
            "owners": owners,
            "use_aliases": not args.no_aliases,
            "approx_total_searches": total_searches,
        }
        os.makedirs("/Users/smrithis/Desktop/landrecords/logs/debug/karnataka_highcourt", exist_ok=True)
        out = "/Users/smrithis/Desktop/landrecords/logs/debug/karnataka_highcourt/SEARCH_PLAN.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Dry run complete — plan saved to {out}")
        return

    if not owners:
        print("\n❌ No owners selected. Aborting.")
        sys.exit(2)

    scraper = KarnatakaHCPartyScraper()
    try:
        summary = await scraper.run(
            headless=args.headless,
            case_types=case_types,
            owners=owners,
            use_aliases=not args.no_aliases,
            captcha_mode=args.captcha_mode,
            max_searches=max_flag,
        )
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
