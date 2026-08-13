import asyncio
import os
import time
import re
import json
from typing import Dict, Optional, List, Any
from playwright.async_api import async_playwright, Error as PlaywrightError, Page
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
from scrapers.bhoomi_base import BhoomiBaseScraper, ScraperException
from scrapers.bhoomi_public_mutation_scraper import (
    _merge_no_dupes,
    BhoomiPublicMutationScraper,
)


class BhoomiMutationScraper(BhoomiBaseScraper):
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        super().__init__(username, password)
        self.mr_url = "https://landrecords.karnataka.gov.in/Service11/MR_MutationExtract.aspx"
        self.log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
        self.mutations_dir = os.path.join(self.log_dir, "mutations_auth")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.mutations_dir, exist_ok=True)
        self._delegate = BhoomiPublicMutationScraper.__new__(BhoomiPublicMutationScraper)
        self._delegate.mr_url = self.mr_url
        self._delegate.log_dir = self.log_dir
        self._delegate.mutations_dir = self.mutations_dir

    async def _fill_form_and_fetch(self, page: Page, district: str, taluk: str, hobli: str, village: str, survey_no: str):
        district_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpdist', district)
        if not district_value:
            raise ScraperException(f"District not found: {district}")
        await page.select_option('#ctl00_MainContent_drpdist', value=district_value)

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drptaluk'):
            raise ScraperException("Taluk dropdown failed to load")
        taluk_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drptaluk', taluk)
        if not taluk_value:
            raise ScraperException(f"Taluk not found: {taluk}")
        await page.select_option('#ctl00_MainContent_drptaluk', value=taluk_value)

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drphobli'):
            raise ScraperException("Hobli dropdown failed to load")
        hobli_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drphobli', hobli)
        if not hobli_value:
            raise ScraperException(f"Hobli not found: {hobli}")
        await page.select_option('#ctl00_MainContent_drphobli', value=hobli_value)

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drpvillage'):
            raise ScraperException("Village dropdown failed to load")
        village_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpvillage', village)
        if not village_value:
            raise ScraperException(f"Village not found: {village}")
        await page.select_option('#ctl00_MainContent_drpvillage', value=village_value)

        await page.fill('#ctl00_MainContent_txtSurvey', survey_no)

        fetch_button = await page.query_selector('#ctl00_MainContent_btnFetch')
        if fetch_button:
            try:
                if not await fetch_button.is_enabled():
                    print("Fetch button disabled, waiting...")
                    try:
                        await page.wait_for_selector('#ctl00_MainContent_btnFetch:not([disabled])', timeout=30000)
                    except PlaywrightError:
                        pass
                try:
                    await fetch_button.click()
                except PlaywrightError:
                    await fetch_button.evaluate("b => b.click()")
                print("Clicked Fetch Details button")
            except Exception as e:
                raise ScraperException(f"Failed to click Fetch Details: {e}")
        else:
            raise ScraperException("Fetch Details button not found")

        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightError:
            pass
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_selector(
                'div:has-text("LOADING"), .loading, #loading, [id*="loading"], [class*="loading"]',
                state="hidden", timeout=60000
            )
        except PlaywrightError:
            pass
        await page.wait_for_timeout(2000)
        print("Fetch Details completed")

    async def fetch_mutation(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str
    ) -> Dict:
        async def _fetch():
            if self._is_session_valid():
                print("Using cached session (age: {:.1f} minutes)".format(
                    (time.time() - self._session_timestamp) / 60
                ))
                cookies_for_playwright = self._session_cache
            else:
                print("Session cache expired or missing, performing fresh login")
                cookies_for_playwright = await self._http_login()
                self._update_session_cache(cookies_for_playwright)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                await context.add_cookies(cookies_for_playwright)
                page = await context.new_page()
                try:
                    await page.goto(self.mr_url)
                    await page.wait_for_load_state("networkidle")
                    print("Navigated to Mutation Extract page")
                    if "Login" in page.url:
                        self._session_cache = None
                        self._session_timestamp = None
                        raise ScraperException("Not logged in - session cookies expired")

                    await self._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
                    mutation_rows = await self._delegate._extract_mutation_table(page)
                    print(f"\nTotal mutations found: {len(mutation_rows)}")

                    base_context = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no_query": survey_no,
                    }

                    index_entries: List[Dict] = []
                    successes = 0
                    failures = 0

                    for idx, row in enumerate(mutation_rows):
                        mr = str(row.get("mr_number") or "")
                        ty = str(row.get("transaction_year") or "")
                        tn = str(row.get("transaction_no") or "")
                        surv = str(row.get("survey_no") or survey_no)
                        mutation_key = self._delegate._safe_filename(
                            f"MR{mr}", f"TY{ty.replace('-', '_')}", f"TN{tn}", f"S{surv.replace('/', '-')}"
                        )
                        print(f"\n{'='*60}")
                        print(f"[{idx+1}/{len(mutation_rows)}] Processing {mutation_key}")
                        print(f"{'='*60}")

                        if idx > 0:
                            try:
                                if "MR_MutationExtract.aspx" not in page.url and "ReportPreview" in page.url:
                                    await self._delegate._navigate_back_to_list(page)
                                try:
                                    sel_test = await page.query_selector_all('a:has-text("Select")')
                                    if len(sel_test) < max(2, idx + 1):
                                        print("  Table missing — re-filling form...")
                                        await page.goto(self.mr_url)
                                        await page.wait_for_load_state("networkidle")
                                        await self._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
                                except Exception:
                                    await page.goto(self.mr_url)
                                    await page.wait_for_load_state("networkidle")
                                    await self._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
                            except Exception as refill_e:
                                print(f"  (refill issue: {refill_e}, continuing)")

                        record: Dict[str, Any] = {
                            "id": mutation_key,
                            "context": base_context,
                            "from_table_row": row,
                            "selected_items": {},
                            "report_preview": None,
                        }

                        try:
                            select_links = await page.query_selector_all('a:has-text("Select")')
                            if idx >= len(select_links):
                                print(f"  WARNING: only {len(select_links)} Select links, need idx {idx}")
                            assert idx < len(select_links), f"No Select link at index {idx}"
                            link = select_links[idx]
                            try:
                                await link.scroll_into_view_if_needed()
                                await link.click()
                            except PlaywrightError:
                                await link.evaluate("e => e.click()")
                            print("  [1/3] Clicked Select")
                            record["selected_items"] = await self._delegate._extract_selected_items(page)
                            print("  [2/3] Extracted Selected Items panel")
                        except Exception as sel_err:
                            print(f"  Select step failed: {sel_err}")
                            record["error"] = f"select_failed: {sel_err}"
                            failures += 1
                            await self._save_single_record(record, mutation_key)
                            index_entries.append(record)
                            continue

                        try:
                            ps_list = ['#ctl00_MainContent_btnPreview', 'input[value*="Preview"]',
                                       'button:has-text("Preview")', 'a:has-text("Preview")', 'text=Preview']
                            preview_clicked = False
                            preview_page = page
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
                                        popup_task = asyncio.create_task(context.wait_for_event("page", timeout=20000))
                                        try:
                                            try:
                                                await el.click(timeout=7000)
                                            except Exception:
                                                await el.evaluate("e => e.click()")
                                        except Exception:
                                            pass
                                        np = await popup_task
                                        try:
                                            await np.wait_for_load_state("domcontentloaded", timeout=15000)
                                        except Exception:
                                            pass
                                        preview_page, preview_clicked = np, True
                                        print(f"  [3/3] Clicked Preview ({ps}) — NEW TAB: {np.url[:150]}")
                                        got_it = True
                                        break
                                    except Exception:
                                        pass
                                if not got_it:
                                    try:
                                        try:
                                            await el.click(timeout=7000)
                                        except Exception:
                                            await el.evaluate("e => e.click()")
                                        await page.wait_for_timeout(3000)
                                        try:
                                            await page.wait_for_load_state("networkidle", timeout=15000)
                                        except Exception:
                                            pass
                                        nps = [p for p in context.pages if p not in pages_before]
                                        if nps:
                                            preview_page = nps[0]
                                            try:
                                                await preview_page.wait_for_load_state("domcontentloaded", timeout=10000)
                                            except Exception:
                                                pass
                                            preview_clicked = True
                                            print(f"  [3/3] Clicked Preview ({ps}) — new tab detected: {preview_page.url[:150]}")
                                            break
                                        if "ReportPreview" in page.url or page.url != url_before:
                                            preview_page, preview_clicked = page, True
                                            print(f"  [3/3] Clicked Preview ({ps}) — URL changed: {page.url[:150]}")
                                            break
                                    except Exception:
                                        continue

                            if not preview_clicked:
                                nps = [p for p in context.pages if p not in pages_before]
                                if nps:
                                    preview_page, preview_clicked = nps[0], True
                                    print(f"  [3/3] Fallback new-page check found preview: {preview_page.url[:150]}")
                            if not preview_clicked:
                                print("  WARNING: No Preview nav confirmed. Extracting on current page anyway.")

                            try:
                                await preview_page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                pass
                            try:
                                await preview_page.bring_to_front()
                            except Exception:
                                pass
                            print(f"  Extracting report from: {preview_page.url[:150]}")
                            record["report_preview"] = await self._delegate._extract_report_preview(
                                preview_page, context, mutation_key
                            )
                            successes += 1

                            try:
                                if preview_page is not page and len(context.pages) > 1:
                                    try:
                                        await preview_page.close()
                                        print("  Closed preview tab")
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        except Exception as prev_err:
                            print(f"  Preview step failed: {prev_err}")
                            import traceback
                            traceback.print_exc()
                            record["error"] = f"preview_failed: {prev_err}"
                            failures += 1

                        merged_clean: Dict[str, Any] = {
                            "id": mutation_key,
                            "context": base_context,
                        }
                        sources = [
                            record.get("from_table_row") or {},
                            record.get("selected_items") or {},
                            (record.get("report_preview") or {}).get("report_header") or {},
                            (record.get("report_preview") or {}).get("footer") or {},
                        ]
                        merged_clean["fields"] = _merge_no_dupes(*sources)
                        rpt = record.get("report_preview")
                        if rpt:
                            merged_clean["land_area"] = rpt.get("land_area_table", [])
                            merged_clean["mutation_parties"] = rpt.get("parties_table", [])
                            for path_key in ("document_path", "screenshot_path", "html_path", "preview_page_url"):
                                if rpt.get(path_key):
                                    if path_key == "screenshot_path":
                                        merged_clean["preview_screenshot"] = rpt[path_key]
                                    elif path_key == "html_path":
                                        merged_clean["preview_html"] = rpt[path_key]
                                    elif path_key == "preview_page_url":
                                        merged_clean["preview_url"] = rpt[path_key]
                                    else:
                                        merged_clean[path_key] = rpt[path_key]
                        if record.get("error"):
                            merged_clean["error"] = record["error"]

                        await self._save_single_record(merged_clean, mutation_key)
                        index_entries.append(merged_clean)

                        try:
                            await self._delegate._navigate_back_to_list(page)
                        except Exception as back_err:
                            print(f"  Back nav issue: {back_err}")

                    combined_path = os.path.join(self.mutations_dir, "ALL_MUTATIONS_COMBINED.json")
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
                    print(f"SUMMARY (AUTHENTICATED)")
                    print(f"  Total found:       {len(mutation_rows)}")
                    print(f"  Successful:        {successes}")
                    print(f"  Failed:            {failures}")
                    print(f"  Individual JSONs:  {self.mutations_dir}/MR*__*.json")
                    print(f"  Combined index:    {combined_path}")
                    print(f"{'='*60}")

                    print("\n=== SAMPLE (first mutation merged fields) ===")
                    for i, md in enumerate(index_entries[:1]):
                        print(f"\nMutation ID: {md.get('id')}")
                        fields = md.get("fields", {})
                        for k, v in list(fields.items())[:20]:
                            print(f"  {k}: {v}")
                        if len(fields) > 20:
                            print(f"  ... +{len(fields)-20} more fields")
                        print(f"  Land area rows:  {len(md.get('land_area', []))}")
                        print(f"  Party rows:      {len(md.get('mutation_parties', []))}")

                    return combined

                finally:
                    await browser.close()

        return await self._retry_with_backoff(_fetch)

    async def _save_single_record(self, record: Dict, mutation_key: str):
        path = os.path.join(self.mutations_dir, f"{mutation_key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {os.path.basename(path)}")
        return path
