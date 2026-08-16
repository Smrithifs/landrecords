#!/usr/bin/env python3
"""
Comprehensive Demo Script for Land Records Scrapers
Runs 3-4 examples from each scraper for client demonstration
"""
import asyncio
import subprocess
import sys
import os

# Color codes for output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_header(title):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}ℹ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

async def run_command(cmd, description):
    """Run a command and return success status"""
    print_header(description)
    print_info(f"Running: {cmd}")
    print()
    
    try:
        result = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        
        # Stream output in real-time
        while True:
            line = await result.stdout.readline()
            if not line:
                break
            print(line.decode().strip())
            
        await result.wait()
        
        if result.returncode == 0:
            print_success(f"{description} completed successfully")
            return True
        else:
            print_error(f"{description} failed with return code {result.returncode}")
            # Print stderr if available
            stderr = await result.stderr.read()
            if stderr:
                print(f"Error output: {stderr.decode()}")
            return False
            
    except Exception as e:
        print_error(f"Error running {description}: {e}")
        return False

async def main():
    print_header("LAND RECORDS SCRAPERS - COMPREHENSIVE DEMO")
    print_info("This demo will run 3-4 examples from each scraper")
    print_info("Make sure you have the .env file configured with API keys")
    print()
    
    results = {}
    
    # 1. Normal Bhoomi Public Scraper (No captcha, with Gemini extraction)
    results['normal_bhoomi'] = await run_command(
        "python3 test_bhoomi_public_gemini.py",
        "1. NORMAL BHOOMI PUBLIC SCRAPER (No captcha, with Gemini extraction)"
    )

    # 2. Public Bhoomi Scraper (5 examples with click and preview, survey 3)
    results['public_bhoomi'] = await run_command(
        "python3 test_public_mutation_scraper.py",
        "2. PUBLIC BHOOMI SCRAPER (5 mutations with click and preview, survey 3)"
    )

    # 3. Mutation Scraper with click and preview (5 examples, survey 3)
    results['mutation'] = await run_command(
        "python3 run_mutation_any.py --limit 5",
        "3. MUTATION SCRAPER (5 examples with click and preview, survey 3)"
    )

    # 4. High Court Party Scraper (5 searches)
    results['highcourt'] = await run_command(
        "python3 run_highcourt_party.py --max-searches 5 --captcha-mode terminal",
        "4. KARNATAKA HIGH COURT PARTY SCRAPER (5 searches)"
    )

    # 5. Eswathu Ekatha Scraper (5 searches)
    results['ekatha'] = await run_command(
        "python3 run_eswathu_ekatha.py --max-searches 5",
        "5. ESWATHU EKATHA SCRAPER (5 searches)"
    )

    # 6. Mutation Status Scraper (1 example, survey 3)
    results['mutation_status'] = await run_command(
        "python3 test_mutation_status_scraper.py",
        "6. MUTATION STATUS SCRAPER (1 example, survey 3)"
    )

    # 7. Gemini Extraction (Integrated in Public Bhoomi + Standalone option)
    # Note: Gemini extraction is already integrated in the Public Bhoomi scraper above
    # For standalone extraction from existing images:
    if os.path.exists("logs/debug/rtc_page.png"):
        results['gemini_extraction'] = await run_command(
            "python3 extract_with_gemini.py",
            "7. STANDALONE GEMINI EXTRACTION (from existing RTC images)"
        )
    else:
        print_info("Skipping standalone Gemini extraction - no RTC images found")
        print_info("Note: Gemini extraction is already integrated in Public Bhoomi scraper (#2 above)")
        results['gemini_extraction'] = None

    # 8. Court Orders Extraction (5 examples)
    results['court_orders'] = await run_command(
        "python3 backfill_court_orders.py",
        "8. COURT ORDERS EXTRACTION (from existing mutations)"
    )
    
    # Summary
    print_header("DEMO SUMMARY")
    for scraper, result in results.items():
        if result is True:
            print_success(f"{scraper}: PASSED")
        elif result is False:
            print_error(f"{scraper}: FAILED")
        else:
            print_info(f"{scraper}: SKIPPED")
    
    print()
    print_info("Demo completed! Check the logs/debug/ directory for outputs")
    print_info("Each scraper saves its results in respective subdirectories")

if __name__ == "__main__":
    asyncio.run(main())