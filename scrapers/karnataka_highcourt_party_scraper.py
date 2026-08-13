"""
Karnataka High Court — Party Name search scraper.
URL: https://judiciary.karnataka.gov.in/casemenu.php

Uses the "Search by Party Name" panel:
  - Bench = Bengaluru
  - Cycles through Case Types:  WP, CP.KLRA, LRRP, RFA, RSA, CRP, WA
  - Pet/Res/Don't know = "Don't Know"
  - Petitioner/Respondent Name = owner name (English) fed from mutation records
  - Filing date: 01-08-2025  ->  01-08-2026
  - Captcha: PAUSED for manual user entry on every submit
"""
import asyncio
import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from playwright.async_api import async_playwright, Page, Error as PlaywrightError
from bs4 import BeautifulSoup


OWNER_NAMES_FROM_MUTATIONS: List[Dict[str, str]] = [
    # Each entry: raw_kannada (from mutation) + english for search
    {
        "raw": "ಗಾಳಿಹನುಮಯ್ಯ ಬಿನ್ ದಿವಂಗತ ಬೈಲಪ್ಪ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Gali Hanumayya",  # ಬಿನ್ ದಿವಂಗತ ಬೈಲಪ್ಪ  = s/o late Bailappa
        "aliases": ["Gali Hanumayya", "Hanumayya Gali", "Hanumayya"],
    },
    {
        "raw": "ಮುನಿಕುಮಾರ್ ಬಿನ್ ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Munikumar Gali Hanumayya",  # ಬಿನ್ ಗಾಳಿಹನುಮಯ್ಯ = s/o Gali Hanumayya
        "aliases": ["Munikumar", "Munikumar G", "Munikumara"],
    },
    {
        "raw": "ಲಕ್ಷ್ಮಣಮೂರ್ತಿ  ಬಿನ್ ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Lakshmikanthamurthy  Gali Hanumayya",
        "aliases": ["Lakshmikanthamurthy", "Lakshmikantha Murthy", "Lakshmikanthamurthy G"],
    },
    {
        "raw": "ಶ್ರೀಮತಿ.ಭಾಗ್ಯಲಕ್ಷ್ಮೀ D/o ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Bhagyalakshmi Gali Hanumayya",  # D/o = daughter of
        "aliases": ["Bhagyalakshmi", "Smt Bhagyalakshmi", "Bhagyalaxmi"],
    },
]

CASE_TYPES_IN_ORDER = ["WP", "CP.KLRA", "LRRP", "RFA", "RSA", "CRP", "WA"]

BENCH = "B"
BENCH_LABEL = "Bengaluru Bench"
FROM_DATE = "01-08-2025"
TO_DATE = "01-08-2026"
PET_RES_SELECTION = "0"
PET_RES_LABEL = "Don't Know"

FIELD_SELECTORS = {
    "bench": "#ptbenchid",
    "case_type": "#pt_types",
    "party_name": "#pt_name",
    "pet_res": "#pt_type1",
    "from_date": "#ptfrom_date",
    "to_date": "#ptto_date",
    "captcha": "#vercode",
    "submit_btn": "input[name=\"submit\"][value=\"Submit\"]",
    "result_det": "#det",
    "result_casedet": "#casedet",
    "typeval_hidden": "#typeval",
    "party_tab": "#parsearch-tab",
}


