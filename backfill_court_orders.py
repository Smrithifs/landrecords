#!/usr/bin/env python3
import sys, os, json, shutil
sys.path.insert(0, '/Users/smrithis/Desktop/landrecords')
from scrapers.bhoomi_public_mutation_scraper import BhoomiPublicMutationScraper

s = BhoomiPublicMutationScraper()
mut_dir = s.mutations_dir
co_dir = s.court_orders_dir
os.makedirs(co_dir, exist_ok=True)

print(f"Mutations dir : {mut_dir}")
print(f"Court orders  : {co_dir}")
print()

copied = []
for fname in sorted(os.listdir(mut_dir)):
    if not fname.endswith(".json") or fname.startswith("ALL_"):
        continue
    mpath = os.path.join(mut_dir, fname)
    with open(mpath) as f:
        rec = json.load(f)
    if not s._is_court_order(rec):
        mtype = (rec.get("fields") or {}).get("mutation_type", "?")
        print(f"  skip  (non-court): {fname}  | type={mtype}")
        continue
    dst = os.path.join(co_dir, fname)
    shutil.copy2(mpath, dst)
    print(f"  COPY  (JSON)     : {fname}  ->  court_orders/")
    copied.append(rec)
    for k in ("preview_screenshot", "preview_html", "document_path"):
        src = rec.get(k)
        if src and os.path.isfile(src):
            a_dst = os.path.join(co_dir, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(a_dst):
                shutil.copy2(src, a_dst)
            print(f"         + asset   : {os.path.basename(src)}")

combined = {
    "source": "backfill from existing mutations dir",
    "generated_at": __import__("datetime").datetime.now().isoformat(),
    "court_orders_found": len(copied),
    "court_orders": copied,
}
idx = os.path.join(co_dir, "ALL_COURT_ORDERS_COMBINED.json")
with open(idx, "w", encoding="utf-8") as f:
    json.dump(combined, f, indent=2, ensure_ascii=False)
print(f"\nWritten combined index ({len(copied)} court orders) -> {idx}")
