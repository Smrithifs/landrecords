import asyncio
import json
import os
import re
from playwright.async_api import async_playwright, Error as PlaywrightError
from scrapers.bhoomi_public_mutation_scraper import (
    BhoomiPublicMutationScraper,
    _merge_no_dupes,
)

async def main():
    scraper = BhoomiPublicMutationScraper()
    district = 'BENGALURU'
    taluk = 'BANGALORE-NORTH'
    hobli = 'DASANAPURA1'
    village = 'ADAKAMARANAHALLI'
    survey_no = '3'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(scraper.mr_url)
            await page.wait_for_load_state("networkidle")
            print("Page loaded")
            await scraper._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
            mutation_rows = await scraper._extract_mutation_table(page)
            mutation_rows = mutation_rows[:2]
            print(f"\n>>> QUICK TEST: processing first {len(mutation_rows)} ONLY <<<\n")

            base_context = {
                "district": district, "taluk": taluk, "hobli": hobli,
                "village": village, "survey_no_query": survey_no,
            }
            index_entries = []
            successes = 0
            failures = 0

            for idx, row in enumerate(mutation_rows):
                mr = str(row.get("mr_number") or "")
                ty = str(row.get("transaction_year") or "")
                tn = str(row.get("transaction_no") or "")
                surv = str(row.get("survey_no") or survey_no)
                mutation_key = scraper._safe_filename(
                    f"MR{mr}", f"TY{ty.replace('-', '_')}", f"TN{tn}", f"S{surv.replace('/', '-')}"
                )
                print(f"\n{'='*60}\n[{idx+1}/{len(mutation_rows)}] Processing {mutation_key}\n{'='*60}")

                if idx > 0:
                    try:
                        if "MR_MutationExtract.aspx" not in page.url and "ReportPreview" in page.url:
                            await scraper._navigate_back_to_list(page)
                        sel_test = await page.query_selector_all('a:has-text("Select")')
                        if len(sel_test) < max(2, idx + 1):
                            print("  Table missing — re-filling form...")
                            await page.goto(scraper.mr_url)
                            await page.wait_for_load_state("networkidle")
                            await scraper._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
                    except Exception:
                        await page.goto(scraper.mr_url)
                        await page.wait_for_load_state("networkidle")
                        await scraper._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)

                record = {"id": mutation_key, "context": base_context,
                          "from_table_row": row, "selected_items": {}, "report_preview": None}

                try:
                    select_links = await page.query_selector_all('a:has-text("Select")')
                    assert idx < len(select_links), f"No Select at idx {idx}"
                    link = select_links[idx]
                    try:
                        await link.scroll_into_view_if_needed()
                        await link.click()
                    except PlaywrightError:
                        await link.evaluate("e => e.click()")
                    print("  [1/3] Clicked Select")
                    record["selected_items"] = await scraper._extract_selected_items(page)
                    print("  [2/3] Extracted Selected Items panel")
                except Exception as se:
                    print(f"  Select FAILED: {se}")
                    record["error"] = f"select: {se}"
                    failures += 1
                    await scraper._save_single_record(record, mutation_key)
                    index_entries.append(record)
                    continue

                preview_page = page
                try:
                    ps_list = ['#ctl00_MainContent_btnPreview', 'input[value*="Preview"]',
                               'button:has-text("Preview")', 'a:has-text("Preview")', 'text=Preview']
                    preview_clicked = False
                    pages_before = set(context.pages)
                    url_before = page.url

                    for ps in ps_list:
                        el = None
                        try:
                            el = await page.query_selector(ps)
                        except Exception:
                            pass
                        if not el or not await el.is_visible():
                            continue
                        await el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        got_it = False
                        try:
                            async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                                try:
                                    await el.click(timeout=7000)
                                except Exception:
                                    await el.evaluate("e => e.click()")
                            preview_clicked, preview_page = True, page
                            print(f"  [3/3] Clicked Preview ({ps}) — same-page nav")
                            got_it = True
                            break
                        except Exception:
                            pass
                        if not got_it:
                            try:
                                popup_task = asyncio.create_task(context.wait_for_event("page", timeout=25000))
                                try:
                                    try:
                                        await el.click(timeout=7000)
                                    except Exception:
                                        await el.evaluate("e => e.click()")
                                except Exception:
                                    pass
                                np = await popup_task
                                try:
                                    await np.wait_for_load_state("domcontentloaded", timeout=20000)
                                except Exception:
                                    await np.wait_for_timeout(3000)
                                preview_page, preview_clicked = np, True
                                print(f"  [3/3] Clicked Preview ({ps}) — NEW TAB: {np.url[:160]}")
                                got_it = True
                                break
                            except Exception as e:
                                print(f"    (popup wait for {ps}: {e})")
                        if not got_it:
                            try:
                                try:
                                    await el.click(timeout=7000)
                                except Exception:
                                    await el.evaluate("e => e.click()")
                                await page.wait_for_timeout(5000)
                                try:
                                    await page.wait_for_load_state("networkidle", timeout=15000)
                                except Exception:
                                    pass
                                nps = [p for p in context.pages if p not in pages_before]
                                if nps:
                                    preview_page = nps[0]
                                    try:
                                        await preview_page.wait_for_load_state("domcontentloaded", timeout=15000)
                                    except Exception:
                                        await preview_page.wait_for_timeout(3000)
                                    preview_clicked = True
                                    print(f"  [3/3] Clicked Preview ({ps}) — new tab detected: {preview_page.url[:160]}")
                                    break
                                if "ReportPreview" in page.url or page.url != url_before:
                                    preview_page, preview_clicked = page, True
                                    print(f"  [3/3] Clicked Preview ({ps}) — URL changed: {page.url[:160]}")
                                    break
                            except Exception:
                                continue

                    if not preview_clicked:
                        nps = [p for p in context.pages if p not in pages_before]
                        if nps:
                            preview_page = nps[0]
                            preview_clicked = True
                            print(f"  [3/3] Fallback new-tab found: {preview_page.url[:160]}")

                    if not preview_clicked:
                        print("  WARNING: No Preview confirmed. Trying current page anyway.")

                    try:
                        await preview_page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        await preview_page.wait_for_timeout(4000)
                    try:
                        await preview_page.bring_to_front()
                    except Exception:
                        pass
                    try:
                        await preview_page.wait_for_timeout(2500)
                    except Exception:
                        pass
                    print(f"  Extracting report from: {preview_page.url[:160]}")
                    record["report_preview"] = await scraper._extract_report_preview(preview_page, context, mutation_key)
                    successes += 1

                    try:
                        if preview_page is not page and len(context.pages) > 1:
                            try:
                                await preview_page.close()
                                print("  Closed preview tab, main list page preserved")
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception as pe:
                    print(f"  Preview FAILED: {pe}")
                    import traceback
                    traceback.print_exc()
                    record["error"] = f"preview: {pe}"
                    failures += 1

                merged = {"id": mutation_key, "context": base_context}
                merged["fields"] = _merge_no_dupes(
                    record.get("from_table_row") or {},
                    record.get("selected_items") or {},
                    (record.get("report_preview") or {}).get("report_header") or {},
                    (record.get("report_preview") or {}).get("footer") or {},
                )
                rpt = record.get("report_preview")
                if rpt:
                    merged["land_area"] = rpt.get("land_area_table", [])
                    merged["mutation_parties"] = rpt.get("parties_table", [])
                    for sk, dk in [("document_path", "document_path"),
                                   ("screenshot_path", "preview_screenshot"),
                                   ("html_path", "preview_html"),
                                   ("preview_page_url", "preview_url")]:
                        if rpt.get(sk):
                            merged[dk] = rpt[sk]
                if record.get("error"):
                    merged["error"] = record["error"]

                await scraper._save_single_record(merged, mutation_key)
                index_entries.append(merged)

                print(f"\n  === MERGED FIELDS (deduplicated) ===")
                for k, v in list(merged["fields"].items()):
                    print(f"    {k}: {v}")
                print(f"  land_area rows: {len(merged.get('land_area', []))}")
                print(f"  mutation_parties rows: {len(merged.get('mutation_parties', []))}")
                print(f"  preview_url: {merged.get('preview_url')}")

                try:
                    if preview_page is page:
                        await scraper._navigate_back_to_list(page)
                    else:
                        print("  Preview was a new tab — list page is still open, no back nav needed")
                        try:
                            await page.bring_to_front()
                        except Exception:
                            pass
                except Exception as be:
                    print(f"  Back issue: {be}")

            combined_path = os.path.join(scraper.mutations_dir, "ALL_MUTATIONS_COMBINED.json")
            combined = {
                "search": base_context,
                "total_found": len(mutation_rows),
                "total_processed": len(index_entries),
                "successful_extractions": successes,
                "failures": failures,
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "mutations": index_entries,
            }
            with open(combined_path, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, ensure_ascii=False)

            print(f"\n{'='*60}")
            print(f"QUICK TEST SUMMARY (first 2 mutations only)")
            print(f"  Successful:  {successes}")
            print(f"  Failed:      {failures}")
            print(f"  Combined:    {combined_path}")
            print(f"  Individual:  {scraper.mutations_dir}/MR*.json")
            print(f"{'='*60}")

        finally:
            try:
                all_pages = context.pages
                for pp in all_pages:
                    try:
                        await pp.close()
                    except Exception:
                        pass
            except Exception:
                pass
            await browser.close()

asyncio.run(main())
