"""
eSwathu ekatha scraper
URL: https://eswathu.karnataka.gov.in/
"""
import asyncio
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Error as PlaywrightError,
)
from bs4 import BeautifulSoup


# Owner names from mutation records
OWNER_NAMES_FROM_MUTATIONS: List[Dict[str, str]] = [
    {
        "raw": "ಗಾಳಿಹನುಮಯ್ಯ ಬಿನ್ ದಿವಂಗತ ಬೈಲಪ್ಪ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Gali Hanumayya",
        "aliases": ["Gali Hanumayya", "Hanumayya Gali", "Hanumayya"],
    },
    {
        "raw": "ಮುನಿಕುಮಾರ್ ಬಿನ್ ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Munikumar Gali Hanumayya",
        "aliases": ["Munikumar", "Munikumar G", "Munikumara"],
    },
    {
        "raw": "ಲಕ್ಷ್ಮಣಮೂರ್ತಿ  ಬಿನ್ ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Lakshmikanthamurthy  Gali Hanumayya",
        "aliases": ["Lakshmikanthamurthy", "Lakshmikantha Murthy", "Lakshmikanthamurthy G"],
    },
    {
        "raw": "ಶ್ರೀಮತಿ.ಭಾಗ್ಯಲಕ್ಷ್ಮೀ D/o ಗಾಳಿಹನುಮಯ್ಯ .  . - ಸಂಬಂಧ :ಇತರೆ",
        "search_name": "Bhagyalakshmi Gali Hanumayya",
        "aliases": ["Bhagyalakshmi", "Smt Bhagyalakshmi", "Bhagyalaxmi"],
    },
]


