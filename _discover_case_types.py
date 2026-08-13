import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://judiciary.karnataka.gov.in/casemenu.php", wait_until="domcontentloaded", timeout=90000)
        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass
        await page.wait_for_timeout(1500)

        # Click Party Name tab
        for sel in ['li:has-text("Party Name")', 'a:has-text("Party Name")']:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                try:
                    await el.click()
                    break
                except Exception:
                    pass
        await page.wait_for_timeout(1500)

        # Set Bench = B (Bengaluru) and wait for AJAX load
        await page.select_option("#ptbenchid", value="B")
        # Wait for AJAX to populate
        try:
            await page.wait_for_function(
                "() => document.querySelectorAll('#pt_types option').length > 2", timeout=15000)
        except Exception as e:
            print(f"Warning: case types didn't load: {e}")
        await page.wait_for_timeout(2500)

        # Print pt_types options
        print("=== CASE TYPE OPTIONS FOR BENCH=B ===")
        opts = await page.query_selector_all("#pt_types option")
        for o in opts:
            v = await o.get_attribute("value") or ""
            t = (await o.inner_text() or "").strip()
            if v and v != "0":
                print(f"  value={v!r:15s}  label={t!r}")
        print(f"Total case type options: {len(opts)}")

        # Check other fields visible
        for fid in ["#ptbenchid", "#pt_types", "#pt_type1", "#pt_name", "#ptfrom_date", "#ptto_date", "#vercode"]:
            el = await page.query_selector(fid)
            ok = bool(el)
            vis = (await el.is_visible()) if el else False
            print(f"  {fid:20s}  exists={ok}  visible={vis}")
        await browser.close()

asyncio.run(main())
