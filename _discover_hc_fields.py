import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://judiciary.karnataka.gov.in/casemenu.php", wait_until="domcontentloaded", timeout=90000)
        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        # Click Party Name tab (using multiple selectors from your earlier working selector
        for sel in [
            'li:has-text("Party Name")',
            'a:has-text("Party Name")',
        ]:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                try:
                    await el.click()
                    print(f"Clicked Party Name tab via {sel}")
                    break
                except Exception:
                    pass
        await page.wait_for_timeout(2000)

        content = await page.content()
        out = "/Users/smrithis/Desktop/landrecords/logs/debug/karnataka_highcourt/_page_dump.html"
        import os
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved full page HTML to {out}")
        await page.screenshot(path=out.replace(".html", ".png"), full_page=True)
        print(f"Saved screenshot")

        # List selects
        print("\n=== ALL <select> ELEMENTS:")
        sels = await page.query_selector_all("select")
        for i, s in enumerate(sels):
            sid = await s.get_attribute("id") or ""
            nm = await s.get_attribute("name") or ""
            try:
                vis = await s.is_visible()
            except Exception:
                vis = "?"
            opts = await s.query_selector_all("option")
            previews = []
            for o in opts[:10]:
                v = await o.get_attribute("value") or ""
                t = (await o.inner_text() or "").strip()
                if t:
                    previews.append(f"{t!r}={v!r}")
            print(f"  [{i}] id={sid!r}  name={nm!r}  visible={vis}")
            print(f"       options (first {min(10, len(previews))}: {', '.join(previews)}")

        print("\n=== ALL VISIBLE TEXT/INPUT ELEMENTS:")
        inps = await page.query_selector_all("input")
        j = 0
        for inp in inps:
            try:
                if not await inp.is_visible():
                    continue
            except Exception:
                pass
            itype = await inp.get_attribute("type") or ""
            iid = await inp.get_attribute("id") or ""
            inm = await inp.get_attribute("name") or ""
            icls = await inp.get_attribute("class") or ""
            iph = await inp.get_attribute("placeholder") or ""
            ival = await inp.input_value() if itype != "password" else ""
            print(f"  [{j}] type={itype!r:10s} id={iid!r} name={inm!r} placeholder={iph!r}")
            j += 1

        print("\n=== BUTTONS/SUBMITS visible:")
        btns = await page.query_selector_all("input[type=submit], input[type=button], button")
        for i, b in enumerate(btns):
            try:
                vis = await b.is_visible()
            except Exception:
                vis = "?"
            if vis is True:
                bid = await b.get_attribute("id") or ""
                bnm = await b.get_attribute("name") or ""
                bval = await b.get_attribute("value") or ""
                btxt = ""
                try:
                    btxt = (await b.inner_text() or "").strip()
                except Exception:
                    pass
                print(f"  [{i}] id={bid!r} name={bnm!r} value={bval!r} text={btxt!r}")

        await browser.close()

asyncio.run(main())