class EswathuEkathaScraper:
    EXISTING_KHATA_URL = "https://eswathu.karnataka.gov.in/eCitizen/Citizen/frm_CitizenPropertyList.aspx"

    SEL_LANG_EN = "#lang-en, button:has-text('English'), a:has-text('English')"
    SEL_DISTRICT = "#ContentPlaceHolder1_ddlDistrict"
    SEL_TALUK = "#ContentPlaceHolder1_ddlBlocks"
    SEL_PANCHAYATH = "#ContentPlaceHolder1_ddlGps"
    SEL_VILLAGE = "#ContentPlaceHolder1_ddlVillage"
    SEL_SEARCH_TYPE = "#ContentPlaceHolder1_ddlSearchType"
    SEL_SEARCH_INPUT = "#ContentPlaceHolder1_txtSearchBy"
    SEL_SEARCH_BTN = "#ContentPlaceHolder1_btnSearch"
    SEL_DRAFT_LINK = "#ContentPlaceHolder1_gvPropertyList a[id*='_lnkDraft_']"
    SEL_PREVPRINT_LINK = "#ContentPlaceHolder1_gvPropertyList a[id*='_lnkPrevPrint_']"
    SEL_NEWPRINT_LINK = "#ContentPlaceHolder1_gvPropertyList a[id*='_lnkNewPrint_']"
    SEL_RESULT_ROWS = "#ContentPlaceHolder1_gvPropertyList tr"

    async def _ensure_selector(self, page: Page, selector: str, retries: int = 6, delay_ms: int = 1000):
        """Wait for selector to be present+visible, retrying."""
        for attempt in range(retries):
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    return el
            except Exception:
                pass
            await page.wait_for_timeout(delay_ms)
        return None

    def __init__(self):
        self.log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
        self.output_dir = os.path.join(self.log_dir, "eswathu_ekatha")
        self.downloads_dir = os.path.join(self.output_dir, "ekatha_downloads")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)

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

    async def _wait_postback(self, page: Page, timeout_ms: int = 30000):
        """Wait for ASP.NET __doPostBack to finish."""
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            await page.wait_for_timeout(1800)
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass
            await page.wait_for_timeout(600)
        except Exception:
            await page.wait_for_timeout(3500)

    def _kannada_tokens(self, text: str) -> List[str]:
        """Extract Kannada script tokens (or any non-ASCII meaningful tokens)."""
        tokens = []
        if not text:
            return tokens
        parts = re.sub(r'[-.:,;!?()\[\]{}]', ' ', text).split()
        for p in parts:
            p = p.strip()
            if len(p) >= 2 and re.search(r'[\u0C80-\u0CFF]', p):
                tokens.append(p)
        return tokens

    def _make_draft_stem(self, search_ctx: Dict[str, Any], row_index: int, kind: str) -> str:
        base = self._safe(
            f"owner_{search_ctx.get('owner_key','unknown')}",
            search_ctx.get('owner_name_search', '')[:20],
            f"row{row_index}",
            kind,
        )
        return base

    def _parse_ekatha_page_text(self, html: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "raw_text": "",
            "fields": {},
            "tables": [],
        }
        if not html:
            return out
        soup = BeautifulSoup(html, "html.parser")
        out["raw_text"] = soup.get_text(" ", strip=True)[:10000]

        for tbl in soup.find_all("table"):
            rows = []
            for tr in tbl.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if any(c for c in cells):
                    rows.append(cells)
            if rows:
                out["tables"].append(rows)

        seen: set = set()
        for tbl in soup.find_all("table"):
            for tr in tbl.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) == 2:
                    k = cells[0].get_text(" ", strip=True)
                    v = cells[1].get_text(" ", strip=True)
                    if k and v and k not in seen and len(k) < 120:
                        out["fields"][k] = v
                        seen.add(k)

        for lbl in soup.select("span[id], label[id], div[id], td[id]"):
            txt = lbl.get_text(" ", strip=True)
            mid = lbl.get("id") or ""
            if (
                txt
                and 1 < len(txt) < 300
                and re.search(r"(owner|khata|property|asset|village|panchayat|survey|ಹೆಸರು|ಖಾತೆ|ಎಸೆಟ್|ಗ್ರಾಮ|ವತ್ತಾರ)", mid + txt, flags=re.I)
            ):
                key = f"{txt[:60]}"
                if key not in out["fields"]:
                    sib = lbl.find_next(["span", "td", "div", "input"])
                    sib_val = sib.get_text(" ", strip=True) if sib and hasattr(sib, "get_text") else ""
                    if sib_val and sib_val != txt:
                        out["fields"][key] = sib_val[:500]
                    elif lbl.get("value"):
                        out["fields"][key] = (lbl.get("value") or "")[:500]
        return out

    async def _handle_draft_click(
        self,
        context: BrowserContext,
        page: Page,
        link,
        link_kind: str,
        search_ctx: Dict[str, Any],
        row_index: int,
    ) -> Dict[str, Any]:
        artifact: Dict[str, Any] = {
            "kind": link_kind,
            "row_index": row_index,
            "clicked_at": datetime.now().isoformat(),
            "ok": False,
            "error": None,
            "artifact_path": None,
            "artifact_type": None,
            "detail_json_path": None,
            "landing_url": None,
            "detail": {},
        }
        search_start_url = page.url
        base_stem = self._make_draft_stem(search_ctx, row_index, link_kind)
        detail: Dict[str, Any] = {}

        try:
            page_opened_event: Optional[Page] = None
            dl_event = None
            nav_done = False

            async def _on_popup(pg: Page):
                nonlocal page_opened_event
                page_opened_event = pg

            async def _on_dl(dl):
                nonlocal dl_event
                dl_event = dl

            context.on("page", _on_popup)
            context.on("download", _on_dl)

            try:
                await link.click()
            finally:
                try:
                    context.remove_listener("page", _on_popup)
                except Exception:
                    pass
                try:
                    context.remove_listener("download", _on_dl)
                except Exception:
                    pass

            dl_path: Optional[str] = None
            if dl_event is not None:
                try:
                    save_name = self._safe(base_stem, Path(dl_event.suggested_filename or "ekatha").stem) + Path(dl_event.suggested_filename or ".pdf").suffix
                    save_path = os.path.join(self.downloads_dir, save_name)
                    await dl_event.save_as(save_path)
                    dl_path = save_path
                    artifact["ok"] = True
                    artifact["artifact_path"] = save_path
                    artifact["artifact_type"] = Path(save_path).suffix.lstrip(".").lower() or "download"
                except Exception as e:
                    artifact["error"] = f"download_failed: {e}"
                    try:
                        await dl_event.failure()
                    except Exception:
                        pass

            target_page = page_opened_event or page
            if target_page is not None and target_page != page:
                try:
                    await target_page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
                try:
                    await target_page.wait_for_timeout(2500)
                except Exception:
                    pass

            if dl_path is None and target_page is not None:
                try:
                    final_url = target_page.url or ""
                    artifact["landing_url"] = final_url
                    html = await target_page.content()
                    if not nav_done:
                        html_path = os.path.join(self.downloads_dir, f"{base_stem}.html")
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html)
                        png_path = os.path.join(self.downloads_dir, f"{base_stem}.png")
                        try:
                            await target_page.screenshot(path=png_path, full_page=True)
                        except Exception:
                            png_path = None
                        artifact["ok"] = True
                        artifact["artifact_path"] = html_path
                        artifact["artifact_type"] = "html"
                        artifact["screenshot_path"] = png_path
                        detail = self._parse_ekatha_page_text(html)
                        nav_done = True
                except Exception as e:
                    if not artifact["ok"]:
                        artifact["error"] = f"capture_failed: {e}"

            if target_page != page and target_page is not None:
                try:
                    await target_page.close()
                except Exception:
                    pass

            if page.url != search_start_url:
                try:
                    html = await page.content()
                    html_path = os.path.join(self.downloads_dir, f"{base_stem}__samepage.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    png_path = os.path.join(self.downloads_dir, f"{base_stem}__samepage.png")
                    try:
                        await page.screenshot(path=png_path, full_page=True)
                    except Exception:
                        png_path = None
                    if not artifact["ok"]:
                        artifact["ok"] = True
                        artifact["artifact_path"] = html_path
                        artifact["artifact_type"] = "html"
                        artifact["screenshot_path"] = png_path
                    same_detail = self._parse_ekatha_page_text(html)
                    if not detail and same_detail.get("fields"):
                        detail = same_detail
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=25000)
                    except Exception:
                        try:
                            await page.goto(search_start_url, wait_until="domcontentloaded", timeout=60000)
                        except Exception:
                            pass
                    await self._wait_postback(page, timeout_ms=30000)
                except Exception as e:
                    if not artifact["ok"] and not artifact["error"]:
                        artifact["error"] = f"samepage_capture_failed: {e}"
        except Exception as e:
            if not artifact["error"]:
                artifact["error"] = str(e)

        artifact["detail"] = detail
        if detail:
            detail_json_path = os.path.join(self.downloads_dir, f"{base_stem}.detail.json")
            try:
                with open(detail_json_path, "w", encoding="utf-8") as f:
                    json.dump(detail, f, indent=2, ensure_ascii=False)
                artifact["detail_json_path"] = detail_json_path
            except Exception:
                pass
        return artifact

    async def _download_available_ekathas(
        self,
        context: BrowserContext,
        page: Page,
        search_ctx: Dict[str, Any],
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        artifacts: List[Dict[str, Any]] = []

        all_links: List[Any] = []
        for sel, kind in (
            (self.SEL_DRAFT_LINK, "DRAFT EKHATA"),
            (self.SEL_PREVPRINT_LINK, "PREVIOUS PRINT"),
            (self.SEL_NEWPRINT_LINK, "NEW PRINT"),
        ):
            try:
                els = await page.query_selector_all(sel)
            except Exception:
                els = []
            for el in els:
                all_links.append((kind, el))

        if not all_links:
            return artifacts

        rows = []
        try:
            rows = await page.query_selector_all(self.SEL_RESULT_ROWS)
        except Exception:
            rows = []

        async def _row_index_from_link_id_async(link) -> int:
            try:
                attr = link.get_attribute("id")
                if hasattr(attr, "__await__"):
                    attr = await attr
                mid = (attr or "")
                m = re.search(r"_(\d+)$", mid)
                if m:
                    return int(m.group(1))
            except Exception:
                pass
            return -1

        def _row_meta(row_idx: int) -> Dict[str, str]:
            meta: Dict[str, str] = {}
            if row_idx >= 0 and row_idx < len(records):
                rec = records[row_idx]
                meta = {
                    "asset_number": str(rec.get("Asset Number :") or rec.get("Asset Number") or ""),
                    "property_id": str(rec.get("PropertyID :") or rec.get("PropertyID") or ""),
                    "owner_name": str(rec.get("Owner Name :") or rec.get("Owner Name") or ""),
                }
            return meta

        for kind, link in all_links:
            row_idx = await _row_index_from_link_id_async(link)
            try:
                visible = await link.is_visible() if link else False
            except Exception:
                visible = False
            if not visible:
                continue
            artifact = await self._handle_draft_click(context, page, link, kind, search_ctx, row_idx)
            artifact["row_meta"] = _row_meta(row_idx)
            artifacts.append(artifact)

            pause_ms = 3500
            try:
                await page.wait_for_timeout(pause_ms)
            except Exception:
                pass
        return artifacts

    async def _extract_ekatha_details(self, page: Page, search_ctx: Dict[str, Any], search_terms_override: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract ekatha details from the page"""
        await page.wait_for_timeout(2500)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        result: Dict[str, Any] = {
            "search_context": search_ctx,
            "page_url": page.url,
            "extracted_at": datetime.now().isoformat(),
            "owner_found": False,
            "details": {},
            "raw_text": soup.get_text(" ", strip=True)[:10000],
            "record_count": 0,
            "records": [],
        }

        stem = self._safe(f"owner_{search_ctx['owner_key']}__" + self._safe(search_ctx['owner_name_search'][:20]))
        html_path = os.path.join(self.output_dir, f"{stem}.html")
        png_path = os.path.join(self.output_dir, f"{stem}.png")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            await page.screenshot(path=png_path, full_page=True)
        except Exception:
            pass

        result["html_path"] = html_path
        result["screenshot_path"] = png_path

        body_text = result["raw_text"]
        body_lower = body_text.lower()

        search_terms: List[str] = []
        if search_terms_override:
            search_terms.extend(search_terms_override)
        search_terms.append(search_ctx["owner_name_search"])
        for part in search_ctx["owner_name_search"].split():
            if len(part) >= 4:
                search_terms.append(part)
        kn_tokens = self._kannada_tokens(search_ctx.get("owner_raw_kannada", ""))
        search_terms.extend(kn_tokens)
        # Also add first big Kannada token as "the key name"
        if kn_tokens:
            search_ctx.setdefault("kannada_primary_token", kn_tokens[0])

        seen = set()
        unique_terms = []
        for t in search_terms:
            tt = t.strip()
            if not tt or len(tt) < 2:
                continue
            key = tt.lower() if '\u0C80' > tt or tt > '\u0CFF' else tt
            if key in seen:
                continue
            seen.add(key)
            unique_terms.append(tt)

        exact_hits = []
        for term in unique_terms:
            if re.search(r'[\u0C80-\u0CFF]', term):
                if term in body_text:
                    exact_hits.append(term)
            else:
                if term.lower() in body_lower:
                    exact_hits.append(term)

        result["matched_terms"] = exact_hits
        if exact_hits:
            result["owner_found"] = True

        if ("no data records to display" not in body_lower) and ("ಯಾವುದೇ ಡೇಟಾ ದಾಖಲೆಗಳು ಪ್ರದರ್ಶಿಸಲಾಗುವುದಿಲ್ಲ" not in body_text):
            tables = soup.find_all('table')
            main_table = None
            for t in tables:
                t_txt = t.get_text(" ", strip=True)
                if ("Owner Name" in t_txt) or ("ಓಡಂಬರ ಹೆಸರು" in t_txt) or ("PropertyID" in t_txt) or ("Asset Number" in t_txt):
                    main_table = t
                    break
            if main_table is None and tables:
                largest = max(tables, key=lambda t: len(t.find_all('tr')))
                if len(largest.find_all('tr')) >= 2:
                    main_table = largest

            if main_table is not None:
                rows = main_table.find_all('tr')
                headers = []
                for th in rows[0].find_all(['th', 'td']) if rows else []:
                    headers.append(th.get_text(strip=True))
                real_records_started = False
                for i, row in enumerate(rows[1:], start=1):
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        rec = {}
                        for j, cell in enumerate(cells):
                            key = headers[j] if j < len(headers) else f"col{j}"
                            rec[key] = cell.get_text(strip=True)
                        non_empty = sum(1 for v in rec.values() if v)
                        if non_empty >= 3:
                            real_records_started = True
                            result["records"].append(rec)
                        elif real_records_started:
                            result["records"].append(rec)
                result["record_count"] = len(result["records"])

            all_owner_names = []
            for rec in result["records"]:
                for k, v in rec.items():
                    if ("Owner" in k) or ("ಹೆಸರು" in k) or (k.lower() == "name"):
                        if v:
                            all_owner_names.append(v)
            result["all_owner_names_in_results"] = all_owner_names

            if not result["owner_found"] and all_owner_names:
                kn_primary = kn_tokens[0] if kn_tokens else None
                en_tokens = [p.lower() for p in search_ctx["owner_name_search"].split() if len(p) >= 4]
                for oname in all_owner_names:
                    oname_l = oname.lower()
                    hit = False
                    if kn_primary and kn_primary in oname:
                        hit = True
                        exact_hits.append(f"kn:{kn_primary}->{oname}")
                    for et in en_tokens:
                        if et and et in oname_l:
                            hit = True
                            exact_hits.append(f"en:{et}->{oname}")
                    if hit:
                        result["owner_found"] = True
                        break
                result["matched_terms"] = list(dict.fromkeys(exact_hits))

            for t in tables:
                rows = t.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value and len(key) < 80 and key not in result["details"] and len(result["details"]) < 30:
                            result["details"][key] = value

        return result

    async def _run_one_search(
        self,
        context: BrowserContext,
        page: Page,
        owner_entry: Dict[str, str],
        attempt_alias: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Run one search for an owner name"""
        label = f"owner={attempt_alias}"

        print(f"\n▶️  {label}")

        search_ctx = {
            "owner_name_search": attempt_alias,
            "owner_key": self._safe(owner_entry["search_name"])[:40],
            "owner_raw_kannada": owner_entry["raw"],
            "district": "BENGALURU",
            "taluk": "BENGALURU NORTH",
            "panchayath": "DAASANAPURA",
            "village": "DASANAPURA",
        }

        try:
            await page.goto(self.EXISTING_KHATA_URL, wait_until="domcontentloaded", timeout=60000)
            await self._wait_postback(page)
        except PlaywrightError as e:
            print(f"   nav failed: {e}")
            return False, None

        # English language switch is removed per user request: "no need english"
        # print("   Page loaded. Switching to English...")
        # try:
        #     en_btn = await self._ensure_selector(page, self.SEL_LANG_EN, retries=4, delay_ms=1200)
        #     if en_btn:
        #         await en_btn.click()
        #         await self._wait_postback(page)
        #         print("   [language] English mode enabled")
        # except Exception:
        #     pass

        print("   Filling form dropdowns...")

        async def _select_robust(selector: str, label_en: str, field_name: str):
            try:
                el = await self._ensure_selector(page, selector)
                if el:
                    found = False
                    # Try exact label first (works if UI is English or label is English)
                    try:
                        await el.select_option(label=label_en)
                        print(f"   [{field_name}] selected {label_en}")
                        found = True
                    except Exception:
                        # Try to find option that contains the English text (transliteration check)
                        # or just select the second option if only one real option exists
                        options = await el.evaluate('el => Array.from(el.options).map(o => ({text: o.text, value: o.value}))')
                        for opt in options:
                            if opt['text'] and label_en.lower() in opt['text'].lower():
                                await el.select_option(value=opt['value'])
                                print(f"   [{field_name}] selected by partial match: {opt['text']}")
                                found = True
                                break
                        
                        if not found and len(options) > 1:
                            # Fallback: select the first non-default option if we can't match
                            await el.select_option(index=1)
                            print(f"   [{field_name}] fallback to first option: {options[1]['text']}")
                            found = True
                    
                    if found:
                        await self._wait_postback(page)
                else:
                    print(f"   [{field_name}] ⚠️ NOT FOUND")
            except Exception as e:
                print(f"   [{field_name}] error: {e}")

        await _select_robust(self.SEL_DISTRICT, search_ctx["district"], "district")
        await _select_robust(self.SEL_TALUK, search_ctx["taluk"], "taluk")
        await _select_robust(self.SEL_PANCHAYATH, search_ctx["panchayath"], "panchayath")
        await _select_robust(self.SEL_VILLAGE, search_ctx["village"], "village")

        try:
            el = await self._ensure_selector(page, self.SEL_SEARCH_TYPE)
            if el:
                # Try English and Kannada for "Owner's Name"
                try:
                    await el.select_option(label="Owner's Name")
                except Exception:
                    await el.select_option(index=2) # Usually the 2nd or 3rd option
                print(f"   [search-type] selected Owner's Name")
                await self._wait_postback(page)
            else:
                print("   [search-type] ⚠️ NOT FOUND")
        except Exception as e:
            print(f"   [search-type] error: {e}")

        filled_text: Optional[str] = None
        search_terms_extra: List[str] = []
        try:
            el = await self._ensure_selector(page, self.SEL_SEARCH_INPUT, retries=6, delay_ms=1000)
            if el:
                await el.click()
                await el.fill("")
                await el.type(attempt_alias, delay=35)
                filled_text = attempt_alias
                search_terms_extra.append(attempt_alias)
                print(f"   [owner-name] filled '{attempt_alias}'")
            else:
                print("   [owner-name] ⚠️ NOT FOUND after retries, trying Kannada fallback search")
        except Exception as e:
            print(f"   [owner-name] error: {e}")

        if filled_text is None:
            try:
                kn_tokens = self._kannada_tokens(owner_entry["raw"])
                if kn_tokens:
                    fallback = kn_tokens[0]
                    el = await self._ensure_selector(page, self.SEL_SEARCH_INPUT, retries=4, delay_ms=1000)
                    if el:
                        await el.click()
                        await el.fill("")
                        await el.type(fallback, delay=40)
                        filled_text = fallback
                        search_ctx["owner_name_search"] = fallback
                        search_terms_extra.extend(kn_tokens)
                        print(f"   [owner-name] filled Kannada fallback: '{fallback}'")
            except Exception as ke:
                print(f"   [owner-name] Kannada fallback failed: {ke}")

        try:
            ss = os.path.join(self.output_dir, "PRE_SUBMIT__" + self._safe(owner_entry["search_name"][:20]) + "__" + self._safe(str(filled_text or attempt_alias)[:15]) + ".png")
            await page.screenshot(path=ss, full_page=True)
            print(f"   [debug] Pre-submit screenshot: {os.path.basename(ss)}")
        except Exception:
            pass

        print("   Submitting search...")
        try:
            btn = await self._ensure_selector(page, self.SEL_SEARCH_BTN, retries=5, delay_ms=800)
            if btn:
                await btn.click()
                await self._wait_postback(page, timeout_ms=50000)
                print("   Submitted. Waiting for results...")
            else:
                print("   [search-btn] ⚠️ NOT FOUND, pressing Enter on input instead")
                inp = await self._ensure_selector(page, self.SEL_SEARCH_INPUT, retries=3, delay_ms=800)
                if inp:
                    await inp.press("Enter")
                    await self._wait_postback(page, timeout_ms=50000)
        except Exception as e:
            print(f"   [submit] error: {e}")

        try:
            extracted = await self._extract_ekatha_details(page, search_ctx, search_terms_override=search_terms_extra)
            extracted["submitted"] = True
            extracted["search_text_used"] = filled_text or attempt_alias

            records = extracted.get("records") or []
            has_draft_links = any(
                str(rec.get(k, "")).strip().upper() in {"DRAFT EKHATA", "PREVIOUS PRINT", "NEW PRINT"}
                for rec in records
                for k in rec.keys()
            )
            if not has_draft_links and records:
                try:
                    preview_any = await page.query_selector(
                        f"{self.SEL_DRAFT_LINK}, {self.SEL_PREVPRINT_LINK}, {self.SEL_NEWPRINT_LINK}"
                    )
                    has_draft_links = preview_any is not None
                except Exception:
                    has_draft_links = False

            artifacts: List[Dict[str, Any]] = []
            if records and has_draft_links:
                print(f"   [ekatha] attempting to download {len(records)} row(s) draft/print ...")
                try:
                    artifacts = await self._download_available_ekathas(
                        context, page, search_ctx, records
                    )
                    ok_count = sum(1 for a in artifacts if a.get("ok"))
                    fail_count = len(artifacts) - ok_count
                    print(f"   [ekatha] downloads ok={ok_count} failed={fail_count}")
                except Exception as ee:
                    import traceback
                    traceback.print_exc()
                    artifacts = [{"kind": "error", "ok": False, "error": str(ee)}]
            extracted["ekatha_artifacts"] = artifacts
            extracted["ekatha_downloads_dir"] = self.downloads_dir
        except Exception as e:
            extracted = {
                "search_context": search_ctx,
                "submitted": True,
                "extraction_error": str(e),
                "search_text_used": filled_text or attempt_alias,
            }
            import traceback
            traceback.print_exc()

        stem = self._safe(f"owner_{search_ctx['owner_key']}__" + self._safe(str(filled_text or attempt_alias)[:20]))
        pth = os.path.join(self.output_dir, f"{stem}.json")
        with open(pth, "w", encoding="utf-8") as f:
            json.dump(extracted, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved -> {os.path.basename(pth)}")
        found_info = f"✅ FOUND (matches: {extracted.get('matched_terms', [])})" if extracted.get("owner_found") else "❌ not found"
        print(f"   🔎 Owner: {found_info} | Records: {extracted.get('record_count', 0)}")

        return True, extracted

    async def run(
        self,
        *,
        headless: bool = False,
        owners: Optional[List[Dict[str, str]]] = None,
        use_aliases: bool = True,
        max_searches: Optional[int] = None,
    ) -> Dict[str, Any]:
        owners = owners or OWNER_NAMES_FROM_MUTATIONS

        summary: Dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "owners": owners,
            "searches": [],
            "total_successful": 0,
            "total_failed": 0,
            "total_found": 0,
            "use_aliases": use_aliases,
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
                    # ONLY use Kannada tokens for search attempts
                    attempts: List[str] = []
                    kn_tokens = self._kannada_tokens(owner.get("raw", ""))
                    if kn_tokens:
                        # Primary name (first token)
                        attempts.append(kn_tokens[0])
                        # Combined tokens (first 3)
                        if len(kn_tokens) >= 2:
                            joined = " ".join(kn_tokens[:3])
                            if joined not in attempts:
                                attempts.append(joined)
                    
                    # English search names and aliases are removed per user request: "searching in kannada is enough no need english"

                    for alias in attempts:
                        if max_searches is not None and len(summary["searches"]) >= max_searches:
                            print(f"\n🛑  Reached max_searches={max_searches} — stopping run.")
                            stop_early = True
                            break

                        search_label = f"{self._safe(owner['search_name'])[:30]}"
                        print(f"\n{'─'*70}")
                        print(f"🔎 SEARCH {len(summary['searches'])+1}/{(max_searches or '∞')}: {search_label}  (alias: {alias})")
                        print(f"{'─'*70}")

                        try:
                            ok, res = await self._run_one_search(context, page, owner, alias)
                            record = {
                                "owner": owner["search_name"],
                                "alias_used": alias,
                                "success": ok,
                                "owner_found": (res or {}).get("owner_found", False),
                                "record_count": (res or {}).get("record_count", 0),
                                "matched_terms": (res or {}).get("matched_terms", []),
                                "ekatha_artifacts_ok": sum(
                                    1 for a in ((res or {}).get("ekatha_artifacts") or []) if a.get("ok")
                                ),
                                "ekatha_artifacts_total": len((res or {}).get("ekatha_artifacts") or []),
                            }
                            summary["searches"].append(record)
                            if ok:
                                summary["total_successful"] += 1
                            else:
                                summary["total_failed"] += 1
                            if record["owner_found"]:
                                summary["total_found"] += 1
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            summary["searches"].append({
                                "owner": owner["search_name"],
                                "alias_used": alias,
                                "success": False,
                                "error": str(e),
                                "owner_found": False,
                                "record_count": 0,
                            })
                            summary["total_failed"] += 1

                        if max_searches is not None and len(summary["searches"]) >= max_searches:
                            print(f"\n🛑  Reached max_searches={max_searches} — stopping run.")
                            stop_early = True
                            break

                        print(f"\n    ⏳ 3s pause before next search ...")
                        await asyncio.sleep(3)
            finally:
                summary["finished_at"] = datetime.now().isoformat()
                summary_path = os.path.join(self.output_dir, "ALL_SEARCHES_SUMMARY.json")
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
                print(f"\n{'='*70}")
                print(f"🏁 FINISHED. Summary saved -> {summary_path}")
                print(f"   Successful searches : {summary['total_successful']}")
                print(f"   Failed searches     : {summary['total_failed']}")
                print(f"   Owner names FOUND   : {summary['total_found']}")
                for s in summary["searches"]:
                    found_mark = "✅ FOUND" if s.get("owner_found") else "❌ not found"
                    extra = f"  [matches: {', '.join(s.get('matched_terms', [])[:3])}]" if s.get("matched_terms") else ""
                    ek_md = ""
                    if s.get("ekatha_artifacts_total"):
                        ek_md = f"  [ekatha: {s.get('ekatha_artifacts_ok', 0)}/{s.get('ekatha_artifacts_total', 0)} ok]"
                    print(f"     • {s['owner']} ({s['alias_used']}): {found_mark} ({s.get('record_count',0)} recs){extra}{ek_md}")
                print(f"{'='*70}")

                await browser.close()

        return summary
