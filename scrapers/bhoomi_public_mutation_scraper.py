import asyncio
import os
import json
import re
from typing import Dict, Optional, List, Any
from playwright.async_api import async_playwright, Error as PlaywrightError, Page
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin


class ScraperException(Exception):
    pass


def _merge_no_dupes(*dicts: Dict) -> Dict:
    merged: Dict[str, Any] = {}
    for d in dicts:
        if not d:
            continue
        for k, v in d.items():
            if v is None or v == "" or v == [] or v == {}:
                continue
            nk = k.strip().rstrip(":").strip()
            if nk in merged and merged[nk] == v:
                continue
            if nk not in merged:
                merged[nk] = v
            else:
                if isinstance(v, list) and isinstance(merged[nk], list):
                    for item in v:
                        if item not in merged[nk]:
                            merged[nk].append(item)
                elif isinstance(v, dict) and isinstance(merged[nk], dict):
                    merged[nk] = _merge_no_dupes(merged[nk], v)
                elif not merged[nk]:
                    merged[nk] = v
    return merged


class BhoomiPublicMutationScraper:
    COURT_ORDER_KEYWORDS = ("ಕೋರ್ಟ್ ಆದೇಶ", "court order", "court_order", "courts order")

    def __init__(self):
        self.mr_url = "https://landrecords.karnataka.gov.in/Service11/MR_MutationExtract.aspx"
        self.log_dir = "/Users/smrithis/Desktop/landrecords/logs/debug"
        self.mutations_dir = os.path.join(self.log_dir, "mutations")
        self.court_orders_dir = os.path.join(self.log_dir, "court_orders")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.mutations_dir, exist_ok=True)
        os.makedirs(self.court_orders_dir, exist_ok=True)

    def _is_court_order(self, record_or_fields: Dict) -> bool:
        fields = record_or_fields.get("fields") if isinstance(record_or_fields.get("fields"), dict) else record_or_fields
        candidates = []
        for k in ("mutation_type", "Mutation Type", "ಬದಲಾವಣೆ ರೀತಿ"):
            v = fields.get(k)
            if isinstance(v, str):
                candidates.append(v)
        row = record_or_fields.get("from_table_row") or {}
        for k in ("mutation_type",):
            v = row.get(k)
            if isinstance(v, str):
                candidates.append(v)
        joined = " ".join(candidates).lower()
        return any(kw.lower() in joined for kw in self.COURT_ORDER_KEYWORDS)

    async def _match_dropdown_option(self, page, selector: str, target_text: str) -> Optional[str]:
        def normalize(s):
            s = s.upper().strip()
            s = s.replace(' (', '(').replace('( ', '(')
            s = s.replace(' )', ')').replace(') ', ')')
            s = re.sub(r'\s+', ' ', s)
            return s

        options = await page.query_selector_all(f'{selector} option')
        target_normalized = normalize(target_text)

        for opt in options:
            val = await opt.get_attribute('value')
            text = await opt.inner_text()
            text_normalized = normalize(text)
            if (target_normalized in text_normalized or text_normalized in target_normalized) and val:
                print(f"Matched {selector}: {val} - {text.strip()}")
                return val

        print(f"No fuzzy match found for {selector}: target='{target_text}'")
        return None

    async def _wait_for_dropdown_options(self, page, selector: str, timeout: int = 30000) -> bool:
        try:
            await page.wait_for_function(
                f"() => document.querySelector('{selector}').options.length > 1",
                timeout=timeout
            )
            return True
        except PlaywrightError:
            return False

    async def _fill_form_and_fetch(self, page: Page, district: str, taluk: str, hobli: str, village: str, survey_no: str):
        district_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpdist', district)
        if not district_value:
            raise ScraperException(f"District not found: {district}")
        await page.select_option('#ctl00_MainContent_drpdist', value=district_value)
        await page.wait_for_load_state("networkidle")

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drptaluk'):
            raise ScraperException("Taluk dropdown failed to load")
        taluk_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drptaluk', taluk)
        if not taluk_value:
            raise ScraperException(f"Taluk not found: {taluk}")
        await page.select_option('#ctl00_MainContent_drptaluk', value=taluk_value)
        await page.wait_for_load_state("networkidle")

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drphobli'):
            raise ScraperException("Hobli dropdown failed to load")
        hobli_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drphobli', hobli)
        if not hobli_value:
            raise ScraperException(f"Hobli not found: {hobli}")
        await page.select_option('#ctl00_MainContent_drphobli', value=hobli_value)
        await page.wait_for_load_state("networkidle")

        if not await self._wait_for_dropdown_options(page, '#ctl00_MainContent_drpvillage'):
            raise ScraperException("Village dropdown failed to load")
        village_value = await self._match_dropdown_option(page, '#ctl00_MainContent_drpvillage', village)
        if not village_value:
            raise ScraperException(f"Village not found: {village}")
        await page.select_option('#ctl00_MainContent_drpvillage', value=village_value)
        await page.wait_for_load_state("networkidle")

        await page.fill('#ctl00_MainContent_txtSurvey', survey_no)
        await page.wait_for_timeout(1000)

        print("Clicking Fetch Details button...")
        try:
            await page.click('#ctl00_MainContent_btnFetch', timeout=10000)
        except PlaywrightError:
            print("Normal click failed, trying JavaScript click...")
            await page.evaluate("document.getElementById('ctl00_MainContent_btnFetch').click()")

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        print("Fetch Details completed")

    async def _extract_mutation_table(self, page: Page) -> List[Dict]:
        page_content = await page.content()
        soup = BeautifulSoup(page_content, 'html.parser')
        tables = soup.find_all('table')
        mutation_rows = []

        print(f"Found {len(tables)} tables on page")
        
        for table_idx, table in enumerate(tables):
            rows = table.find_all('tr')
            print(f"Table {table_idx}: {len(rows)} rows")
            
            # Look for rows with "Select" text (indicates mutation rows)
            for row_idx, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                row_text = ' | '.join([c.get_text(strip=True) for c in cells])
                
                # Skip header rows and rows without "Select"
                if row_idx == 0 or 'Select' not in row_text or len(row_text) < 10:
                    continue
                
                # Parse the row data
                parts = [c.get_text(strip=True) for c in cells]
                
                mutation_row = {
                    "table_row_index": row_idx,
                    "table_index": table_idx,
                    "survey_no": None,
                    "transaction_year": None,
                    "transaction_no": None,
                    "mr_number": None,
                    "mutation_type": None,
                    "acquisition_type": None,
                    "approved_date": None,
                    "raw_data": parts
                }
                
                # Try to extract structured data from the parts
                # Expected format: Select | Survey/*/Hissa | Year | MR_No | Trans_No | Mutation_Type | Acquisition_Type | Date
                if len(parts) >= 3:
                    mutation_row["survey_no"] = parts[1] if len(parts) > 1 else None
                    mutation_row["transaction_year"] = parts[2] if len(parts) > 2 else None
                    mutation_row["mr_number"] = parts[3] if len(parts) > 3 else None
                    mutation_row["transaction_no"] = parts[4] if len(parts) > 4 else None
                    mutation_row["mutation_type"] = parts[5] if len(parts) > 5 else None
                    mutation_row["acquisition_type"] = parts[6] if len(parts) > 6 else None
                    mutation_row["approved_date"] = parts[7] if len(parts) > 7 else None
                
                mutation_rows.append(mutation_row)
                print(f"  Row {row_idx}: {row_text}")
        
        print(f"Total mutation rows extracted: {len(mutation_rows)}")
        return mutation_rows

    async def _extract_selected_items(self, page: Page) -> Dict:
        await page.wait_for_timeout(1500)
        data: Dict[str, Any] = {}

        KNOWN_FIELDS = [
            ("Survey No", '#ctl00_MainContent_lblSurveyNo'),
            ("Transaction Year", '#ctl00_MainContent_lblTransactionYear'),
            ("Transaction No", '#ctl00_MainContent_lblTransactionNo'),
            ("MR No", '#ctl00_MainContent_lbl_MR_No'),
            ("Mutation Type", '#ctl00_MainContent_lblMutationType'),
            ("Acquisition Type", '#ctl00_MainContent_lblAcquisionType'),
        ]
        for field_name, selector in KNOWN_FIELDS:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        if field_name not in data:
                            data[field_name] = text
            except Exception:
                pass

        page_content = await page.content()
        soup = BeautifulSoup(page_content, 'html.parser')
        panel = soup.find(id='ctl00_MainContent_divDetails')
        if panel:
            labels = panel.find_all('span', id=re.compile(r'^ctl00_MainContent_Label\d+$'))
            for lab in labels:
                lab_text = lab.get_text(strip=True).rstrip(':').strip()
                if not lab_text or lab_text.lower() == 'selected items':
                    continue
                if lab_text in ("Acquisition Type", "Acquistion Type"):
                    lab_text = "Acquisition Type"
                nxt = lab.find_next('span')
                if nxt and nxt.get('id') and nxt.get('id', '').startswith('ctl00_MainContent_lbl'):
                    val = nxt.get_text(strip=True)
                    if val and lab_text not in data:
                        data[lab_text] = val

        print(f"  Selected Items extracted: {len(data)} fields")
        for k, v in list(data.items()):
            print(f"    - {k}: {v}")
        return data

    def _safe_filename(self, *parts: str) -> str:
        cleaned = []
        for p in parts:
            if not p:
                continue
            s = re.sub(r'[\\/*?:"<>|]+', '_', str(p)).strip()
            s = re.sub(r'\s+', '_', s)
            if s:
                cleaned.append(s)
        return "__".join(cleaned) if cleaned else "unknown"

    async def _extract_report_preview(self, page: Page, context, mutation_key: str) -> Dict:
        await page.wait_for_timeout(3500)
        screenshot_path = os.path.join(self.mutations_dir, f"{mutation_key}__preview.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"  Preview screenshot saved")

        page_content = await page.content()
        html_path = os.path.join(self.mutations_dir, f"{mutation_key}__preview.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page_content)

        soup = BeautifulSoup(page_content, 'html.parser')

        result: Dict[str, Any] = {
            "preview_page_url": page.url,
            "report_header": {},
            "land_area_table": [],
            "parties_table": [],
            "footer": {},
            "raw_tables": [],
        }

        tables = soup.find_all('table')
        for ti, t in enumerate(tables):
            rows = t.find_all('tr')
            tbl_rows = []
            for r in rows:
                cells = [c.get_text(separator=' ', strip=True) for c in r.find_all(['td', 'th'])]
                if any(c for c in cells):
                    tbl_rows.append(cells)
            if tbl_rows:
                result["raw_tables"].append({"table_index": ti, "rows": tbl_rows})

        kv_pairs: Dict[str, str] = {}
        for t in tables:
            rows = t.find_all('tr')
            for r in rows:
                cells = r.find_all(['td', 'th'])
                cleaned_cells = [c.get_text(separator=' ', strip=True) for c in cells]
                for cidx in range(0, len(cleaned_cells) - 1, 2):
                    k = cleaned_cells[cidx].rstrip(':').strip()
                    v = cleaned_cells[cidx + 1].strip()
                    if k and v and len(k) < 120 and not k.startswith('---'):
                        if k not in kv_pairs:
                            kv_pairs[k] = v
                if len(cleaned_cells) == 4:
                    k2 = cleaned_cells[2].rstrip(':').strip()
                    v2 = cleaned_cells[3].strip()
                    if k2 and v2 and len(k2) < 120 and k2 not in kv_pairs:
                        kv_pairs[k2] = v2

        result["report_header"] = {}
        header_like = {}
        area_keywords = ['ಒಟ್ಟು', 'ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ', 'ಕಂದಾಯ', 'ಭೂ ಕಂದಾಯ', 'ಜೋಡಿ', 'ಸೆಸ್ಸು', 'ಸೆರಿಸಲಾಗಿದೆ',
                        'Total', 'Land Revenue', 'Area', 'ಒಕ್ಕಳು', 'ಬಡಿ', 'ಬಲ', 'ಪಕ್ಷ', 'ಸ್ಥಿತಿ']
        party_keywords = ['ಸ್ವಾಧೀನದಾರರ ಹೆಸರು', 'ಎಸ್ಸಿಎಲ', 'ಕರಾರ', 'ಸ್ಥಿತಿ',
                          'Occupant', 'Name', 'SLC', 'Status', 'Party', 'ಹಕ್ಕು', 'ಋಣ',
                          'ಸಾಗುವಳಿ ವಿವರ', 'ಗೇಣಿಯ ವಿವರ', 'ವತ್ತಾರ ಸ್ಥಿತಿ', 'ವರ್ಗ', 'ಸ್ಥಿತಿ',
                          'ತಿಗೆ', 'ಮಳೆ', 'ಎಕ್ರೆ', 'ಗುಂಟೆ', 'ಕೃಷಿ', 'ಬೆಳೆ', 'ಸಿರಿ', 'ಬಾವಿ']

        for k, v in kv_pairs.items():
            k_norm = k.strip()
            is_area = any(kw in k_norm for kw in area_keywords)
            is_party = any(kw in k_norm for kw in party_keywords)
            if is_area or is_party:
                continue
            if len(k_norm) < 80 and len(v) < 200:
                header_like[k_norm] = v
        result["report_header"] = header_like

        for table_data in result["raw_tables"]:
            rows = table_data["rows"]
            if len(rows) < 2:
                continue
            header_row = rows[0]
            header_joined = " ".join(header_row)
            if any(x in header_joined for x in ['ಸರ್ವೆ ಸಂಖ್ಯೆ', 'Survey Number', 'ಸರ್ವೆ ನಂಬರು', 'ಸರ್ವೆ', 'ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ']) \
                    and any(x in header_joined for x in ['ಒಕ್ಕಳು', 'ಬಡಿ', 'ಕಲಕಟೆ', 'ವಿಭಾಗ', 'ಭಾಗ', 'ಹಣೆ', 'ಸರ್ಕಾರಿ']):
                for data_row in rows[1:]:
                    if not any(c for c in data_row):
                        continue
                    entry: Dict[str, Any] = {}
                    for ci, col_name in enumerate(header_row):
                        if ci < len(data_row):
                            key = col_name.rstrip(':').strip() or f"col{ci}"
                            entry[key] = data_row[ci]
                    if entry:
                        result["land_area_table"].append(entry)
                continue

            if any(x in header_joined for x in ['ಸರ್ವೆ ಸಂಖ್ಯೆ', 'ಸರ್ವೆ ನಂಬರು', 'Survey Number', 'ಸರ್ವೆ']) \
                    and (any(x in header_joined for x in ['ಸ್ಥಿತಿ', 'ಹೆ', 'ಎಸ್ಸಿಎಲ್', 'ಕರಾರ', 'ಸ್ವಾಧೀನದಾರರ ಹೆಸರು', 'ಹಕ್ಕು', 'ಪಕ್ಷ'])
                         or len(header_row) >= 5):
                for data_row in rows[1:]:
                    if not any(c for c in data_row):
                        continue
                    entry = {}
                    for ci, col_name in enumerate(header_row):
                        if ci < len(data_row):
                            key = col_name.rstrip(':').strip() or f"col{ci}"
                            entry[key] = data_row[ci]
                    if entry:
                        result["parties_table"].append(entry)

        footer_fields = {}
        all_body_text = soup.get_text('\n', strip=True)
        for line in all_body_text.split('\n'):
            line = line.strip()
            if ':' in line:
                k, _, v = line.partition(':')
                k = k.strip().rstrip(':').strip()
                v = v.strip()
                if k and v and len(k) < 80:
                    if any(x in k for x in ['ಆದೇಶದ ದಿನಾಂಕ', 'ಒಪ್ಪಂದ ದಿನಾಂಕ', 'ಮುಕ್ತಾಯ', 'ಮುಚ್ಚಲಗುಡ್ಡ', 'ರಾಜಸ್ವ', 'ಸ್ಥಿತಿ', 'ದಿನಾಂಕ', 'ದಾಖಲೆ', 'ಸರ್ಕಾರಿ ಶುಲ್ಕ', 'ನೋಂದಣಿ']):
                        footer_fields[k] = v
        result["footer"] = footer_fields

        print(f"  Report header fields: {len(result['report_header'])}")
        print(f"  Land area rows: {len(result['land_area_table'])}")
        print(f"  Mutation parties rows: {len(result['parties_table'])}")
        print(f"  Footer fields: {len(result['footer'])}")

        document_path = None
        try:
            img_selector = 'img[src*="Mutation"], img[src*="mutation"], img[src*="MR"], img[src*="mr"], img[id*="Doc"], img[id*="doc"]'
            doc_element = await page.query_selector(img_selector)
            if doc_element:
                document_path = os.path.join(self.mutations_dir, f"{mutation_key}__document.png")
                await doc_element.screenshot(path=document_path)
                print(f"  Captured document image")
            else:
                pdf_link = await page.query_selector('a[href*=".pdf"], a:has-text("PDF"), a:has-text("Download")')
                if pdf_link:
                    pdf_url = await pdf_link.get_attribute('href')
                    if pdf_url:
                        pdf_url = urljoin(page.url, pdf_url)
                        cookies = await context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}
                        headers = {
                            'Referer': page.url,
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36'
                        }
                        resp = requests.get(pdf_url, cookies=cookie_dict, headers=headers, allow_redirects=True, timeout=30)
                        if resp.status_code == 200:
                            document_path = os.path.join(self.mutations_dir, f"{mutation_key}.pdf")
                            with open(document_path, 'wb') as f:
                                f.write(resp.content)
                            print(f"  Downloaded PDF")
        except Exception as doc_err:
            print(f"  (document capture skipped: {doc_err})")

        if document_path:
            result["document_path"] = document_path
        result["screenshot_path"] = screenshot_path
        result["html_path"] = html_path

        return result

    async def _navigate_back_to_list(self, page: Page):
        print("  Navigating back to mutation list...")
        try:
            if "MR_MutationExtract.aspx" in page.url:
                print("    -> Already on list page, no back needed")
                return True
        except Exception:
            pass

        back_selectors = [
            '#ctl00_MainContent_btnBack',
            'input[value*="Back"]',
            'button:has-text("Back")',
            'a:has-text("Back")',
            'input[id*="btnBack"]',
            'a[id*="btnBack"]',
        ]
        for s in back_selectors:
            try:
                el = await page.query_selector(s)
                if el and await el.is_visible():
                    try:
                        async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                            try:
                                await el.click(timeout=4000)
                            except PlaywrightError:
                                await el.evaluate("e => e.click()")
                    except Exception:
                        try:
                            try:
                                await el.click(timeout=4000)
                            except PlaywrightError:
                                await el.evaluate("e => e.click()")
                            await page.wait_for_timeout(3000)
                        except Exception:
                            pass
                    await page.wait_for_timeout(2000)
                    print(f"    -> Clicked back via '{s}' — url: {page.url[:120]}")
                    if "MR_MutationExtract.aspx" in page.url or "ReportPreview" not in page.url:
                        return True
            except Exception:
                continue
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                await page.go_back()
        except Exception:
            try:
                await page.go_back()
                await page.wait_for_timeout(3000)
            except Exception:
                pass
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            await page.wait_for_timeout(3000)
        try:
            if "MR_MutationExtract.aspx" in page.url or "ReportPreview" not in page.url:
                print("    -> Used browser go_back() — url: " + page.url[:120])
                return True
        except Exception:
            pass
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
                await page.goto(self.mr_url, timeout=45000)
            await page.wait_for_timeout(2000)
            print("    -> Force navigated to base URL (success)")
            return True
        except Exception as e:
            print(f"    -> Force goto base URL failed: {e}")
            return False

    async def fetch_mutation(
        self,
        district: str,
        taluk: str,
        hobli: str,
        village: str,
        survey_no: str,
        max_mutations: Optional[int] = None,
        headless: bool = False,
        extract_details: bool = False,
    ) -> Dict:
        async def _fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    print(f"Navigating to {self.mr_url}")
                    await page.goto(self.mr_url)
                    await page.wait_for_load_state("networkidle")
                    print("Mutation Extract page loaded")

                    await self._fill_form_and_fetch(page, district, taluk, hobli, village, survey_no)
                    mutation_rows = await self._extract_mutation_table(page)
                    print(f"\nTotal mutations found: {len(mutation_rows)}")

                    if max_mutations is not None and max_mutations > 0:
                        original_count = len(mutation_rows)
                        mutation_rows = mutation_rows[:max_mutations]
                        if len(mutation_rows) < original_count:
                            print(f"(Limiting to first {len(mutation_rows)} of {original_count} via max_mutations={max_mutations})")

                    base_context = {
                        "district": district,
                        "taluk": taluk,
                        "hobli": hobli,
                        "village": village,
                        "survey_no_query": survey_no,
                    }

                    # If extract_details is False, just return the summary
                    if not extract_details:
                        summary_result = {
                            "search": base_context,
                            "total_found": len(mutation_rows),
                            "mutations": mutation_rows,
                            "generated_at": __import__("datetime").datetime.now().isoformat(),
                        }
                        print(f"\n{'='*60}")
                        print(f"SUMMARY (Status Only)")
                        print(f"  Total found: {len(mutation_rows)}")
                        print(f"{'='*60}")
                        return summary_result

                    index_entries = []
                    court_order_entries: List[Dict] = []
                    successes = 0
                    failures = 0

                    for idx, row in enumerate(mutation_rows):
                        mr = str(row.get("mr_number") or "")
                        ty = str(row.get("transaction_year") or "")
                        tn = str(row.get("transaction_no") or "")
                        surv = str(row.get("survey_no") or survey_no)
                        mtype = str(row.get("mutation_type") or "")

                        mutation_key = self._safe_filename(
                            f"MR{mr}", f"TY{ty.replace('-', '_')}", f"TN{tn}", f"S{surv.replace('/', '-')}"
                        )
                        print(f"\n{'='*60}")
                        print(f"[{idx+1}/{len(mutation_rows)}] Processing {mutation_key}")
                        print(f"{'='*60}")

                        if idx > 0:
                            try:
                                if "MR_MutationExtract.aspx" not in page.url and "ReportPreview" in page.url:
                                    await self._navigate_back_to_list(page)
                                try:
                                    sel_test = await page.query_selector_all('a:has-text("Select")')
                                    if len(sel_test) < max(2, idx + 1):
                                        print("  Table not present after back-nav — re-filling form...")
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

                        processed_ok = False

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

                            record["selected_items"] = await self._extract_selected_items(page)
                            print("  [2/3] Extracted Selected Items panel")
                        except Exception as sel_err:
                            print(f"  Select step failed: {sel_err}")
                            record["error"] = f"select_failed: {sel_err}"
                            failures += 1
                            index_entries.append(record)
                            _ = await self._save_single_record(record, mutation_key)
                            continue

                        try:
                            preview_selectors = [
                                '#ctl00_MainContent_btnPreview',
                                'input[value*="Preview"]',
                                'button:has-text("Preview")',
                                'a:has-text("Preview")',
                                'text=Preview',
                            ]
                            preview_clicked = False
                            preview_page = page
                            pages_before = set(context.pages)
                            current_url_before = page.url

                            for ps in preview_selectors:
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
                                        except PlaywrightError:
                                            await el.evaluate("e => e.click()")
                                    preview_clicked = True
                                    preview_page = page
                                    print(f"  [3/3] Clicked Preview ({ps}) — same-page nav captured")
                                    got_it = True
                                    break
                                except Exception:
                                    pass

                                if not got_it:
                                    try:
                                        popup_event = asyncio.create_task(context.wait_for_event("page", timeout=20000))
                                        try:
                                            try:
                                                await el.click(timeout=7000)
                                            except PlaywrightError:
                                                await el.evaluate("e => e.click()")
                                        except Exception:
                                            pass
                                        new_page = await popup_event
                                        try:
                                            await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                                        except Exception:
                                            pass
                                        preview_page = new_page
                                        preview_clicked = True
                                        print(f"  [3/3] Clicked Preview ({ps}) — NEW TAB opened: {new_page.url[:150]}")
                                        got_it = True
                                        break
                                    except Exception:
                                        pass

                                if not got_it:
                                    try:
                                        try:
                                            await el.click(timeout=7000)
                                        except PlaywrightError:
                                            await el.evaluate("e => e.click()")
                                        await page.wait_for_timeout(3000)
                                        try:
                                            await page.wait_for_load_state("networkidle", timeout=15000)
                                        except Exception:
                                            pass
                                        new_pages = [p for p in context.pages if p not in pages_before]
                                        if new_pages:
                                            preview_page = new_pages[0]
                                            try:
                                                await preview_page.wait_for_load_state("domcontentloaded", timeout=10000)
                                            except Exception:
                                                pass
                                            preview_clicked = True
                                            print(f"  [3/3] Clicked Preview ({ps}) — new tab detected: {preview_page.url[:150]}")
                                            break
                                        if "ReportPreview" in page.url or page.url != current_url_before:
                                            preview_page = page
                                            preview_clicked = True
                                            print(f"  [3/3] Clicked Preview ({ps}) — URL changed: {page.url[:150]}")
                                            break
                                        try:
                                            has_report = await page.evaluate(
                                                "() => (window.location.href.indexOf('ReportPreview') !== -1) || "
                                                "!!(document.querySelector('title') && document.title.toLowerCase().indexOf('preview') !== -1) || "
                                                "!!document.body && document.body.innerText && "
                                                "document.body.innerText.indexOf('ಮ್ಯುಟೇಶನ್ ಪ್ರತಿ') !== -1"
                                            )
                                            if has_report:
                                                preview_page = page
                                                preview_clicked = True
                                                print(f"  [3/3] Clicked Preview ({ps}) — report rendered on page")
                                                break
                                        except Exception:
                                            pass
                                    except Exception:
                                        continue

                            if not preview_clicked:
                                try:
                                    await page.wait_for_function(
                                        "() => window.location.href.indexOf('ReportPreview') !== -1",
                                        timeout=8000
                                    )
                                    preview_page = page
                                    preview_clicked = True
                                    print("  [3/3] Already on ReportPreview page")
                                except PlaywrightError:
                                    pass

                            if not preview_clicked:
                                new_pages = [p for p in context.pages if p not in pages_before]
                                if new_pages:
                                    preview_page = new_pages[0]
                                    preview_clicked = True
                                    print(f"  [3/3] Found ReportPreview page via fallback new-page check: {preview_page.url[:150]}")

                            if not preview_clicked:
                                print("  WARNING: Could not confirm Preview navigation. Attempting extract on current page anyway.")

                            try:
                                await preview_page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                pass
                            try:
                                await preview_page.bring_to_front()
                            except Exception:
                                pass

                            print(f"  Extracting report from: {preview_page.url[:150]}")
                            record["report_preview"] = await self._extract_report_preview(preview_page, context, mutation_key)
                            processed_ok = True
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
                        sources_ordered = [
                            ("from_table_row", record.get("from_table_row") or {}),
                            ("selected_items", record.get("selected_items") or {}),
                            ("report_header", (record.get("report_preview") or {}).get("report_header") or {}),
                            ("footer", (record.get("report_preview") or {}).get("footer") or {}),
                        ]
                        merged_fields = _merge_no_dupes(*[s[1] for s in sources_ordered])
                        merged_clean["fields"] = merged_fields
                        if record.get("report_preview"):
                            rpt = record["report_preview"]
                            merged_clean["land_area"] = rpt.get("land_area_table", [])
                            merged_clean["mutation_parties"] = rpt.get("parties_table", [])
                            if rpt.get("document_path"):
                                merged_clean["document_path"] = rpt["document_path"]
                            if rpt.get("screenshot_path"):
                                merged_clean["preview_screenshot"] = rpt["screenshot_path"]
                            if rpt.get("html_path"):
                                merged_clean["preview_html"] = rpt["html_path"]
                            if rpt.get("preview_page_url"):
                                merged_clean["preview_url"] = rpt["preview_page_url"]
                        if record.get("error"):
                            merged_clean["error"] = record["error"]

                        save_result = await self._save_single_record(merged_clean, mutation_key)
                        _m_path, _c_path, was_court_order = save_result
                        index_entries.append(merged_clean)
                        if was_court_order:
                            court_order_entries.append(merged_clean)

                        try:
                            back_ok = await self._navigate_back_to_list(page)
                            if not back_ok:
                                print("  Back nav uncertain; will re-fill form for next mutation")
                        except Exception as back_err:
                            print(f"  Back nav issue: {back_err}")

                    combined_path = os.path.join(self.mutations_dir, "ALL_MUTATIONS_COMBINED.json")
                    combined = {
                        "search": base_context,
                        "total_found": len(mutation_rows),
                        "total_processed": len(index_entries),
                        "successful_extractions": successes,
                        "failures": failures,
                        "court_orders_found": len(court_order_entries),
                        "generated_at": __import__("datetime").datetime.now().isoformat(),
                        "mutations": index_entries,
                    }
                    with open(combined_path, "w", encoding="utf-8") as f:
                        json.dump(combined, f, indent=2, ensure_ascii=False)

                    court_combined_path = os.path.join(self.court_orders_dir, "ALL_COURT_ORDERS_COMBINED.json")
                    court_combined = {
                        "search": base_context,
                        "total_mutations": len(mutation_rows),
                        "court_orders_found": len(court_order_entries),
                        "generated_at": __import__("datetime").datetime.now().isoformat(),
                        "court_orders": court_order_entries,
                    }
                    if court_order_entries:
                        with open(court_combined_path, "w", encoding="utf-8") as f:
                            json.dump(court_combined, f, indent=2, ensure_ascii=False)

                    print(f"\n{'='*60}")
                    print(f"SUMMARY")
                    print(f"  Total found:       {len(mutation_rows)}")
                    print(f"  Successful:        {successes}")
                    print(f"  Failed:            {failures}")
                    print(f"  Court orders:      {len(court_order_entries)}")
                    print(f"  Mutations dir:     {self.mutations_dir}")
                    print(f"  Court orders dir:  {self.court_orders_dir}")
                    print(f"  All mutations:     {combined_path}")
                    if court_order_entries:
                        print(f"  All court orders:  {court_combined_path}")
                    print(f"{'='*60}")

                    return combined
                finally:
                    await browser.close()

        return await _fetch()

    def _copy_artifact_if_exists(self, src_path: Optional[str], dst_dir: str) -> Optional[str]:
        if not src_path or not os.path.isfile(src_path):
            return None
        try:
            import shutil
            dst_path = os.path.join(dst_dir, os.path.basename(src_path))
            if os.path.abspath(src_path) != os.path.abspath(dst_path):
                shutil.copy2(src_path, dst_path)
            return dst_path
        except Exception:
            return None

    async def _save_single_record(self, record: Dict, mutation_key: str):
        path = os.path.join(self.mutations_dir, f"{mutation_key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        print(f"  Saved (mutations): {os.path.basename(path)}")

        is_co = self._is_court_order(record)
        court_path: Optional[str] = None
        if is_co:
            court_path = os.path.join(self.court_orders_dir, f"{mutation_key}.json")
            with open(court_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
            for asset_key in ("preview_screenshot", "preview_html", "document_path"):
                src = record.get(asset_key)
                self._copy_artifact_if_exists(src, self.court_orders_dir)
            print(f"  Saved (court_orders): {os.path.basename(court_path)} [+ assets]")
        return path, court_path, is_co
