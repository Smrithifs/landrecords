import asyncio
from playwright.async_api import async_playwright
import json, os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://kaveri.karnataka.gov.in/landing-page",
            wait_until="domcontentloaded", timeout=60000)
        
        # Click Login button
        await page.click("text=Login")
        await page.wait_for_timeout(2000)
        
        # Click Mobile/Email OTP Login
        await page.click("text=Mobile/Email OTP Login")
        await page.wait_for_timeout(2000)
        
        # Fill email
        await page.fill("input[type='email'], input[placeholder*='mail'], input[placeholder*='Mail']", 
            "smritzz0007@gmail.com")
        await page.wait_for_timeout(1000)
        
        print("\n=== COMPLETE OTP PROCESS MANUALLY ===")
        print("1. Click Send OTP/Get OTP button")
        print("2. Enter OTP from your email")
        print("3. Click Login/Submit")
        print("=== PRESS ENTER WHEN SUCCESSFULLY LOGGED IN ===")
        input()
        
        print(f"Current URL: {page.url}")
        
        # Wait for dashboard
        print("PRESS ENTER WHEN YOU SEE DASHBOARD")
        input()
        
        # Save session
        await context.storage_state(path="logs/debug/kaveri_auth.json")
        print("Session saved to logs/debug/kaveri_auth.json")
        
        # Navigate to Online EC
        print("Scrolling down to find Online EC...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        
        print("Clicking on Online EC...")
        await page.click("text=Online EC")
        await page.wait_for_timeout(2000)
        
        # Click Continue
        print("Clicking on Continue...")
        await page.click("text=Continue")
        await page.wait_for_timeout(2000)
        
        # Click After 2004
        print("Clicking on After 2004...")
        await page.click("text=After 2004")
        await page.wait_for_timeout(2000)
        
        print("Navigation to EC search page complete")
        print(f"Current URL: {page.url}")
        
        print("\n=== READY FOR EC SEARCH ===")
        print("Press ENTER when you're ready to fill in search details...")
        input()
        
        await browser.close()

asyncio.run(main())