class KarnatakaHCPartyScraper:
    BASE_URL = "https://judiciary.karnataka.gov.in/casemenu.php"

    def __init__(self):
        self.log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
        self.output_dir = os.path.join(self.log_dir, "karnataka_highcourt")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _safe(self, *parts: str) -> str:
        cleaned = []
        for p in parts:
            if not p:
                continue
            s = re.sub(r'[\\/*?:"<>|]+', '_', str(p)).strip()
            s = re.sub(r'\s+', '_', s)
            if s:
                cleaned.append(s)
        return "__".join(cleaned) if cleaned else "unknown"

    async def _match_option(self, page: Page, selector: str, target: str) -> Optional[str]:
        def norm(s: str) -> str:
            return re.sub(r'[^A-Za-z0-9]+', '', s.upper())
        options = await page.query_selector_all(f"{selector} option")
        t_norm = norm(target)
        for opt in options:
            val = await opt.get_attribute("value") or ""
            txt = await opt.inner_text() or ""
            if t_norm == norm(val) or t_norm == norm(txt) or t_norm in norm(txt):
                return val
        # Fuzzy substring fallback
        for opt in options:
            txt = await opt.inner_text() or ""
            if t_norm[:4] and t_norm[:4] in norm(txt) and norm(txt):
                return await opt.get_attribute("value") or ""
        return None

    # ------------------------------------------------------------------
    # Captcha handling: mode A — wait for USER to fill captcha + click Submit IN THE BROWSER
    # ------------------------------------------------------------------
    async def _wait_for_browser_submit(self, page: Page, search_label: str, timeout_s: int = 180) -> bool:
        """
        Preferred flow (matches the user's request):
          - The open Chrome window shows the pre-filled form + captcha image.
          - YOU type the captcha digits directly into #vercode IN THE BROWSER.
          - YOU click the Submit button yourself.
          - This method just watches #det / #casedet / body for results to appear.
          - Once results appear (or "Invalid Captcha" shows), it returns True / loops / fails.

        Returns True once results are rendered.
        """
        FS = FIELD_SELECTORS
        print()
        print("=" * 70)
        print(f"  ⚠️  CAPTCHA REQUIRED — search: {search_label}")
        print("     👉  Switch to the open CHROME WINDOW.")
        print("        • Type the 6-digit captcha shown in the captcha image.")
        print("        • Click the BLUE Submit button yourself.")
        print(f"     (Waiting up to {timeout_s//60}m for results to load ...)")
        print("=" * 70)

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        # Give user time to switch to browser and type captcha
        print("  ⏳ Waiting 10 seconds for you to switch to browser and type captcha...")
        await asyncio.sleep(10)

        start_url = page.url
        deadline = asyncio.get_event_loop().time() + timeout_s
        last_notice = 0.0
        while asyncio.get_event_loop().time() < deadline:
            try:
                current_url = page.url
                if current_url != start_url and "casemenu" not in current_url:
                    print(f"  ✅ Detected navigation -> {current_url[:140]}")
                    return True
                status = await page.evaluate(
                    """() => {
                        const det = document.getElementById('det');
                        const cdet = document.getElementById('casedet');
                        const detShown = det && !det.classList.contains('display');
                        const cdetShown = cdet && !cdet.classList.contains('display');
                        const detContent = (det && det.innerHTML || '').trim();
                        const cdetContent = (cdet && cdet.innerHTML || '').trim();
                        const bodyText = document.body ? document.body.innerText || '' : '';
                        const hasTable = !!document.querySelector('table');
                        const hasResult =
                            (detShown && detContent.length > 40) ||
                            (cdetShown && cdetContent.length > 40) ||
                            /Case Details|Petitoner|Respondent|Case Number|Showing|Case No|Filing Date|STATUS|Next Date|Bench|Subject|No Record|No record|Record not found|RECORDS NOT FOUND/i.test(bodyText) ||
                            (hasTable && (detShown || cdetShown));
                        const captchaErr = /Invalid Captcha|Captcha Mismatch|captcha.*incorrect|wrong captcha/i.test(bodyText);
                        const fieldErr = /Please Enter|Required field|Select Bench|Select Case Type|Enter Party|Enter Captcha/i.test(bodyText);
                        if (hasResult) return 'OK';
                        if (captchaErr) return 'BAD_CAPTCHA';
                        if (fieldErr && !hasResult) return 'BAD_INPUT';
                        return '';
                    }"""
                )
                if status == "OK":
                    print("  ✅ Detected results rendered on page — extracting now")
                    return True
                now = asyncio.get_event_loop().time()
                if status == "BAD_CAPTCHA" and now - last_notice > 15:
                    last_notice = now
                    print("  ⚠️  Invalid captcha detected — please refresh the image (🔄 icon) and re-submit.")
                elif status == "BAD_INPUT" and now - last_notice > 20:
                    last_notice = now
                    print("  ⚠️  Field-level validation issue — please check the form in Chrome and fix before clicking Submit again.")
            except Exception:
                pass
            await asyncio.sleep(1.5)
        print(f"  ⏰ Timed out after {timeout_s}s waiting for you to click Submit.")
        return False

    # ------------------------------------------------------------------
    # Captcha handling: mode B — prompt in terminal, fill + submit programmatically
    # ------------------------------------------------------------------
    async def _handle_captcha_submit(
        self, page: Page, search_label: str, max_attempts: int = 5
    ) -> bool:
        """
        Improved captcha flow:
          1. Display captcha image location to user
          2. Prompt for captcha digits in the TERMINAL (not the browser)
          3. Fill #vercode programmatically and click Submit
          4. Detect errors and retry up to max_attempts times

        Returns True once results appear.
        """
        FS = FIELD_SELECTORS
        import sys

        for attempt in range(1, max_attempts + 1):
            print()
            print("=" * 70)
            print(f"  ⚠️  CAPTCHA REQUIRED [attempt {attempt}/{max_attempts}] — search: {search_label}")
            print("     The captcha image is visible in the open Chrome window.")
            print("     Type the 6-digit captcha below (or 'r' to refresh image, 's' to skip):")
            print("=" * 70)

            captcha_val = await asyncio.to_thread(
                lambda: input(f"  captcha [{attempt}]: ").strip()
            )

            if captcha_val.lower() in ("s", "skip", "q", "quit"):
                print("  ⏭️  Skipping this search per user request.")
                return False
            if captcha_val.lower() in ("r", "refresh", ""):
                try:
                    reload_btn = await page.query_selector("#reload-button")
                    if reload_btn:
                        await reload_btn.click()
                        print("  🔄 Captcha image refreshed.")
                        await asyncio.sleep(1.0)
                except Exception:
                    pass
                continue
            if not re.fullmatch(r"\d{6}", captcha_val):
                print(f"  ⚠️  Expected exactly 6 digits, got: {captcha_val!r}. Try again.")
                continue

            try:
                captcha_input = await page.query_selector(FS["captcha"])
                if captcha_input:
                    await captcha_input.click()
                    await captcha_input.fill("")
                    await captcha_input.type(captcha_val, delay=20)
                    print(f"   [captcha] filled {captcha_val}")
                else:
                    print("   [captcha] ⚠️  input not found")
                    continue

                submit_btn = await page.query_selector(FS["submit_btn"])
                if submit_btn:
                    try:
                        await submit_btn.click()
                        print(f"   [submit] clicked")
                    except Exception:
                        await submit_btn.evaluate("e => e.click()")
                        print(f"   [submit] JS-clicked")
                else:
                    print("   [submit] ⚠️  button not found")
            except Exception as e:
                print(f"   [captcha/submit] error: {e}")

            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            deadline = asyncio.get_event_loop().time() + 20
            err_seen = False
            while asyncio.get_event_loop().time() < deadline:
                try:
                    status = await page.evaluate(
                        """() => {
                            const det = document.getElementById('det');
                            const cdet = document.getElementById('casedet');
                            const detShown = det && !det.classList.contains('display');
                            const cdetShown = cdet && !cdet.classList.contains('display');
                            const detContent = (det && det.innerHTML || '').trim();
                            const cdetContent = (cdet && cdet.innerHTML || '').trim();
                            const bodyText = document.body ? document.body.innerText || '' : '';
                            const hasResult = detShown && detContent.length > 50 ||
                                              cdetShown && cdetContent.length > 50 ||
                                              /Case Details|Petitoner|Respondent|Case Number|Showing|Case No|Filing Date|STATUS|Next Date|Bench|Subject|No Record|No record/i.test(bodyText);
                            const captchaErr = /Invalid Captcha|Captcha Mismatch|captcha/i.test(bodyText);
                            const otherErr = /Please Enter|Required|Select/i.test(bodyText) && !hasResult;
                            if (hasResult) return 'OK';
                            if (captchaErr) return 'BAD_CAPTCHA';
                            if (otherErr) return 'BAD_INPUT';
                            return '';
                        }"""
                    )
                    if status == "OK":
                        print("  ✅ Results rendered — captcha accepted")
                        return True
                    if status == "BAD_CAPTCHA":
                        print("  ❌ Invalid captcha detected by server — try again.")
                        err_seen = True
                        break
                    if status == "BAD_INPUT":
                        print("  ⚠️  Validation issue detected (may be field-level) — continuing to wait")
                        err_seen = True
                except Exception:
                    pass
                await asyncio.sleep(0.8)
            if not err_seen:
                print("  ⏱️  Did not detect result or error within 20s — treating as OK and moving to extraction")
                return True
            try:
                reload_btn = await page.query_selector("#reload-button")
                if reload_btn:
                    await reload_btn.click()
                    await asyncio.sleep(0.8)
            except Exception:
                pass

        print(f"  ⏰ Exhausted {max_attempts} captcha attempts. Skipping this search.")
        return False

    # ------------------------------------------------------------------
    # Result extraction
    # ------------------------------------------------------------------
    async def _extract_results(self, page: Page, search_ctx: Dict[str, Any]) -> Dict[str, Any]:
        FS = FIELD_SELECTORS
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        content = await page.content()
        url_now = page.url
        soup = BeautifulSoup(content, "html.parser")

        result: Dict[str, Any] = {
            "search_context": search_ctx,
            "page_url": url_now,
            "extracted_at": datetime.now().isoformat(),
            "summary": {},
            "cases": [],
            "raw_tables": [],
            "page_text_excerpt": "",
            "result_divs": {},
            "no_record": False,
        }

        # Save HTML + screenshot - include alias in filename to avoid overwriting
        alias_key = self._safe(search_ctx['owner_name_search'])[:30]
        stem = self._safe(
            f"owner_{search_ctx['owner_key']}",
            f"alias_{alias_key}",
            f"ct_{search_ctx['case_type']}",
        )
        html_path = os.path.join(self.output_dir, f"{stem}.html")
        png_path = os.path.join(self.output_dir, f"{stem}.png")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            await page.screenshot(path=png_path, full_page=True)
        except Exception:
            pass
        result["screenshot_path"] = png_path
        result["html_path"] = html_path

        # Check content of #det and #casedet specifically
        for div_id in ["det", "casedet"]:
            div = soup.find("div", id=div_id)
            if div:
                dtxt = div.get_text(" ", strip=True)
                result["result_divs"][div_id] = {
                    "shown": "display" not in (div.get("class") or []),
                    "text_length": len(dtxt),
                    "text_excerpt": dtxt[:1500],
                    "has_tables": bool(div.find("table")),
                }
                if re.search(r"No Record|No record|NO RECORD|Records? not found|not found|No Data", dtxt, re.I):
                    result["no_record"] = True

        # Grab tables — prefer tables inside result divs
        search_scopes = []
        for div_id in ["casedet", "det"]:
            div = soup.find("div", id=div_id)
            if div:
                search_scopes.append((f"#{div_id}", div))
        search_scopes.append(("body", soup))

        seen_tables = set()
        for scope_name, scope in search_scopes:
            for ti, table in enumerate(scope.find_all("table")):
                tbl_id = id(table)
                if tbl_id in seen_tables:
                    continue
                seen_tables.add(tbl_id)
                rows = []
                for tr in table.find_all("tr"):
                    cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                    if any(c for c in cells):
                        rows.append(cells)
                if rows:
                    result["raw_tables"].append({
                        "table_index": ti,
                        "from_scope": scope_name,
                        "rows": rows,
                    })

        # Heuristic: find the cases table — usually has case number / filing date / party cols
        cases: List[Dict[str, str]] = []
        for tbl in result["raw_tables"]:
            rows = tbl["rows"]
            if len(rows) < 2:
                continue
            header = rows[0]
            h_joined = " ".join(header).lower()
            if any(k in h_joined for k in [
                "case no", "case number", "filing", "petit", "respond",
                "status", "bench", "next date", "subject", "sr no", "s.no", "sl no"
            ]) and len(rows) >= 2:
                for r in rows[1:]:
                    if not any(r):
                        continue
                    rowdict = {}
                    for ci, col in enumerate(header):
                        key = (col or f"col{ci}").strip() or f"col{ci}"
                        rowdict[key] = r[ci] if ci < len(r) else ""
                    cases.append(rowdict)
        # If no structured table detected, keep raw first table rows as case list fallback
        if not cases and len(result["raw_tables"]) >= 1:
            first_rows = result["raw_tables"][0]["rows"]
            if len(first_rows) >= 2:
                cases = [dict(enumerate(r)) for r in first_rows[1:]]

        result["cases"] = cases
        result["summary"] = {
            "tables_found": len(result["raw_tables"]),
            "case_rows_detected": len(cases),
            "result_div_detected": any(
                v.get("shown") and v.get("text_length", 0) > 20
                for v in result["result_divs"].values()
            ),
            "no_record_flag": result["no_record"],
        }
        txt = soup.get_text("\n", strip=True)
        result["page_text_excerpt"] = txt[:3000]
        return result

    # ------------------------------------------------------------------
    # Single search execution
    # ------------------------------------------------------------------
    async def _run_one_search(
        self,
        page: Page,
        owner_entry: Dict[str, str],
        case_type: str,
        attempt_alias: str,
        captcha_mode: Optional[str] = "browser",
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        label = f"owner={attempt_alias}, case_type={case_type}"

        # Always start from the party-name page (navigate fresh)
        print(f"\n▶️  {label}")
        try:
            await page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightError as e:
            print(f"   nav failed: {e}")
            return False, None
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(1000)

        # 1) Click "Party Name" tab via exact ID, ensure it's active
        FS = FIELD_SELECTORS
        party_tab = await page.query_selector(FS["party_tab"])
        if party_tab:
            try:
                await party_tab.click()
                print(f"   [tab] clicked Party Name tab")
            except Exception:
                await party_tab.evaluate("e => e.click()")
                print(f"   [tab] JS-clicked Party Name tab")
        else:
            for sel in [
                'li:has-text("Party Name")',
                'a:has-text("Party Name")',
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        print(f"   [tab] clicked Party Name via fallback {sel}")
                        break
                except Exception:
                    continue
        try:
            await page.evaluate("document.querySelector('#typeval').value = 'P'")
        except Exception:
            pass
        await page.wait_for_timeout(500)

        # 2) Select Bench = B (Bengaluru) via exact ID, then WAIT for case type AJAX
        try:
            await page.select_option(FS["bench"], value=BENCH)
            print(f"   [bench] {BENCH_LABEL} <- value={BENCH}")
        except Exception as e:
            print(f"   [bench] FAILED to set via {FS['bench']}: {e}")
        try:
            await page.wait_for_function(
                "() => document.querySelectorAll('#pt_types option').length > 2",
                timeout=15000,
            )
            print(f"   [bench] case types loaded via AJAX")
        except Exception as e:
            print(f"   [bench] warning: case types may not have loaded: {e}")
        await page.wait_for_timeout(1500)

        # 3) Select Case Type via exact ID, fuzzy match on the loaded options
        ct_val = None
        ct_norm = re.sub(r'[^A-Z0-9.]', '', case_type.upper())
        opts = await page.query_selector_all(f"{FS['case_type']} option")
        for o in opts:
            v = await o.get_attribute("value") or ""
            t = (await o.inner_text() or "").strip()
            t_norm = re.sub(r'[^A-Z0-9.]', '', t.upper())
            if v and v != "0" and (t_norm == ct_norm or ct_norm in t_norm or t_norm.startswith(ct_norm)):
                ct_val = v
                break
        if ct_val:
            try:
                await page.select_option(FS["case_type"], value=ct_val)
                print(f"   [case_type] {case_type} <- value={ct_val}")
            except Exception as e:
                print(f"   [case_type] select FAILED: {e}")
        else:
            print(f"   [case_type] ⚠️  Could not find option matching {case_type!r} in loaded {len(opts)} options")
        await page.wait_for_timeout(300)

        # 4) Pet/Res/Don't know dropdown -> value "0" = Don't Know
        try:
            await page.select_option(FS["pet_res"], value=PET_RES_SELECTION)
            print(f"   [pet/res] {PET_RES_LABEL} <- value={PET_RES_SELECTION}")
        except Exception as e:
            print(f"   [pet/res] select FAILED: {e}")

        # 5) Fill party name via exact ID
        name_el = await page.query_selector(FS["party_name"])
        if name_el:
            try:
                await name_el.click()
                await name_el.fill("")
                await name_el.type(attempt_alias, delay=20)
                print(f"   [party name] '{attempt_alias}'")
            except Exception as e:
                print(f"   [party name] fill FAILED: {e}")
        else:
            print(f"   [party name] ⚠️  Element {FS['party_name']} not found")

        # 6) Dates: From + To via exact IDs
        try:
            from_el = await page.query_selector(FS["from_date"])
            if from_el:
                await from_el.click()
                await from_el.fill("")
                await from_el.type(FROM_DATE, delay=25)
                print(f"   [from date] {FROM_DATE}")
        except Exception as e:
            print(f"   [from date] FAILED: {e}")
        try:
            to_el = await page.query_selector(FS["to_date"])
            if to_el:
                await to_el.click()
                await to_el.fill("")
                await to_el.type(TO_DATE, delay=25)
                print(f"   [to date]   {TO_DATE}")
        except Exception as e:
            print(f"   [to date] FAILED: {e}")

        # Snapshot before submit (debug)
        try:
            ss = os.path.join(self.output_dir, "PRE_SUBMIT__" + self._safe(owner_entry["search_name"][:20], case_type) + ".png")
            await page.screenshot(path=ss, full_page=True)
        except Exception:
            pass

        # 7) CAPTCHA — mode chosen by user:
        #      "browser" (default): YOU fill captcha + click Submit IN THE BROWSER
        #      "terminal"          : terminal prompt, scraper fills + clicks Submit
        search_ctx = {
            "bench_code": BENCH,
            "bench_label": BENCH_LABEL,
            "case_type": case_type,
            "pet_res_code": PET_RES_SELECTION,
            "pet_res_label": PET_RES_LABEL,
            "owner_name_search": attempt_alias,
            "owner_key": self._safe(owner_entry["search_name"])[:40],
            "owner_raw_kannada": owner_entry["raw"],
            "filing_from": FROM_DATE,
            "filing_to": TO_DATE,
        }
        captcha_mode = (captcha_mode or "browser").lower()
        if captcha_mode == "terminal":
            submitted = await self._handle_captcha_submit(page, label)
        else:
            submitted = await self._wait_for_browser_submit(page, label)
        if not submitted:
            # Save empty placeholder result
            result = {
                "search_context": search_ctx,
                "extracted_at": datetime.now().isoformat(),
                "submitted": False,
                "note": "timed out / not submitted by user",
            }
            stem = self._safe(f"owner_{search_ctx['owner_key']}", f"ct_{case_type}")
            pth = os.path.join(self.output_dir, f"{stem}.json")
            with open(pth, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return False, result

        # 8) Extract results
        try:
            extracted = await self._extract_results(page, search_ctx)
            extracted["submitted"] = True
        except Exception as e:
            extracted = {"search_context": search_ctx, "submitted": True,
                         "extraction_error": str(e)}
            import traceback
            traceback.print_exc()
        stem = self._safe(f"owner_{search_ctx['owner_key']}", f"ct_{case_type}")
        pth = os.path.join(self.output_dir, f"{stem}.json")
        with open(pth, "w", encoding="utf-8") as f:
            json.dump(extracted, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved -> {os.path.basename(pth)}   [{len(extracted.get('cases', []))} case rows]")
        return True, extracted

    # ------------------------------------------------------------------
    # Main driver: iterate owners × case types
    # ------------------------------------------------------------------
    async def run(
        self,
        *,
        headless: bool = False,
        case_types: Optional[List[str]] = None,
        owners: Optional[List[Dict[str, str]]] = None,
        use_aliases: bool = True,
        captcha_mode: Optional[str] = "browser",
        max_searches: Optional[int] = None,
    ) -> Dict[str, Any]:
        case_types = case_types or CASE_TYPES_IN_ORDER
        owners = owners or OWNER_NAMES_FROM_MUTATIONS

        summary: Dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "bench_code": BENCH,
            "bench_label": BENCH_LABEL,
            "filing_from": FROM_DATE,
            "filing_to": TO_DATE,
            "pet_res_code": PET_RES_SELECTION,
            "pet_res_label": PET_RES_LABEL,
            "case_types": case_types,
            "owners": owners,
            "searches": [],
            "total_successful": 0,
            "total_failed": 0,
            "use_aliases": use_aliases,
            "captcha_mode": captcha_mode,
            "max_searches": max_searches,
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                stop_early = False
                for owner in owners:
                    if stop_early:
                        break
                    attempts = [owner["search_name"]]
                    if use_aliases and owner.get("aliases"):
                        for alias in owner["aliases"]:
                            if alias and alias not in attempts:
                                attempts.append(alias)
                    for case_type in case_types:
                        if stop_early:
                            break
                        for alias_idx, alias in enumerate(attempts):
                            if max_searches is not None and len(summary["searches"]) >= max_searches:
                                print(f"\n🛑  Reached max_searches={max_searches} — stopping run.")
                                stop_early = True
                                break
                            search_label = f"{self._safe(owner['search_name'])[:30]} × {case_type}"
                            if alias_idx > 0:
                                search_label += f"  (alias {alias_idx}: {alias})"
                            print(f"\n{'─'*70}")
                            print(f"🔎 SEARCH {len(summary['searches'])+1}/{(max_searches or '∞')}: {search_label}")
                            print(f"{'─'*70}")
                            try:
                                ok, res = await self._run_one_search(
                                    page, owner, case_type, alias, captcha_mode=captcha_mode
                                )
                                record = {
                                    "owner": owner["search_name"],
                                    "alias_used": alias,
                                    "case_type": case_type,
                                    "success": ok,
                                    "case_rows_found": len((res or {}).get("cases", [])),
                                }
                                if res:
                                    record["result_json"] = os.path.basename(
                                        res.get("search_context", {}).get("owner_key", "") or ""
                                    ) or None
                                summary["searches"].append(record)
                                if ok:
                                    summary["total_successful"] += 1
                                else:
                                    summary["total_failed"] += 1
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                                summary["searches"].append({
                                    "owner": owner["search_name"],
                                    "alias_used": alias,
                                    "case_type": case_type,
                                    "success": False,
                                    "error": str(e),
                                })
                                summary["total_failed"] += 1
                            if max_searches is not None and len(summary["searches"]) >= max_searches:
                                print(f"\n🛑  Reached max_searches={max_searches} — stopping run.")
                                stop_early = True
                                break
                            # Short pause before next iteration so user can breathe
                            print(f"\n    ⏳ 3s pause before next search ...")
                            await asyncio.sleep(3)
            finally:
                summary["finished_at"] = datetime.now().isoformat()
                summary_path = os.path.join(self.output_dir, "ALL_SEARCHES_SUMMARY.json")
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
                print(f"\n\n{'='*70}")
                print(f"🏁 FINISHED. Summary saved -> {summary_path}")
                print(f"   Successful: {summary['total_successful']}")
                print(f"   Failed    : {summary['total_failed']}")
                print(f"{'='*70}")
                try:
                    await browser.close()
                except Exception:
                    pass
        return summary

    # ------------------------------------------------------------------
    # Result aggregation + structured Pydantic output
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_case_row(raw_row: Dict[str, Any], case_type_hint: Optional[str] = None) -> "KarnatakaHCCase":
        from .models import KarnatakaHCCase
        def get(*keys: str) -> Optional[str]:
            for k in keys:
                if k in raw_row and raw_row[k]:
                    v = str(raw_row[k]).strip()
                    if v:
                        return v
                for rk in raw_row:
                    if re.sub(r'[^a-z0-9]', '', rk.lower()) == re.sub(r'[^a-z0-9]', '', k.lower()):
                        v = str(raw_row[rk]).strip()
                        if v:
                            return v
            return None

        case_no = get("Case No", "Case Number", "case_no", "case_number", "Case Number / Year")
        ct = case_type_hint or get("Case Type", "case_type", "Type")
        if case_no and not ct:
            m = re.match(r'^([A-Za-z.]+)', case_no)
            if m:
                ct = m.group(1)
        status_next = get("Status", "Next Hearing", "Next Date", "Next Hearing Date",
                           "Stage", "Hearing Date", "Next listed on")
        next_date = get("Next Hearing Date", "Next Date", "Hearing Date", "Next listed on", "Next Hearing")
        status = get("Status", "Stage", "Current Status")
        filing = get("Filing Date", "Filed On", "Filed", "Date of Filing")
        bench = get("Bench", "Court", "Judge", "Bench Name")
        subj = get("Subject", "Category", "Subject/Act", "Act / Section")
        pet = get("Petitioner", "Petitioner(s)", "Appellant(s)", "Applicant(s)")
        res = get("Respondent", "Respondent(s)", "Defendant(s)", "Respondant(s)")
        adv_p = get("Advocate for Petitioner", "Adv Petitioner", "Counsel for Petitioner", "Pet Advocate")
        adv_r = get("Advocate for Respondent", "Adv Respondent", "Counsel for Respondent", "Res Advocate")

        return KarnatakaHCCase(
            case_number=case_no,
            case_type=ct,
            filing_date=filing,
            status=status,
            next_hearing_date=next_date or (status_next if status_next and re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', status_next or '') else None),
            bench=bench,
            subject=subj,
            petitioner=pet,
            respondent=res,
            advocate_petitioner=adv_p,
            advocate_respondent=adv_r,
            raw_row={k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v) for k, v in raw_row.items()},
        )

    def aggregate_owner_results(
        self,
        raw_summary: Dict[str, Any],
        *,
        owner_name: str,
        bench_code: str = BENCH,
        bench_label: str = BENCH_LABEL,
        filing_from: str = FROM_DATE,
        filing_to: str = TO_DATE,
    ) -> "KarnatakaHCOutput":
        from .models import KarnatakaHCOutput, KarnatakaHCCase
        searches = raw_summary.get("searches", [])
        case_types_checked: List[str] = []
        aliases_tried: List[str] = []
        per_ct: Dict[str, Dict[str, int]] = {}
        no_record: List[str] = []
        seen_case_keys: set = set()
        distinct: List[KarnatakaHCCase] = []
        errors: List[str] = []
        total_rows = 0

        for s in searches:
            ct = s.get("case_type")
            alias = s.get("alias_used")
            if ct and ct not in case_types_checked:
                case_types_checked.append(ct)
            if alias and alias not in aliases_tried:
                aliases_tried.append(alias)
            if not s.get("success"):
                err = s.get("error")
                if err:
                    errors.append(f"[{ct}/{alias}] {err[:200]}")
                continue
            per_ct.setdefault(ct or "?", {"rows": 0, "searches": 0})
            per_ct[ct or "?"]["searches"] += 1
            rows_found = s.get("case_rows_found") or 0
            per_ct[ct or "?"]["rows"] = max(per_ct[ct or "?"]["rows"], rows_found)
            total_rows += rows_found
            if rows_found == 0 and s.get("result_json"):
                maybe_json_path = os.path.join(self.output_dir, s["result_json"] + ".json")
                if os.path.exists(maybe_json_path):
                    try:
                        with open(maybe_json_path, "r", encoding="utf-8") as f:
                            jr = json.load(f)
                        if jr.get("no_record") or (jr.get("summary", {}).get("no_record_flag")):
                            if ct and ct not in no_record:
                                no_record.append(ct)
                    except Exception:
                        pass
            if rows_found == 0 and ct and ct not in no_record:
                pass

        # Read back actual case rows from the saved JSON files
        for s in searches:
            if not s.get("success") or not (s.get("case_rows_found") or 0):
                continue
            if not s.get("result_json"):
                continue
            jr_path = os.path.join(self.output_dir, s["result_json"] + ".json")
            if not os.path.exists(jr_path):
                continue
            try:
                with open(jr_path, "r", encoding="utf-8") as f:
                    jr = json.load(f)
                for raw_row in jr.get("cases", []):
                    parsed = self._parse_case_row(raw_row, case_type_hint=s.get("case_type"))
                    key = (
                        (parsed.case_number or "").strip().lower(),
                        (parsed.filing_date or "").strip(),
                        (parsed.petitioner or "").strip().lower()[:40],
                        (parsed.respondent or "").strip().lower()[:40],
                    )
                    if any(k for k in key) and key not in seen_case_keys:
                        seen_case_keys.add(key)
                        distinct.append(parsed)
            except Exception as e:
                errors.append(f"[aggregate] reading {jr_path}: {e}")

        has_litigation = total_rows > 0 or len(distinct) > 0
        return KarnatakaHCOutput(
            owner_name=owner_name,
            bench_code=bench_code,
            bench_label=bench_label,
            filing_from=filing_from,
            filing_to=filing_to,
            case_types_checked=case_types_checked,
            aliases_tried=aliases_tried,
            total_cases_found=total_rows,
            distinct_cases=distinct,
            has_active_litigation=has_litigation,
            no_record_case_types=sorted(set(no_record)),
            per_case_type_summary=per_ct,
            search_summaries=searches,
            extraction_errors=errors,
        )

    async def scrape_owner(
        self,
        owner_name: str,
        *,
        case_types: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        headless: bool = False,
        bench_code: str = BENCH,
        bench_label: str = BENCH_LABEL,
        filing_from: str = FROM_DATE,
        filing_to: str = TO_DATE,
        pet_res_code: str = PET_RES_SELECTION,
    ) -> "KarnatakaHCOutput":
        """High-level single-owner scrape that returns the aggregated Pydantic model."""
        # Temporarily override module-level constants if user passed different values
        global BENCH, BENCH_LABEL, FROM_DATE, TO_DATE, PET_RES_SELECTION
        _orig = (BENCH, BENCH_LABEL, FROM_DATE, TO_DATE, PET_RES_SELECTION)
        BENCH, BENCH_LABEL, FROM_DATE, TO_DATE, PET_RES_SELECTION = (
            bench_code, bench_label, filing_from, filing_to, pet_res_code,
        )
        try:
            owner_entry = {
                "raw": owner_name,
                "search_name": owner_name,
                "aliases": aliases or [],
            }
            raw_summary = await self.run(
                headless=headless,
                case_types=case_types or CASE_TYPES_IN_ORDER,
                owners=[owner_entry],
                use_aliases=bool(aliases),
            )
            return self.aggregate_owner_results(
                raw_summary,
                owner_name=owner_name,
                bench_code=bench_code,
                bench_label=bench_label,
                filing_from=filing_from,
                filing_to=filing_to,
            )
        finally:
            BENCH, BENCH_LABEL, FROM_DATE, TO_DATE, PET_RES_SELECTION = _orig


# ----------------------------------------------------------------------
# BaseScraper adapter — plug Karnataka HC into the property-verification pipeline
# ----------------------------------------------------------------------
from .base import BaseScraper  # noqa: E402
from utils.retry import retry  # noqa: E402


class KarnatakaHCLegalScraper(BaseScraper):
    """
    BaseScraper-compatible wrapper around KarnatakaHCPartyScraper.

    Use this from the property-verification orchestrator:
        scraper = KarnatakaHCLegalScraper(config, cache, proxy, captcha)
        result = await scraper.scrape(karnataka_hc_input)
        if result.has_active_litigation:
            flag_risk(RiskFlag.ACTIVE_LITIGATION)
    """
    def __init__(self, config, cache_service=None, proxy_service=None, captcha_service=None):
        super().__init__(config, cache_service, proxy_service, captcha_service)
        self.base_url = config.get('karnataka_hc_url',
                                   'https://judiciary.karnataka.gov.in/casemenu.php')
        self._impl = KarnatakaHCPartyScraper()
        self.cache_ttl = config.get('cache_ttl', 86400)

    def _cache_key(self, owner, case_types, bench):
        ct = ",".join(sorted(case_types or []))
        return f"karnatakahc:v1:{bench}:{owner}:{ct}"

    @retry(max_attempts=2, delay=3.0, backoff=1.5, exceptions=(Exception,))
    async def scrape(self, input_data) -> List["KarnatakaHCOutput"]:
        """Accept KarnatakaHCInput (or dict) and return a list of KarnatakaHCOutput."""
        from .models import KarnatakaHCInput, KarnatakaHCOutput
        if isinstance(input_data, dict):
            input_data = KarnatakaHCInput(**input_data)
        self.logger.info(f"Starting Karnataka HC scrape for owner: {input_data.owner_name}")
        owner = input_data.owner_name.strip()
        key = self._cache_key(owner, input_data.case_types, input_data.bench)
        if self.cache_service:
            cached = await self.cache_service.get(key)
            if cached:
                self.logger.info(f"Cache hit for {key}")
                try:
                    return [KarnatakaHCOutput(**item) for item in cached]
                except Exception:
                    pass
        # Note: this still requires manual captcha entry in the terminal.
        # In a production automation, pass a real captcha_service and extend _handle_captcha_submit.
        headless_mode = self.config.get('hc_headless', False)
        output = await self._impl.scrape_owner(
            owner_name=owner,
            case_types=list(input_data.case_types or []),
            aliases=list(input_data.aliases or []) or None,
            headless=headless_mode,
            bench_code=input_data.bench,
            bench_label={"B": "Bengaluru Bench", "D": "Dharwad Bench", "K": "Kalaburagi Bench"}.get(input_data.bench, input_data.bench),
            filing_from=input_data.filing_from,
            filing_to=input_data.filing_to,
            pet_res_code=input_data.pet_res_code,
        )
        if self.cache_service:
            await self.cache_service.set(key, [output.model_dump()], ttl=self.cache_ttl)
        return [output]

    async def scrape_and_flag(self, input_data):
        """Shorthand: runs scrape() and returns (output_list, risk_flags)."""
        from services.property_verification_service import RiskFlag
        outs = await self.scrape(input_data)
        flags: List = []
        if any(getattr(o, 'has_active_litigation', False) for o in outs):
            flags.append(RiskFlag.ACTIVE_LITIGATION)
        return outs, flags
